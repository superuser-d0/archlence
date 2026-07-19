"""Küçük, salt-okunur sorgu servisleri.

Tek başına dosya olamayacak kadar küçük üç servis burada toplandı:
CategoryService (eski services/category_service.py), TransactionHistoryService
(eski services/transaction_history_service.py) ve DashboardService (eski
screens/dashboard.py — ekran değil, yanlış klasörde duran bir servisti).
Eski modül yollarındaki shim dosyaları, tüm import'lar buraya yönlendirildikten
sonra kaldırıldı.

Not: Bu servisler amount/description kolonlarını çözmeden (şifreli haliyle)
döndürür; şifre çözme çağıran tarafın sorumluluğundadır (bkz. utils/crypto.py).
"""
from database.db import get_connection


class CategoryService:

    @staticmethod
    def get_categories(category_type=None):
        """Türe (income/expense) göre kategorileri getirir; tür verilmezse hepsini."""
        conn = get_connection()

        if category_type:
            rows = conn.execute(
                "SELECT id, name FROM categories WHERE type = ?",
                (category_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name FROM categories"
            ).fetchall()

        conn.close()
        return rows


class TransactionHistoryService:

    @staticmethod
    def get_last_transactions(limit=10):
        conn = get_connection()

        rows = conn.execute("""
            SELECT *
            FROM transactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        conn.close()

        return rows


class DashboardService:

    @staticmethod
    def get_total_balance():
        conn = get_connection()

        result = conn.execute(
            "SELECT SUM(balance) as total FROM accounts"
        ).fetchone()

        conn.close()

        return round(result["total"] or 0, 2)

    @staticmethod
    def get_accounts():
        conn = get_connection()

        rows = conn.execute(
            "SELECT * FROM accounts"
        ).fetchall()

        conn.close()

        return rows

    @staticmethod
    def refresh_data():
        return {
            "total": DashboardService.get_total_balance(),
            "accounts": DashboardService.get_accounts()
        }
