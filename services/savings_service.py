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


class SavingsService:

    @staticmethod
    def create_goal(goal_name, target_amount, target_date=None, current_amount=0.0):
        """Yeni birikim hedefi açar; hedefin id'sini döndürür."""
        target_amount = float(target_amount)
        current_amount = float(current_amount)
        if target_amount <= 0:
            raise ValueError("Hedef tutar 0'dan büyük olmalıdır")
        if current_amount < 0:
            raise ValueError("Birikim tutarı negatif olamaz")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savings_goals (goal_name, target_amount, current_amount, target_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (encrypt(str(goal_name), SECRET_KEY), target_amount,
                  current_amount, target_date,
                  STATUS_COMPLETED
                  if fiat(current_amount) >= fiat(target_amount)
                  else STATUS_ACTIVE))
            goal_id = cursor.lastrowid
            # [Faz 2 · defter] Hedef 0 birikimle açılır: delta 0, toplamı
            # etkilemez ama defterde hedefin doğuşu görünür.
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
                # Anahtar yoksa TÜM hedefler etkilenir; satır bazında yutmak
                # toplam arızayı "hepsi Bilinmeyen Hedef" diye normal veri
                # gibi gösterirdi.
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(
                    "[VERİ BÜTÜNLÜĞÜ] savings_goals id=%s adı çözülemedi",
                    r["id"])
                name = "Bilinmeyen Hedef"
            goals.append({
                "id": r["id"],
                "goal_name": name,
                "target_amount": r["target_amount"],
                "current_amount": r["current_amount"],
                "target_date": r["target_date"],
                "status": r["status"],
            })
        return goals

    @staticmethod
    def deposit_to_goal(goal_id, amount, account_id=DEFAULT_ACCOUNT_ID):
        """Ana hesaptan hedefe para aktarır (atomik izolasyon).

        Yetersiz bakiye koruması iptal edildi: hesap eksiye düşebilir.
        Güncel hedef durumunu (dict) döndürür.
        """
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Aktarılacak tutar 0'dan büyük olmalıdır")

        conn = get_connection()
        try:
            cursor = conn.cursor()

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

            # Hedefe ulaşıldıysa durumu aynı commit içinde işaretle.
            #
            # ROUND(...,2) ZORUNLU: `current_amount` REAL bir sütun ve
            # `current_amount + ?` ile birikiyor, yani ikili kayan nokta
            # artığı taşıyabiliyor. 3000 x 0,10 TL yatırma 300,00 yerine
            # 299.9999999999997 üretir — ekranda "300,00 TL" yazarken hedef
            # tamamlanmamış sayılırdı. Para kuruştan ince değildir; karar da
            # kuruş hassasiyetinde verilmeli.
            cursor.execute(
                f"UPDATE savings_goals SET status = '{STATUS_COMPLETED}' "
                f"WHERE id = ? AND ROUND(current_amount, 2) "
                f">= ROUND(target_amount, 2)",
                (goal_id,),
            )

            # [Faz 2 · defter 2/6] Para ana hesaptan çıkıp hedefe girdi:
            # iki ayrı varlık değiştiği için iki olay, ikisi de bu commit'te.
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
    def withdraw_from_goal(goal_id, amount, account_id=DEFAULT_ACCOUNT_ID):
        """Hedeften ana hesaba para iade eder (deposit'in tersi, aynı atomik desen)."""
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Çekilecek tutar 0'dan büyük olmalıdır")

        conn = get_connection()
        try:
            cursor = conn.cursor()

            # ROUND(...,2): bu koruma olmadan uygulama, EKRANDA GÖSTERDİĞİ
            # parayı kullanıcıya vermiyordu. 3000 x 0,10 TL yatıran birinin
            # birikimi REAL sütunda 299.9999999999997 durur; ekranda
            # "300,00 TL" yazar; 300,00 TL çekmek isteyince `current_amount
            # >= ?` sağlanmaz ve "Hedefte bu kadar birikim yok" hatası alır.
            # Kendi parasına erişemez.
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

            # Çekim hedefi tamamlanmışlıktan geri düşürdüyse durumu düzelt
            cursor.execute(
                f"UPDATE savings_goals SET status = '{STATUS_ACTIVE}' "
                f"WHERE id = ? AND current_amount < target_amount",
                (goal_id,),
            )

            # [Faz 2 · defter 3/6] deposit'in tersi: hedeften çıktı, hesaba girdi.
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
        return {
            "id": r["id"],
            "goal_name": name,
            "target_amount": r["target_amount"],
            "current_amount": r["current_amount"],
            "target_date": r["target_date"],
            "status": r["status"],
        }

    @staticmethod
    def delete_goal(goal_id, account_id=DEFAULT_ACCOUNT_ID, refund=True):
        """Hedefi atomik olarak siler; istenirse bakiyeyi vadesiz hesaba aktarır."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
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
                # [Faz 2 · defter 4/6] İade hesaba girdi.
                record_balance_event(
                    cursor, ACCOUNT, account_id, refund_amount,
                    current_account_balance(cursor, account_id),
                    "savings_goal_deleted", goal_id,
                )
            # Hedef siliniyor: birikimi 0'a düşen bir olayla kapat ki replay
            # hedefin bakiyesini sonsuza kadar taşımasın.
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
