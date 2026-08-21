import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from utils.crypto import encrypt, decrypt
from utils.errors import (
    DecryptionError,
    FinancialDataIntegrityError,
    KeyUnavailableError,
)
from utils.app_paths import LEGACY_CBC_PASSWORD, data_dir, migrate_legacy_path
from utils.financial_decimal import decimal_from, fiat

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_LEGACY_DB_PATH = os.path.join(BASE_DIR, "finance.db")
DB_NAME = os.path.join(data_dir(), "finance.db")


SECRET_KEY = LEGACY_CBC_PASSWORD


def migrate_legacy_database_location() -> bool:
    """Var olan bir kurulumdan geçiş: eski BASE_DIR/finance.db'yi (varsa)
    yeni kullanıcı-veri konumuna taşır. main.py'nin başlangıcında,
    initialize_database()'DEN ÖNCE açıkça çağrılır — bu modülün salt
    import edilmesiyle OTOMATİK tetiklenmez, çünkü test suite'i bu modülü
    sürekli import ediyor ve import'un kendisi gerçek kullanıcı verisini
    taşımamalı."""
    return migrate_legacy_path(_LEGACY_DB_PATH, DB_NAME)


DEFAULT_ACCOUNT_ID = 1

NETWORK_LOGOS = {
    "Visa": "assets/visa.png",
    "Mastercard": "assets/mastercard.png",
    "Troy": "assets/troy.png",
}


COMPLETED_TX = "COALESCE(status, 'completed') = 'completed'"
COMPLETED_TX_T = "COALESCE(t.status, 'completed') = 'completed'"

def get_connection():


    directory = os.path.dirname(DB_NAME)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    enable_foreign_keys(conn)
    return conn


def enable_foreign_keys(conn):
    """`PRAGMA foreign_keys=ON` — bağlantı kurulur kurulmaz, DML'den ÖNCE.

    SQLite'ta foreign key zorlaması BAĞLANTI BAŞINA ve VARSAYILAN OLARAK
    KAPALIDIR (3.6.19'da eklenirken geriye dönük uyumluluk için alınmış bir
    karar). Şemada `transactions.account_id REFERENCES accounts(id)` yazıyor
    olması tek başına HİÇBİR ŞEY zorlamıyordu — ölçüldü: var olmayan bir
    hesaba işlem yazmak kabul ediliyor, `PRAGMA foreign_key_check` ise
    ihlali bildiriyordu. Yani şema bir kural olduğunu sanıyor, motor
    uygulamıyordu.

    SIRA ÖNEMLİ: bu PRAGMA bir transaction'ın İÇİNDE sessiz bir NO-OP'tur.
    Burada, `connect`'ten hemen sonra ve herhangi bir `BEGIN`/DML'den önce
    çalışıyor.

    SONUÇ DOĞRULANIYOR: PRAGMA, foreign key desteği olmadan derlenmiş bir
    SQLite'ta hata VERMEDEN hiçbir şey yapmaz. Sessizce korumasız devam
    etmek, korumanın var olduğunu sanarak yazılmış her çağrıyı yanıltır;
    bu yüzden fail-closed.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if not row or not row[0]:
        conn.close()
        raise FinancialDataIntegrityError(
            "sqlite", None, "foreign_keys",
            reason="PRAGMA foreign_keys=ON etkinleştirilemedi.",
        )


@contextmanager
def managed_connection():
    """Bağlantıyı HER ÇIKIŞ YOLUNDA kapatan context manager.

    Bu modüldeki fonksiyonlar eskiden `conn = get_connection()` ... `conn.close()`
    kalıbını try/finally OLMADAN kullanıyordu — yani araya giren herhangi bir
    istisnada `close()` hiç çalışmıyordu. Bu teorik bir risk değildi:
    `adjust_account_balance` hesap bulunamadığında BİLEREK ValueError fırlatır
    (aşağıdaki `cursor.rowcount == 0` koruması) ve onu çağıran
    `process_due_recurring_payment` tam da bu kalıptaydı. Yazma bütünlüğü zaten güvendeydi (commit'e ulaşılmadığı için
    yarım kayıt oluşmaz), sızan şey bağlantı nesnesinin kendisiydi.

    Servis katmanı (services/account_service.py, transaction_service.py vb.)
    bu işi zaten try/finally ile doğru yapıyordu; eksik olan tek katman
    buydu. Context manager tercih edildi ki bundan SONRA eklenecek
    fonksiyonlar da kalıbı yeniden yazmak zorunda kalmadan güvenli olsun.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


ACCOUNT = "account"
SAVINGS_GOAL = "savings_goal"


def record_balance_event(cursor, entity_type, entity_id, delta,
                         resulting_value, source, ref_id=None):
    """balance_events'e tek satır yazar — ÇAĞIRANIN cursor'ıyla, aynı commit'te.

    Kendi bağlantısını AÇMAZ: defter, kaydettiği bakiye değişikliğiyle aynı
    işlemde durmak zorunda. Ayrı bağlantı açsaydı UPDATE geri alındığında
    defterde hayalet bir satır kalırdı ve replay gerçek bakiyeden sapardı.

    delta 0 olan olaylar da yazılır (örn. hedef açılışı): toplamı etkilemezler
    ama defterin varlık geçmişini eksiksiz tutarlar.
    """
    cursor.execute(
        """
        INSERT INTO balance_events
            (ts, entity_type, entity_id, delta, resulting_value, source, ref_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            entity_type,
            int(entity_id),
            float(delta),
            None if resulting_value is None else float(resulting_value),
            source,
            None if ref_id is None else int(ref_id),
        ),
    )


    event_id = cursor.lastrowid
    if entity_type == ACCOUNT:
        from services.asset_service import mark_account_cache_stale
        mark_account_cache_stale()


    return event_id


def current_account_balance(cursor, account_id):
    """Açık cursor üzerinden hesabın güncel bakiyesi (olay sonrası değer için)."""
    cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    return (row["balance"] if row else 0.0) or 0.0


def current_goal_amount(cursor, goal_id):
    """Açık cursor üzerinden hedefin güncel birikimi."""
    cursor.execute("SELECT current_amount FROM savings_goals WHERE id = ?", (goal_id,))
    row = cursor.fetchone()
    return (row["current_amount"] if row else 0.0) or 0.0


def adjust_account_balance(cursor, account_id, transaction_type, amount,
                           ref_id=None, source="transaction"):
    """accounts.balance'ı işlem tutarına göre senkron günceller (Hesaplar Kopuk
    düzeltmesi). Açık bir cursor alır ki çağıran INSERT ile aynı commit'te atomik
    olarak yazılsın — ayrı bir connection açılırsa iki yazım arasında tutarsız bir
    ara durum oluşabilir.

    İŞARET KONVANSİYONU (kredi kartı desteğinin temeli):
    accounts.balance her zaman "bu hesabın net servete KATKISI"dır.
      * Vadesiz (checking): bakiye pozitiftir, gider onu DÜŞÜRÜR.
      * Kredi kartı (credit_card): borç NEGATİF bakiye olarak tutulur. Karttan
        gider işlenince bakiye daha da negatife gider, yani KART BORCU ARTAR;
        karta ödeme yapılınca (income) bakiye 0'a yaklaşır, borç azalır.

    Bu konvansiyonun tek ama kritik faydası: net servet hâlâ düz bir
    SUM(balance) ile doğru çıkar (kart borçları kendiliğinden eksi düşer) ve
    accounts.balance'a dokunan diğer yerler (savings_service, admin sıfırlama,
    CSV içe aktarımı) hiçbir tür ayrımı yapmak zorunda kalmaz. Borcu pozitif bir
    sayı olarak saklasaydık SUM(balance) borcu servete EKLERDİ ve tek bir unutulan
    çağrı noktası sessizce yanlış net servet üretirdi.

    Ekrana pozitif borç ("₺3.500 borcunuz var") göstermek isteyen taraf
    services/account_service.py içindeki türetilmiş `debt` / `available_limit`
    alanlarını kullanır; ham işaretli değeri UI'da göstermez."""
    delta = amount if transaction_type in ("income", "Gelir") else -amount
    cursor.execute(
        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
        (delta, account_id),
    )


    if cursor.rowcount == 0:
        raise ValueError(
            f"Hesap bulunamadı (id={account_id}); işlem bakiyeye yazılamadı. "
            "Önce bir hesap oluşturulmalı."
        )

    record_balance_event(
        cursor, ACCOUNT, account_id, delta,
        current_account_balance(cursor, account_id), source, ref_id,
    )

def insert_debt(debt_name, total_amount, monthly_payment, total_installments, is_auto_pay=0, auto_pay_day=1):
    with managed_connection() as conn:
        cursor = conn.cursor()


        enc_name = encrypt(str(debt_name), SECRET_KEY)
        enc_total = encrypt(str(fiat(total_amount)), SECRET_KEY)
        enc_monthly = encrypt(str(fiat(monthly_payment)), SECRET_KEY)

        cursor.execute("""
            INSERT INTO active_debts (debt_name, total_amount, monthly_payment, total_installments, paid_installments, is_active, is_auto_pay, auto_pay_day)
            VALUES (?, ?, ?, ?, 0, 1, ?, ?)
        """, (enc_name, enc_total, enc_monthly, total_installments, int(is_auto_pay), auto_pay_day))
        conn.commit()

def update_debt_progress(debt_id, extra_installments_paid, is_active=1):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET paid_installments = paid_installments + ?, is_active = ?
            WHERE id = ?
        """, (extra_installments_paid, is_active, debt_id))
        conn.commit()

def update_debt_auto_pay(debt_id, is_auto_pay, auto_pay_day):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET is_auto_pay = ?, auto_pay_day = ?
            WHERE id = ?
        """, (int(is_auto_pay), auto_pay_day, debt_id))
        conn.commit()

def get_active_debts():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_debts WHERE is_active = 1")
        rows = cursor.fetchall()


    debts = []
    for r in rows:
        try:
            dec_name = decrypt(r["debt_name"], SECRET_KEY)
            dec_total = float(decrypt(r["total_amount"], SECRET_KEY))
            dec_monthly = float(decrypt(r["monthly_payment"], SECRET_KEY))
        except (DecryptionError, ValueError, TypeError) as exc:
            raise FinancialDataIntegrityError(
                "active_debts", r["id"], "encrypted_fields", reason=exc
            ) from exc

        debts.append({
            "id": r["id"],
            "debt_name": dec_name,
            "total_amount": dec_total,
            "monthly_payment": dec_monthly,
            "total_installments": r["total_installments"],
            "paid_installments": r["paid_installments"],
            "is_auto_pay": bool(r["is_auto_pay"]) if "is_auto_pay" in r.keys() and r["is_auto_pay"] else False,
            "auto_pay_day": r["auto_pay_day"] if "auto_pay_day" in r.keys() and r["auto_pay_day"] else 1,
            "last_auto_pay_date": r["last_auto_pay_date"] if "last_auto_pay_date" in r.keys() else None
        })
    return debts


def insert_asset(asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date=None):


    if decimal_from(purchase_price) <= 0 or decimal_from(quantity) <= 0:
        raise ValueError("Fiyat ve miktar sıfırdan büyük olmalıdır.")
    from datetime import datetime
    with managed_connection() as conn:
        cursor = conn.cursor()
        enc_purchase_price = encrypt(str(purchase_price), SECRET_KEY)
        enc_quantity       = encrypt(str(quantity),       SECRET_KEY)
        if purchase_date is None:
            purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO active_assets (asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (asset_name, asset_code.upper(), asset_type, enc_purchase_price, enc_quantity, purchase_date))
        conn.commit()


def get_all_assets():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_assets ORDER BY id DESC")
        rows = cursor.fetchall()

    assets = []
    for r in rows:
        try:
            dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
            dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
        except (DecryptionError, ValueError, TypeError) as exc:
            raise FinancialDataIntegrityError(
                "active_assets", r["id"], "purchase_price/quantity",
                reason=exc,
            ) from exc
        assets.append({
            "id":             r["id"],
            "asset_name":     r["asset_name"],
            "asset_code":     r["asset_code"],
            "asset_type":     r["asset_type"],
            "purchase_price": dec_price,
            "quantity":       dec_quantity,
        })
    return assets


def delete_asset(asset_id):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_assets WHERE id = ?", (asset_id,))
        conn.commit()


def get_asset_by_id(asset_id):
    """Returns a single asset row as a dict (decrypted)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_assets WHERE id = ?", (asset_id,))
        r = cursor.fetchone()
    if not r:
        return None
    try:
        dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
        dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
    except (DecryptionError, ValueError, TypeError) as exc:
        raise FinancialDataIntegrityError(
            "active_assets", r["id"], "purchase_price/quantity", reason=exc
        ) from exc
    return {
        "id":             r["id"],
        "asset_name":     r["asset_name"],
        "asset_code":     r["asset_code"],
        "asset_type":     r["asset_type"],
        "purchase_price": dec_price,
        "quantity":       dec_quantity,
        "purchase_date":  r["purchase_date"],
    }


def get_asset_transaction_history(limit=50):
    """
    Returns all investment ledger entries (Varlık Alımı + Varlık Satışı)
    ordered by most recent first, for the 'Varlık Geçmişi' section.
    """
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            -- `id` yalnızca hata kaydı için seçiliyor: aşağıdaki iki
            -- [VERİ BÜTÜNLÜĞÜ] log satırı kaydı kimliğiyle işaretliyor.
            -- Eskiden sorguda YOKTU, dolayısıyla gerçek bir bozuk satırda
            -- hata işleyicisinin KENDİSİ `IndexError` ile çöküyordu; bu
            -- yol hiç çalıştırılmadığı için fark edilmemişti
            -- (tests/test_decrypt_error_contract.py yakaladı).
            SELECT id, type, category, amount, description,
                   strftime('%d/%m/%Y %H:%M', transaction_date) as t_date
            FROM transactions
            WHERE category IN ('Varlık Alımı', 'Varlık Satışı')
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

    result = []
    for r in rows:
        try:
            dec_amount = float(decrypt(str(r["amount"]), SECRET_KEY))
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] transactions id={r['id']} tutar çözülemedi")
            dec_amount = 0.0
        try:
            dec_desc = decrypt(str(r["description"]), SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] transactions id=%s açıklaması çözülemedi",
                r["id"])
            dec_desc = ""
        result.append({
            "type":        r["type"],
            "category":    r["category"],
            "amount":      dec_amount,
            "description": dec_desc,
            "date":        r["t_date"],
        })
    return result


def insert_recurring_payment(
        name, amount, category, frequency, next_due_date, auto_deduct,
        account_id=DEFAULT_ACCOUNT_ID, recurrence_day=None,
        transaction_type="expense"):
    if recurrence_day is None:
        recurrence_day = int(str(next_due_date)[8:10])
    recurrence_day = int(recurrence_day)
    if not 1 <= recurrence_day <= 31:
        raise ValueError("Tekrarlama günü 1 ile 31 arasında olmalıdır.")
    transaction_type = str(transaction_type or "expense").strip().lower()
    if transaction_type not in ("income", "expense"):
        raise ValueError("Tekrarlanan işlem türü income veya expense olmalıdır.")


    try:
        amount_decimal = fiat(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("Tekrarlanan işlem tutarı geçerli bir sayı olmalıdır.") from exc
    if amount_decimal <= 0:
        raise ValueError("Tekrarlanan işlem tutarı 0'dan büyük olmalıdır.")
    with managed_connection() as conn:
        cursor = conn.cursor()
        enc_name = encrypt(str(name), SECRET_KEY)
        enc_amount = encrypt(str(amount_decimal), SECRET_KEY)
        cursor.execute("""
            INSERT INTO recurring_payments
                (name, amount, category, frequency, next_due_date, recurrence_day,
                 auto_deduct, is_active, account_id, transaction_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            enc_name, enc_amount, category, frequency, next_due_date,
            recurrence_day, int(bool(auto_deduct)), account_id,
            transaction_type,
        ))
        conn.commit()


def has_active_recurring_payment(name):
    """Aktif tekrarlanan ödemeler arasında aynı isimde (büyük/küçük harf
    duyarsız) bir kayıt olup olmadığını kontrol eder. İsimler şifreli
    tutulduğundan SQL WHERE ile aranamaz; aktif kayıtlar çözülüp Python'da
    karşılaştırılır (abonelik duplikasyonunu engellemek için)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM recurring_payments WHERE is_active = 1")
        rows = cursor.fetchall()

    target = str(name).strip().lower()
    for r in rows:
        try:
            existing_name = decrypt(r["name"], SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):


            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] recurring_payments adı çözülemedi, "
                "isim çakışma kontrolünde atlandı")
            continue
        if existing_name.strip().lower() == target:
            return True
    return False


def get_active_recurring_payments():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recurring_payments WHERE is_active = 1 ORDER BY next_due_date ASC")
        rows = cursor.fetchall()

    payments = []
    for r in rows:
        try:
            dec_name = decrypt(r["name"], SECRET_KEY)


            amount_decimal = decimal_from(decrypt(r["amount"], SECRET_KEY))


            if amount_decimal <= 0:
                raise ValueError("recurring amount must be positive")
            dec_amount = float(amount_decimal)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] recurring_payments id={r['id']} okunamadı")
            dec_name = "Bilinmeyen Ödeme"
            dec_amount = 0.0
            amount_is_valid = False
        else:
            amount_is_valid = True
        payments.append({
            "id":            r["id"],
            "name":          dec_name,
            "amount":        dec_amount,


            "amount_is_valid": amount_is_valid,
            "category":      r["category"],
            "frequency":     r["frequency"],
            "next_due_date": r["next_due_date"],
            "recurrence_day": r["recurrence_day"],
            "auto_deduct":   bool(r["auto_deduct"]),
            "account_id":    r["account_id"],
            "transaction_type": (
                r["transaction_type"]
                if "transaction_type" in r.keys()
                else "expense"
            ),
        })
    return payments


def deactivate_recurring_payment(payment_id):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE recurring_payments SET is_active = 0 WHERE id = ?", (payment_id,))
        conn.commit()


def _advance_due_date(date_str, frequency):
    """Vadeyi desteklenen sıklık kadar ileri alır.

    Haftalık periyotlar sabit gün, aylık periyotlar takvim ayı üzerinden
    ilerler. Böylece 31 Ocak + üç ay 30 Nisan olur; bilinmeyen bir değer de
    sessizce aylık kabul edilmek yerine açıkça reddedilir.
    """
    from datetime import date, timedelta
    import calendar

    d = date.fromisoformat(date_str)
    if frequency == "weekly":
        return (d + timedelta(days=7)).isoformat()
    if frequency == "biweekly":
        return (d + timedelta(days=14)).isoformat()
    if frequency == "yearly":
        try:
            return d.replace(year=d.year + 1).isoformat()
        except ValueError:
            return d.replace(year=d.year + 1, day=28).isoformat()
    if frequency not in ("monthly", "quarterly"):
        raise ValueError(f"Desteklenmeyen tekrarlama sıklığı: {frequency}")

    months = 3 if frequency == "quarterly" else 1
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day).isoformat()


def process_due_recurring_payment(payment):
    """Vadesi gelen tekrarlanan gelir/gideri işler ve vadeyi ilerletir."""
    from datetime import datetime


    from services.recurring_service import next_due_for_recurrence
    from utils.financial_decimal import fiat


    amount_decimal = fiat(payment["amount"])
    if amount_decimal <= 0:
        raise ValueError("Tekrarlanan işlem tutarı 0'dan büyük olmalıdır.")
    amount = float(amount_decimal)
    new_due = next_due_for_recurrence(
        payment["next_due_date"],
        payment["frequency"],
        payment.get("recurrence_day")
        or int(str(payment["next_due_date"])[8:10]),
    )
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        # Stale UI objects intentionally retain the old due date.  The marker
        # therefore keys the financial generation, not the mutable next due.
        cursor.execute(
            "INSERT OR IGNORE INTO recurring_operation_markers "
            "(recurring_payment_id, due_date, operation_type) VALUES (?, ?, 'charge')",
            (payment["id"], payment["next_due_date"]),
        )
        if cursor.rowcount == 0:
            return False
        transaction_type = str(
            payment.get("transaction_type") or "expense"
        ).strip().lower()
        if transaction_type not in ("income", "expense"):
            raise ValueError("Geçersiz tekrarlanan işlem türü.")
        from services.account_service import AccountService


        AccountService.assert_spending_allowed(
            cursor, payment["account_id"], amount, transaction_type,
        )
        enc_amount = encrypt(str(amount), SECRET_KEY)
        enc_desc = encrypt(f"{payment['name']} (Otomatik)", SECRET_KEY)
        tx_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        cursor.execute("""
            INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payment["account_id"], enc_amount, transaction_type,
            payment["category"], enc_desc, tx_date,
        ))
        transaction_id = cursor.lastrowid
        adjust_account_balance(
            cursor, payment["account_id"], transaction_type,
            amount, ref_id=transaction_id,
            source="recurring_payment",
        )

        cursor.execute("UPDATE recurring_payments SET next_due_date = ? WHERE id = ?", (new_due, payment["id"]))
        cursor.execute(
            "UPDATE recurring_operation_markers SET transaction_id=? "
            "WHERE recurring_payment_id=? AND due_date=? AND operation_type='charge'",
            (transaction_id, payment["id"], payment["next_due_date"]),
        )
        conn.commit()
    return True

def update_debt_last_auto_pay(debt_id, current_month_str):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET last_auto_pay_date = ?
            WHERE id = ?
        """, (current_month_str, debt_id))
        conn.commit()
