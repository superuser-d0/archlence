"""Birikim Hedefleri (Savings Goals) servisi.

Yeni arayüzdeki "Birikimler" modülünün DB katmanı. Hedefe para eklemek,
parayı ana vadesiz hesaptan İZOLE etmek demektir: accounts.balance azalır,
hedefin current_amount'u aynı SQL işlemi içinde artar — ikisi tek commit'te
atomiktir, yarıda kalırsa rollback ile ikisi de geri alınır. Para çekme
bunun tersidir. Bu bir gelir/gider DEĞİLDİR; transactions tablosuna kayıt
yazılmaz (grafiklerde harcama olarak görünmemeli), yalnızca bakiye izole edilir.

goal_name AES şifreli saklanır; tutarlar düz REAL'dir (bkz. init_db.py'deki
şema notu). status: 'aktif' → hedefe ulaşınca 'tamamlandi', çekimle hedefin
altına inerse tekrar 'aktif'.
"""

import uuid
from datetime import date

from database.db import (
    ACCOUNT,
    DEFAULT_ACCOUNT_ID,
    SAVINGS_GOAL,
    SECRET_KEY,
    current_account_balance,
    current_goal_amount,
    get_connection,
    record_balance_event,
)
from utils.crypto import encrypt, decrypt
from utils.errors import DecryptionError, KeyUnavailableError
from utils.financial_decimal import fiat

STATUS_ACTIVE = "aktif"
STATUS_COMPLETED = "tamamlandi"


IDENTITY_MISMATCH_MESSAGE = (
    "Bu hedef artık mevcut değil ya da değişmiş görünüyor; işlem güvenlik "
    "için durduruldu ve hiçbir para hareket etmedi. Lütfen ekranı yenileyip "
    "tekrar deneyin."
)


def _assert_identity(cursor, goal_id, goal_uid):
    """Sayısal id ile KALICI kimliğin aynı satırı gösterdiğini kanıtlar.

    FAIL-CLOSED ve para hareket etmeden ÖNCE çalışır. Sayısal `id` restore
    sonrasında yeniden kullanılabiliyor (bkz. database/init_db.py ve
    tests/test_savings_identity_reuse_regression.py): bir kullanıcı eyleminin
    HANGİ hedefi kastettiğini tek başına kanıtlayamaz. `goal_uid` verilmişse
    ikisi birlikte tutmak zorundadır.

    `goal_uid` None ise doğrulama yapılmaz — bu, kimliği bilmeyen eski
    çağıranlar (servis testleri, bakım betikleri) için bilinçli bir kapı.
    Arayüz HER ZAMAN UID geçirir; kart kaydında UID yoksa `SavingsMixin`
    işlemi zaten servise hiç göndermez.
    """
    if goal_uid is None:
        return
    cursor.execute(
        "SELECT 1 FROM savings_goals WHERE id = ? AND goal_uid = ?",
        (goal_id, str(goal_uid)),
    )
    if cursor.fetchone() is None:
        from utils.logging_config import get_logger
        get_logger().warning(
            "[KİMLİK] savings_goals id=%s ile verilen goal_uid eşleşmiyor; "
            "işlem reddedildi", goal_id,
        )
        raise ValueError(IDENTITY_MISMATCH_MESSAGE)


class SavingsService:

    @staticmethod
    def create_goal(goal_name, target_amount, target_date=None, current_amount=0.0,
                    color=None, auto_deposit=False, created_at=None,
                    goal_uid=None):
        """Yeni birikim hedefi açar; hedefin id'sini döndürür.

        `goal_uid` KALICI kimliktir ve burada üretilir — sayısal `id` restore
        sonrasında yeniden kullanılabildiği için (bkz. init_db.py'deki not)
        kimlik olarak ona güvenilemez. Çağıran açıkça bir UID verebilir;
        yalnız göç motoru bunu kullanır ve orada da değer `uuid4()`'tür.
        """
        target_amount = float(fiat(target_amount))
        current_amount = float(fiat(current_amount))
        if target_amount <= 0:
            raise ValueError("Hedef tutar 0'dan büyük olmalıdır")
        if current_amount < 0:
            raise ValueError("Birikim tutarı negatif olamaz")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savings_goals (goal_name, target_amount, current_amount,
                                           target_date, status, goal_uid, color,
                                           auto_deposit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (encrypt(str(goal_name), SECRET_KEY), target_amount,
                  current_amount, target_date,
                  STATUS_COMPLETED
                  if fiat(current_amount) >= fiat(target_amount)
                  else STATUS_ACTIVE,
                  str(goal_uid or uuid.uuid4()), color,
                  1 if auto_deposit else 0,
                  created_at or date.today().isoformat()))
            goal_id = cursor.lastrowid


            record_balance_event(cursor, SAVINGS_GOAL, goal_id, current_amount, current_amount,
                                 "savings_goal_created")
            conn.commit()
            return goal_id
        finally:
            conn.close()

    @staticmethod
    def get_goals(only_active=False):
        """Hedefleri çözülmüş isimlerle döndürür (dict listesi)."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM savings_goals"
            if only_active:
                query += f" WHERE status = '{STATUS_ACTIVE}'"
            cursor.execute(query + " ORDER BY id")
            rows = cursor.fetchall()
        finally:
            conn.close()

        goals = []
        for r in rows:
            try:
                name = decrypt(r["goal_name"], SECRET_KEY)
            except KeyUnavailableError:


                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(
                    "[VERİ BÜTÜNLÜĞÜ] savings_goals id=%s adı çözülemedi",
                    r["id"])
                name = "Bilinmeyen Hedef"
            goals.append(SavingsService._goal_dict(r, name))
        return goals

    @staticmethod
    def _goal_dict(row, name):
        """Satırı servis sözleşmesindeki tek sözlük şekline çevirir.

        `get_goals` ve `_get_goal_row` eskiden bu sözlüğü AYRI AYRI kuruyordu;
        yeni alanlar eklendiğinde birini güncelleyip diğerini unutmak, hedef
        kartının bir işlemden sonra rengini/tarihini kaybetmesi demekti.
        """
        return {
            "id": row["id"],
            "goal_uid": row["goal_uid"],
            "goal_name": name,
            "target_amount": row["target_amount"],
            "current_amount": row["current_amount"],
            "target_date": row["target_date"],
            "status": row["status"],
            "color": row["color"],
            "auto_deposit": bool(row["auto_deposit"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def deposit_to_goal(goal_id, amount, account_id=DEFAULT_ACCOUNT_ID,
                       goal_uid=None):
        """Ana hesaptan hedefe para aktarır (atomik izolasyon).

        Yetersiz bakiye koruması iptal edildi: hesap eksiye düşebilir.
        Güncel hedef durumunu (dict) döndürür.

        `goal_uid` verilirse kimlik doğrulaması PARA HAREKET ETMEDEN ÖNCE
        yapılır ve eşleşmezse işlem reddedilir.
        """
        amount = float(fiat(amount))
        if amount <= 0:
            raise ValueError("Aktarılacak tutar 0'dan büyük olmalıdır")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            _assert_identity(cursor, goal_id, goal_uid)

            cursor.execute(
                "UPDATE accounts SET balance = balance - ? WHERE id = ?",
                (amount, account_id),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise ValueError("Hesap güncellenemedi (hesap bulunamadı).")

            cursor.execute(
                f"UPDATE savings_goals SET current_amount = current_amount + ? "
                f"WHERE id = ? AND status != '{STATUS_COMPLETED}'",
                (amount, goal_id),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise ValueError("Hedef bulunamadı ya da zaten tamamlanmış")


            cursor.execute(
                f"UPDATE savings_goals SET status = '{STATUS_COMPLETED}' "
                f"WHERE id = ? AND ROUND(current_amount, 2) "
                f">= ROUND(target_amount, 2)",
                (goal_id,),
            )


            record_balance_event(
                cursor, ACCOUNT, account_id, -amount,
                current_account_balance(cursor, account_id),
                "savings_deposit", goal_id,
            )
            record_balance_event(
                cursor, SAVINGS_GOAL, goal_id, amount,
                current_goal_amount(cursor, goal_id),
                "savings_deposit", account_id,
            )

            conn.commit()
            return SavingsService._get_goal_row(cursor, goal_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def withdraw_from_goal(goal_id, amount, account_id=DEFAULT_ACCOUNT_ID,
                           goal_uid=None):
        """Hedeften ana hesaba para iade eder (deposit'in tersi, aynı atomik desen).

        `goal_uid` sözleşmesi `deposit_to_goal` ile aynıdır.
        """
        amount = float(fiat(amount))
        if amount <= 0:
            raise ValueError("Çekilecek tutar 0'dan büyük olmalıdır")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            _assert_identity(cursor, goal_id, goal_uid)


            cursor.execute(
                "UPDATE savings_goals SET current_amount = current_amount - ? "
                "WHERE id = ? AND ROUND(current_amount, 2) >= ROUND(?, 2)",
                (amount, goal_id, amount),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise ValueError("Hedefte bu kadar birikim yok")

            cursor.execute(
                "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                (amount, account_id),
            )


            cursor.execute(
                f"UPDATE savings_goals SET status = '{STATUS_ACTIVE}' "
                f"WHERE id = ? AND ROUND(current_amount, 2) "
                f"< ROUND(target_amount, 2)",
                (goal_id,),
            )


            record_balance_event(
                cursor, SAVINGS_GOAL, goal_id, -amount,
                current_goal_amount(cursor, goal_id),
                "savings_withdraw", account_id,
            )
            record_balance_event(
                cursor, ACCOUNT, account_id, amount,
                current_account_balance(cursor, account_id),
                "savings_withdraw", goal_id,
            )

            conn.commit()
            return SavingsService._get_goal_row(cursor, goal_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _get_goal_row(cursor, goal_id):
        """Açık cursor üzerinden tek hedefi çözülmüş isimle okur."""
        cursor.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,))
        r = cursor.fetchone()
        if not r:
            return None
        try:
            name = decrypt(r["goal_name"], SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] savings_goals id=%s adı çözülemedi", goal_id)
            name = "Bilinmeyen Hedef"
        return SavingsService._goal_dict(r, name)

    @staticmethod
    def delete_goal(goal_id, account_id=DEFAULT_ACCOUNT_ID, refund=True,
                    goal_uid=None):
        """Hedefi atomik olarak siler; istenirse bakiyeyi vadesiz hesaba aktarır.

        `goal_uid` sözleşmesi `deposit_to_goal` ile aynıdır — silme, yanlış
        hedefte en pahalı işlem olduğu için doğrulama burada da yapılır.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            _assert_identity(cursor, goal_id, goal_uid)
            cursor.execute("SELECT current_amount FROM savings_goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if not row:
                return False
            refund_amount = float(row["current_amount"] or 0.0)
            if refund and refund_amount > 0:
                if account_id is None:
                    raise ValueError("Bakiyenin aktarılacağı hesap seçilmelidir")
                cursor.execute(
                    """UPDATE accounts SET balance = balance + ?
                       WHERE id = ? AND account_type = 'checking'""",
                    (refund_amount, account_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Seçilen vadesiz hesap bulunamadı")

                record_balance_event(
                    cursor, ACCOUNT, account_id, refund_amount,
                    current_account_balance(cursor, account_id),
                    "savings_goal_deleted", goal_id,
                )


            record_balance_event(
                cursor, SAVINGS_GOAL, goal_id, -refund_amount, 0.0,
                "savings_goal_deleted" if refund else "savings_goal_discarded",
                account_id,
            )
            cursor.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
