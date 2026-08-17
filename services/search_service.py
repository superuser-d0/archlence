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

    # İki küme AYRI eşleştirilip sonra birleştiriliyor: hesaplar kategorilerden
    # önce gelsin diye. Tek listede eşleştirmek, alfabetik olarak öne düşen bir
    # kategoriyi kullanıcının kendi hesabının üstüne çıkarabilirdi.
    results = match_names(query, accounts) + match_names(query, categories)
    return results[:limit]
