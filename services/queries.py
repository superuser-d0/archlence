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
from database.db import ACCOUNT, managed_connection


class CategoryService:

    @staticmethod
    def get_categories(category_type=None):
        """Türe (income/expense) göre kategorileri getirir; tür verilmezse hepsini."""
        with managed_connection() as conn:
            if category_type:
                rows = conn.execute(
                    "SELECT id, name FROM categories WHERE type = ?",
                    (category_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name FROM categories"
                ).fetchall()
        return rows


class TransactionHistoryService:

    @staticmethod
    def get_last_transactions(limit=10):
        with managed_connection() as conn:
            rows = conn.execute("""
                SELECT *
                FROM transactions
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return rows


class DashboardService:

    @staticmethod
    def get_total_balance():
        with managed_connection() as conn:
            result = conn.execute(
                "SELECT SUM(balance) as total FROM accounts"
            ).fetchone()

        return round(result["total"] or 0, 2)

    @staticmethod
    def get_opening_baseline():
        """Hesapların açılış bakiyelerinin (işaretli) toplamı.

        NEDEN: Ana sayfadaki "Cüzdanım" toplamı işlem defterinden
        (gelir − gider) besleniyor; oysa bir hesabın açılış bakiyesi doğrudan
        accounts.balance'a yazılıp balance_events'e 'account_opened' olarak
        düşülüyor, transactions'a HİÇ girmiyor. Sonuç: açılış bakiyesi
        "Kartlarım"da görünüp "Cüzdanım"da görünmüyordu (senkronizasyon hatası).

        Bu toplam eksik kalan açılış tabanını verir. Açılış bakiyesini sahte bir
        "gelir" işlemi olarak yazmak yerine ayrı tutulur; böylece tasarruf oranı,
        50-30-20 sağlık skoru ve ODE günlük gelir girdisi gibi saf nakit-akışı
        analizleri açılış bakiyesiyle şişmez.

        Her hesabın tam olarak BİR 'account_opened' olayı vardır (create_account
        yazar; açılış çizgisi olmayan eski hesaplar için init_db idempotent
        olarak tamamlar), bu yüzden delta toplamı açılış bakiyelerinin işaretli
        toplamına eşittir. Kredi kartı borcu negatif işaretli girdiğinden bu
        toplam otomatik olarak borç kadar azalır.
        """
        with managed_connection() as conn:
            result = conn.execute(
                "SELECT COALESCE(SUM(delta), 0) AS total FROM balance_events"
                " WHERE entity_type = ? AND source = 'account_opened'",
                (ACCOUNT,),
            ).fetchone()
        return round(result["total"] or 0.0, 2)

    @staticmethod
    def get_accounts():
        with managed_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts"
            ).fetchall()

        return rows

    @staticmethod
    def refresh_data():
        return {
            "total": DashboardService.get_total_balance(),
            "accounts": DashboardService.get_accounts()
        }
