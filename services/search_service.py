"""Hesap ve kategori adlarında arama.

KAPSAM BİLEREK DAR. Yalnızca `accounts.name` ve `categories.name` aranır —
ikisi de düz metin (bkz. account_service.py'nin tepesindeki not: hesap adı
şifrelenmez). İşlem açıklamaları KAPSAM DIŞI ve bu bir eksiklik değil, bilinçli
bir sınır: o alanlar AES ile şifreli tutuluyor, yani orada arama yapmak filtreyi
SQL'e itmek yerine bir çalışma kümesini belleğe çözmek demek. 50.000 işlemli bir
profilde tüm veriyi çözmek 1,1 sn sürüyor (docs/performance/benchmark-results-windows.json).
Bu tur o maliyeti almıyor; kararın kaydı docs/ROADMAP.md Phase 2'de.

TÜRKÇE KATLAMA BU DOSYANIN ASIL İŞİ. Depoda hâlihazırda arama yapan iki yer
(mixins/budget_mixin.py, mixins/asset_mixin.py) düz `.casefold()` kullanıyor ve
bu Türkçe'de YANLIŞ sonuç verir: `"I".casefold()` → `"i"` ama `"ı".casefold()`
→ `"ı"`, yani "ISI" yazan kullanıcı "ısı" kaydını bulamaz. `"İ".casefold()` ise
`"i"` + U+0307 (birleşen nokta) üretir — görsel olarak "i" ama eşit değil.
`normalize()` üçünü de aynı yere indirir.
"""

import unicodedata

from database.db import managed_connection

#: Tek çağrıda dönecek en fazla sonuç. Açılır liste bundan uzunsa zaten
#: kullanışlı olmaktan çıkar; kullanıcı yazmaya devam ederek daraltır.
DEFAULT_LIMIT = 20

ACCOUNT = "account"
CATEGORY = "category"
TRANSACTION = "transaction"

#: İşlem açıklamalarında aranırken çözülecek EN YENİ satır sayısı.
#:
#: BU SAYI BİR GÜVENLİK/PERFORMANS TAKASI, keyfi bir sabit değil. Açıklamalar
#: AEAD ile şifreli tutuluyor, yani filtre SQL'e itilemiyor: eşleştirmek için
#: satırları belleğe çözmek gerekiyor. Üç seçenek vardı ve ikisi reddedildi:
#:
#:   * Yazma-zamanı arama indeksi — en hızlısı, ama düz-metne yakın veriyi
#:     diske geri koyuyor ve açıklamaları şifrelemenin amacını ortadan
#:     kaldırıyor. Kendi tehdit incelemesi olmadan alınacak bir karar değil;
#:     ALINMADI.
#:   * Tüm veriyi çözmek — 50.000 işlemde 1,1 sn ölçüldü
#:     (docs/performance/benchmark-results-windows.json). Her tuş vuruşunda
#:     kabul edilemez.
#:   * SINIRLI PENCERE — seçilen bu. En yeni N satır çözülüyor.
#:
#: 500 ölçülerek seçildi: bu makinede 200/500/1000 satır sırasıyla
#: 7,3 / 17,5 / 34,8 ms. 500, tek kare bütçesinin (33 ms) altında kalıyor ve
#: yavaş bir makinede 3 kat yavaşlasa bile donma değil, düşen bir kare üretir.
#: 1000 zaten sınırda olduğu için seçilmedi.
#:
#: BEDELİ AÇIK: bu pencereden eski bir işlem açıklamasıyla BULUNAMAZ. Hesap ve
#: kategori araması bu sınırdan etkilenmez; onlar düz metin ve SQL'de filtreleniyor.
DEFAULT_DESCRIPTION_WINDOW = 500


def normalize(text):
    """Aramada karşılaştırılabilir tek bir biçime indirger.

    Sıra ÖNEMLİ ve şu adımlardan oluşuyor:

    1. `casefold()` — büyük/küçük harf farkını düşürür.
    2. NFKD — birleşik harfleri taban + birleşen işarete ayırır
       (`ş` → `s` + cedilla, `ğ` → `g` + breve, `ö` → `o` + iki nokta).
    3. Birleşen işaretleri at — böylece aksansız yazan kullanıcı da bulur:
       "sirket" → "Şirket", "gunluk" → "Günlük".
    4. `ı` → `i` — NFKD bunu ayrıştırmaz, çünkü noktasız ı Unicode'da ayrı bir
       harftir, birleşimli değil. Bu satır olmadan 2. adım ı/i ayrımını
       çözmez ve Türkçe aramanın en sık kırıldığı yer burasıdır.

    `is_read_only_asset_account` (ui/components.py) aynı zinciri kullanıyor;
    bilerek aynı, çünkü iki yerde farklı normalize etmek sessiz tutarsızlık
    üretir.
    """
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    stripped = "".join(
        char for char in folded if not unicodedata.combining(char)
    )
    return " ".join(stripped.replace("ı", "i").split())


def matches(query, *candidates):
    """Sorgu, verilen alanlardan HERHANGİ birinde geçiyor mu.

    Liste FİLTRELEYEN çağıranlar için (bütçe kategori seçici, BIST/kripto
    seçicileri). `search()`ten farklı olarak BOŞ SORGU `True` döndürür: orada
    boş sorgu "hiçbir şey gösterme" demekti, burada "filtreleme yok, hepsini
    göster" demek. İki karşıt varsayılan bilerek ayrı fonksiyonlarda; tek
    fonksiyona bayrak eklemek çağrı yerinde hangi davranışın geçerli
    olduğunu okunmaz kılardı.
    """
    needle = normalize(query)
    if not needle:
        return True
    return any(needle in normalize(candidate) for candidate in candidates)


def _rank(needle, haystack):
    """Eşleşmenin ne kadar iyi olduğunu döndürür; eşleşme yoksa None.

    0 = birebir, 1 = baştan eşleşme, 2 = içinde geçiyor. Küçük olan önce.
    Kullanıcı "Nakit" yazdığında "Nakit" sonucu "Nakit Olmayan"ın üstünde
    çıksın diye; salt içerik kontrolü bu sırayı vermiyordu.
    """
    if not needle:
        return None
    if haystack == needle:
        return 0
    if haystack.startswith(needle):
        return 1
    if needle in haystack:
        return 2
    return None


def match_names(query, items):
    """Saf eşleştirme — DB'ye dokunmaz, bu yüzden doğrudan test edilebilir.

    `items`: `{"name": ..., ...}` sözlüklerinden oluşan sıra. Girdi sözlükleri
    DEĞİŞTİRİLMEZ; eşleşenlerin kopyası döner.
    """
    needle = normalize(query)
    if not needle:
        return []
    scored = []
    for position, item in enumerate(items):
        rank = _rank(needle, normalize(item.get("name")))
        if rank is None:
            continue
        # `position` beraberlik bozucu: eşit puanlı sonuçlar çağıranın
        # verdiği sırayı korur (hesaplarda vadesiz-önce, kategorilerde
        # alfabetik). Sıralamanın kararlı olması testleri de deterministik
        # kılıyor.
        scored.append((rank, position, dict(item)))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [item for _rank_value, _position, item in scored]


def search_transactions(query, limit=DEFAULT_LIMIT,
                        window=DEFAULT_DESCRIPTION_WINDOW):
    """En yeni `window` işlemin AÇIKLAMASINDA arar.

    Açıklama şifreli olduğu için eşleştirme Python'da yapılıyor; sıralama ve
    pencereleme düz kolon (`transaction_date`) üzerinden SQL'de. Pencerenin
    neden var olduğu ve bedelinin ne olduğu için `DEFAULT_DESCRIPTION_WINDOW`.

    Çözülemeyen tek bir satır aramayı düşürmez, atlanır — bozuk/eski bir kayıt
    yüzünden kutu tamamen çalışmaz hâle gelmemeli. Ama anahtarın kendisi
    yoksa bu bir satır sorunu değil, `KeyUnavailableError` yukarı çıkar;
    `get_pending_transactions` ile aynı ayrım.
    """
    needle = normalize(query)
    if not needle:
        return []

    from utils.crypto import decrypt
    from utils.errors import DecryptionError, KeyUnavailableError
    from database.db import SECRET_KEY

    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, account_id, description, category, transaction_date "
            "FROM transactions WHERE description IS NOT NULL "
            "ORDER BY date(transaction_date) DESC, id DESC LIMIT ?",
            (int(window),),
        )
        rows = cursor.fetchall()

    results = []
    for row in rows:
        try:
            description = decrypt(str(row[2]), SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            continue
        if _rank(needle, normalize(description)) is None:
            continue
        results.append({
            "kind": TRANSACTION,
            "id": row[0],
            "name": description,
            "detail": row[3] or "",
            "date": row[4],
        })
        # Sıra zaten en yeniden eskiye; `limit` dolunca kalanları çözmenin
        # anlamı yok ve çözme bu döngüdeki tek pahalı iş.
        if len(results) >= limit:
            break
    return results


def search(query, limit=DEFAULT_LIMIT):
    """Hesap ve kategori adlarında arar, sıralı tek liste döndürür.

    Boş/boşluk-only sorgu BOŞ liste döndürür — "her şeyi listele" davranışı
    bilerek yok: arama kutusu odaklanınca tüm profili dökmemeli.
    """
    needle = normalize(query)
    if not needle:
        return []

    with managed_connection() as conn:
        cursor = conn.cursor()
        # Vadesizler önce, sonra kredi kartları — AccountService.get_accounts
        # ile aynı sıra, böylece açılır listedeki sıra hesaplar ekranıyla
        # tutarlı görünüyor.
        cursor.execute(
            "SELECT id, name, account_type FROM accounts "
            "ORDER BY CASE WHEN account_type = 'credit_card' THEN 1 ELSE 0 END, id"
        )
        accounts = [
            {"kind": ACCOUNT, "id": row[0], "name": row[1], "detail": row[2]}
            for row in cursor.fetchall()
        ]
        cursor.execute(
            "SELECT name, type FROM categories ORDER BY name"
        )
        categories = [
            {"kind": CATEGORY, "id": None, "name": row[0], "detail": row[1]}
            for row in cursor.fetchall()
        ]

    # Kümeler AYRI eşleştirilip sonra birleştiriliyor: hesaplar kategorilerden,
    # kategoriler de işlemlerden önce gelsin diye. Tek listede eşleştirmek,
    # alfabetik olarak öne düşen bir kategoriyi kullanıcının kendi hesabının
    # üstüne çıkarabilirdi.
    #
    # İŞLEMLER EN SONA: en pahalı küme onlar (çözme gerektiriyor) ve en
    # gürültülüsü — 500 satırlık pencerede bir kelime çok kez geçebilir.
    # Hesap/kategori isabetleri kullanıcının aradığı şey olma ihtimali daha
    # yüksek ve onlar tepede kalıyor.
    results = match_names(query, accounts) + match_names(query, categories)
    if len(results) < limit:
        results += search_transactions(query, limit=limit - len(results))
    return results[:limit]
