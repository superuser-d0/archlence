"""Tekrarlanan ödeme / abonelik kuralları — Kivy'den bağımsız servis katmanı.

Aboneliklerin TEK kayıt yeri `recurring_payments` tablosudur. `subscriptions`
adında ikinci bir tablo bir ara oluşturulmuştu ama hiçbir yerden okunmuyordu;
iki ayrı doğruluk kaynağı tutmak (biri UI'ın okuduğu, diğeri boş) sessiz
tutarsızlık üretirdi, o yüzden bu servis yalnız `recurring_payments` üzerinde
çalışır.
"""

import calendar
from datetime import date, datetime

from database.db import (
    SECRET_KEY, _advance_due_date, adjust_account_balance, get_connection,
)
from utils.crypto import decrypt, encrypt
from utils.errors import DecryptionError, KeyUnavailableError


SUBSCRIPTION_CATEGORY = "Dijital Abonelik"

# Aboneliğe işaret eden kategoriler. SUBSCRIPTION_CATEGORY kullanıcının açıkça
# "bu bir abonelik" dediği kategori; diğerleri kredi kartından geçen tipik
# abonelik kalemleri.
SUBSCRIPTION_CATEGORIES = {
    "Dijital Abonelik",
    "Dijital Platformlar",
    "Yazılım & Lisans",
    "Eğitim & Kurs",
    "Spor & Sağlık (Abonelik)",
    "Bağış (Düzenli)",
}

# Açıklamada geçince harcamayı abonelik sayan marka adları. Küçük harfe
# duyarsız ALT DİZE olarak aranır (bkz. looks_like_subscription): "NETFLIX.COM
# 12/2026" içinde "netflix" bulunur. Adlar normalize (küçük harf, sade) tutulur;
# marka LOGOSU ayrı bir sistemdir (services/brand_icon_service.py::_BRANDS) ve
# oradaki alias'lar bu listeye örnek alındı.
# DİKKAT: eşleşme düz alt dizedir (kelime sınırı yok). Bu yüzden kısa/yaygın
# tokenler (tod, gain, calm, steam, fitness...) BİLEREK dışarıda bırakıldı;
# "again"/"bargain"/"steamed" gibi masum metinlerde yanlış pozitif üretirlerdi.
# Yalnız ayırt edici (≈5+ harf) adlar listelenir. Kategori sinyali zaten
# "Dijital Platformlar" gibi durumları kapsıyor; bu liste ikincil bir sinyal.
KNOWN_BRANDS = [
    # Video / müzik / içerik platformları
    "netflix", "spotify", "youtube premium", "youtube music", "amazon prime",
    "prime video", "disney+", "disney plus", "blutv", "exxen", "mubi",
    "deezer", "tabii", "hbo max", "apple music", "apple tv", "apple one",
    "twitch", "paramount plus", "paramount+", "peacock", "crunchyroll",
    "tidal", "soundcloud go", "soundcloud",
    # Kitap / sesli kitap
    "storytel", "audible", "kindle unlimited", "blinkist",
    # Yazılım / lisans / bulut
    "adobe", "creative cloud", "microsoft 365", "office 365", "icloud",
    "google one", "dropbox", "notion", "figma", "canva", "jetbrains",
    "github", "1password", "lastpass", "nordvpn", "expressvpn",
    "proton vpn", "protonvpn", "proton mail", "protonmail", "proton pass",
    "protonpass", "proton drive", "protondrive", "proton calendar",
    "protoncalendar", "proton unlimited", "proton duo", "proton family",
    "proton visionary", "proton",
    # Telekomünikasyon / internet
    "türk telekom", "turk telekom", "türktelekom", "turktelekom", "ttnet",
    "vodafone türkiye", "vodafone turkey", "vodafone net", "vodafone",
    "turkcell superonline", "superonline", "turkcell",
    "chatgpt", "openai", "claude", "anthropic", "gemini advanced",
    "slack", "zoom", "linkedin premium", "meta verified",
    # Eğitim / kurs
    "udemy", "coursera", "duolingo", "skillshare",
    # Spor / sağlık / üyelik
    "macfit", "club sporium", "clubsporium", "sporium", "strava",
    "headspace", "spotify premium",
    # Bağış / üyelik
    "patreon", "wikipedia",
    # Oyun
    "playstation plus", "ps plus", "xbox game pass", "game pass",
    "nintendo online", "ea play", "ubisoft+", "ubisoft plus",
]


def apply_category_trigger(category, recurring_switch) -> bool:
    """Dijital abonelik seçildiyse switch'i bir kez açar.

    Sonrasında kalıcı bir binding kurulmaz; kullanıcı switch'i manuel olarak
    tekrar kapatabilir.
    """
    should_enable = str(category).strip() == SUBSCRIPTION_CATEGORY
    if should_enable:
        recurring_switch.active = True
    return should_enable


def next_due_for_recurrence(
        from_date: str | date, frequency: str, recurrence_day: int) -> str:
    """Bir sonraki periyodu seçilen ay gününe sabitleyerek döndürür."""
    day = int(recurrence_day)
    if not 1 <= day <= 31:
        raise ValueError("Tekrarlama günü 1 ile 31 arasında olmalıdır.")
    source = from_date if isinstance(from_date, date) else date.fromisoformat(from_date)
    advanced = date.fromisoformat(_advance_due_date(source.isoformat(), frequency))
    valid_day = min(day, calendar.monthrange(advanced.year, advanced.month)[1])
    return advanced.replace(day=valid_day).isoformat()


def initial_recurring_income_date(
        reference_date: date, recurrence_day: int, include_current_month: bool
) -> date | None:
    """İlk maaş kaydının tarihini kullanıcı kararına göre belirler.

    Ayın seçilen günü geçtiyse "bu ayı dahil et" bugüne yazar; henüz
    gelmediyse o güne bekleyen işlem planlar. 29-31 seçimleri kısa aylarda
    ayın son gününe sıkıştırılır. Dahil edilmeyen ay hiç işlem üretmez.
    """
    if not include_current_month:
        return None
    day = int(recurrence_day)
    if not 1 <= day <= 31:
        raise ValueError("Tekrarlama günü 1 ile 31 arasında olmalıdır.")
    valid_day = min(
        day,
        calendar.monthrange(reference_date.year, reference_date.month)[1],
    )
    occurrence = reference_date.replace(day=valid_day)
    return occurrence if occurrence > reference_date else reference_date


def looks_like_subscription(category, description="", is_credit_card=False):
    """İşlem tekrar eden bir abonelik gibi mi görünüyor?

    Üç sinyal aranır (herhangi biri yeterli):
      1. Kategori açıkça abonelik kategorilerinden biri.
      2. Açıklamada tanınan bir marka adı geçiyor (KNOWN_BRANDS).
      3. Kredi kartından geçen ve kategorisi abonelik olan harcama.

    Kredi kartı sinyali TEK BAŞINA yeterli DEĞİL: karttan yapılan her market
    alışverişi abonelik sayılırsa radar çöp dolar. Kart yalnızca kategori/marka
    sinyalini güçlendirir.
    """
    normalized_category = str(category or "").strip()
    if normalized_category in SUBSCRIPTION_CATEGORIES:
        return True

    if KNOWN_BRANDS:
        haystack = f"{description or ''} {normalized_category}".casefold()
        for brand in KNOWN_BRANDS:
            if str(brand).casefold() in haystack:
                return True

    # is_credit_card şu an yalnız yukarıdaki sinyallerle birlikte anlamlı;
    # imzada tutuluyor çünkü çağıran taraf bu bilgiyi zaten hesaplıyor ve
    # GEMINI marka listesini doldurduğunda kural buradan genişletilecek.
    return False


def register_subscription_from_transaction(
        account_id, amount, category, description, frequency="monthly",
        recurrence_day=None, transaction_date=None, is_credit_card=False):
    """Abonelik gibi görünen işlemi `recurring_payments` radarına yazar.

    İşlem defterine (transactions) yazma işini ÇAĞIRAN yapar; bu fonksiyon
    yalnızca "Aktif Aboneliklerim" kaydını ekler. Böylece bir işlem hem normal
    gider olarak görünür hem de radara düşer.

    Aynı isimde aktif bir abonelik varsa hiçbir şey yapmaz (idempotent) —
    kullanıcı aynı aboneliği her ay elle girse bile radar tek kayıt tutar.

    Kaydedildiyse yeni satırın id'sini, atlandıysa None döner.
    """
    from database.db import (
        get_active_recurring_payments, has_active_recurring_payment,
        insert_recurring_payment,
    )

    # Bu interceptor yalnız kredi kartı harcamaları içindir. Kart dışındaki
    # açıkça tekrarlanan ödemeler formun recurring akışı tarafından kaydedilir;
    # onları burada da yakalamak iki ayrı kayıt üretirdi.
    if not is_credit_card:
        return None
    if not looks_like_subscription(category, description, is_credit_card):
        return None

    name = (description or category or "").strip()
    if not name:
        return None
    if has_active_recurring_payment(name):
        return None

    reference = (
        date.fromisoformat(str(transaction_date)[:10])
        if transaction_date else date.today()
    )
    day = int(recurrence_day or reference.day)
    next_due = next_due_for_recurrence(reference, frequency, day)

    insert_recurring_payment(
        name, float(amount), category, frequency, next_due,
        auto_deduct=0, account_id=account_id, recurrence_day=day,
    )
    match = [
        payment for payment in get_active_recurring_payments()
        if payment["name"] == name
    ]
    return match[0]["id"] if match else None


def _get_payment(cursor, payment_id):
    """Aboneliği ham satır olarak okur (ad/tutar hâlâ şifreli)."""
    cursor.execute(
        "SELECT * FROM recurring_payments WHERE id = ?", (int(payment_id),)
    )
    return cursor.fetchone()


def _plain_name(raw):
    try:
        return decrypt(str(raw), SECRET_KEY) or ""
    except KeyUnavailableError:
        # Anahtar yoksa TÜM kayıtlar etkilenir; satır bazında yutmak toplam
        # arızayı "hepsi adsız" diye normal veri gibi gösterirdi.
        raise
    except (DecryptionError, ValueError, TypeError):
        from utils.logging_config import get_logger
        get_logger().exception(
            "[VERİ BÜTÜNLÜĞÜ] recurring_payments adı çözülemedi")
        return ""


def _plain_amount(raw):
    try:
        return float(decrypt(str(raw), SECRET_KEY))
    except KeyUnavailableError:
        raise
    except (DecryptionError, ValueError, TypeError):
        from utils.logging_config import get_logger
        get_logger().exception("[VERİ BÜTÜNLÜĞÜ] recurring_payments tutarı çözülemedi")
        return 0.0


def update_subscription_amount(payment_id, new_amount):
    """Aboneliğin güncel ücretini değiştirir (zam senaryosu).

    Kullanıcı zam gelince aboneliği silip yeniden kurmak zorunda kalmamalı;
    silme+yeniden kurma vade geçmişini ve `next_due_date` hizasını da
    sıfırlardı. Yalnız tutar güncellenir, vade dokunulmaz.
    """
    amount = float(new_amount)
    if amount <= 0:
        raise ValueError("Abonelik ücreti 0'dan büyük olmalıdır.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE recurring_payments SET amount = ?"
            " WHERE id = ? AND is_active = 1",
            (encrypt(str(amount), SECRET_KEY), int(payment_id)),
        )
        updated = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    return updated > 0


def skip_next_occurrence(payment_id):
    """Aboneliği iptal ETMEDEN yalnızca bir sonraki tahsilatı atlar.

    Spec'teki "sadece bu ay için sil" seçeneği: kayıt aktif kalır, vade bir
    periyot ileri alınır. Böylece kullanıcı gelecek ayları kaybetmeden tek bir
    dönemi atlayabilir. Yeni vade tarihini döndürür; abonelik yoksa None.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        row = _get_payment(cursor, payment_id)
        if row is None or not row["is_active"]:
            return None
        new_due = next_due_for_recurrence(
            row["next_due_date"],
            row["frequency"],
            row["recurrence_day"] or int(str(row["next_due_date"])[8:10]),
        )
        cursor.execute(
            "UPDATE recurring_payments SET next_due_date = ? WHERE id = ?",
            (new_due, int(payment_id)),
        )
        conn.commit()
    finally:
        conn.close()
    return new_due


def cancel_subscription(payment_id):
    """Aboneliği kalıcı olarak durdurur (bu ay ve sonraki tüm aylar).

    Satır SİLİNMEZ, `is_active = 0` yapılır: geçmiş işlemler ve abonelik
    radarının "bu zaten takip ediliyor" kontrolü kaydın varlığına dayanıyor,
    fiziksel silme geçmişi yeniden "keşfedilecek aday" hâline getirirdi.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE recurring_payments SET is_active = 0 WHERE id = ?",
            (int(payment_id),),
        )
        updated = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    return updated > 0


def find_current_period_charge(payment_id, today=None):
    """Bu ay bu abonelik için kesilmiş otomatik tahsilatı bulur.

    `process_due_recurring_payment` açıklamayı `"{ad} (Otomatik)"` olarak
    ŞİFRELİ yazar; bu yüzden açıklama SQL'de aranamaz, aday satırlar çekilip
    Python'da çözülür (projedeki genel desen). Bulunursa
    {'id', 'amount', 'date'}, yoksa None döner.
    """
    reference = date.fromisoformat(today) if today else date.today()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        row = _get_payment(cursor, payment_id)
        if row is None:
            return None
        name = _plain_name(row["name"])
        expected_description = f"{name} (Otomatik)"

        cursor.execute(
            "SELECT id, amount, description, transaction_date FROM transactions"
            " WHERE account_id = ? AND type = 'expense'"
            "   AND COALESCE(category, '') = COALESCE(?, '')"
            "   AND strftime('%Y-%m', transaction_date) = ?"
            " ORDER BY id DESC",
            (row["account_id"], row["category"], reference.strftime("%Y-%m")),
        )
        candidates = cursor.fetchall()
    finally:
        conn.close()

    for candidate in candidates:
        try:
            description = decrypt(str(candidate["description"]), SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            # Bu bir ARAMA döngüsü: çözülemeyen aday atlanır, çünkü onu
            # eşleşme sayamayız. Yine de iz bırakılır — sessizce atlamak,
            # "eşleşme bulunamadı" ile "veri bozuk" arasındaki farkı siler.
            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] aday işlem id=%s açıklaması çözülemedi",
                candidate["id"] if "id" in candidate.keys() else "?")
            continue
        if description == expected_description:
            return {
                "id": candidate["id"],
                "amount": _plain_amount(candidate["amount"]),
                "date": candidate["transaction_date"],
            }
    return None


def refund_current_period_charge(payment_id, today=None):
    """Bu ay kesilen abonelik ücretini bakiyeye geri ekler.

    Kullanıcı aboneliği gerçekte iptal edip uygulamadan silmeyi unuttuğunda
    para boşuna düşmüş olur. Orijinal gider satırı SİLİNMEZ; dengeleyici bir
    gelir işlemi yazılır (çift kayıt mantığı) — geçmişi yeniden yazmak yerine
    tersine çeviriyoruz, böylece defter ile bakiye tutarlı kalır.

    İade edilen tutarı döndürür; bu ay tahsilat yoksa 0.0.
    """
    charge = find_current_period_charge(payment_id, today=today)
    if not charge or charge["amount"] <= 0:
        return 0.0

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "INSERT OR IGNORE INTO recurring_operation_markers "
            "(recurring_payment_id, due_date, operation_type) VALUES (?, ?, 'refund')",
            (payment_id, str(charge["id"])),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            return 0.0
        row = _get_payment(cursor, payment_id)
        if row is None:
            return 0.0
        name = _plain_name(row["name"])
        amount = float(charge["amount"])

        cursor.execute(
            "INSERT INTO transactions"
            " (account_id, amount, type, category, description,"
            "  transaction_date, status, execution_date)"
            " VALUES (?, ?, 'income', ?, ?, ?, 'completed', ?)",
            (
                row["account_id"],
                encrypt(str(amount), SECRET_KEY),
                row["category"],
                encrypt(f"{name} aboneliği iadesi", SECRET_KEY),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        # Bakiye ve defter aynı commit içinde (adjust_account_balance sözleşmesi).
        adjust_account_balance(
            cursor, row["account_id"], "income", amount,
            ref_id=cursor.lastrowid, source="subscription_refund",
        )
        conn.commit()
    finally:
        conn.close()
    return amount
