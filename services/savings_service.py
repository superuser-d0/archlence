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

from database.db import get_connection, DEFAULT_ACCOUNT_ID, SECRET_KEY
from utils.crypto import encrypt, decrypt

STATUS_ACTIVE = "aktif"
STATUS_COMPLETED = "tamamlandi"


class SavingsService:

    @staticmethod
    def create_goal(goal_name, target_amount, target_date=None):
        """Yeni birikim hedefi açar; hedefin id'sini döndürür."""
        target_amount = float(target_amount)
        if target_amount <= 0:
            raise ValueError("Hedef tutar 0'dan büyük olmalıdır")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savings_goals (goal_name, target_amount, current_amount, target_date, status)
                VALUES (?, ?, 0, ?, ?)
            """, (encrypt(str(goal_name), SECRET_KEY), target_amount, target_date, STATUS_ACTIVE))
            conn.commit()
            return cursor.lastrowid
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
            except Exception:
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

        Yetersiz bakiye koruması SQL'in kendisinde: koşullu UPDATE hiç satır
        etkilemezse para yoktur, iki yazımdan hiçbiri kalıcı olmaz. Python'da
        önce SELECT ile bakıp sonra yazmak iki adım arasında başka bir yazıma
        açık olurdu. Güncel hedef durumunu (dict) döndürür.
        """
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Aktarılacak tutar 0'dan büyük olmalıdır")

        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?",
                (amount, account_id, amount),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise ValueError("Yetersiz bakiye: ana hesapta bu tutar yok")

            cursor.execute(
                f"UPDATE savings_goals SET current_amount = current_amount + ? "
                f"WHERE id = ? AND status != '{STATUS_COMPLETED}'",
                (amount, goal_id),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise ValueError("Hedef bulunamadı ya da zaten tamamlanmış")

            # Hedefe ulaşıldıysa durumu aynı commit içinde işaretle
            cursor.execute(
                f"UPDATE savings_goals SET status = '{STATUS_COMPLETED}' "
                f"WHERE id = ? AND current_amount >= target_amount",
                (goal_id,),
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

            cursor.execute(
                "UPDATE savings_goals SET current_amount = current_amount - ? "
                "WHERE id = ? AND current_amount >= ?",
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
        except Exception:
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
    def delete_goal(goal_id, account_id=DEFAULT_ACCOUNT_ID):
        """Hedefi siler; içinde birikim varsa tamamı ana hesaba iade edilir
        (silme para buharlaştırmamalı). Aynı atomik desenle tek commit."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_amount FROM savings_goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if not row:
                return False
            refund = row["current_amount"] or 0.0
            if refund > 0:
                cursor.execute(
                    "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                    (refund, account_id),
                )
            cursor.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
