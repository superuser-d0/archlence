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


SUBSCRIPTION_CATEGORY = "Dijital Abonelik"


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


def _get_payment(cursor, payment_id):
    """Aboneliği ham satır olarak okur (ad/tutar hâlâ şifreli)."""
    cursor.execute(
        "SELECT * FROM recurring_payments WHERE id = ?", (int(payment_id),)
    )
    return cursor.fetchone()


def _plain_name(raw):
    try:
        return decrypt(str(raw), SECRET_KEY) or ""
    except Exception:
        return ""


def _plain_amount(raw):
    try:
        return float(decrypt(str(raw), SECRET_KEY))
    except Exception:
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
        except Exception:
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
