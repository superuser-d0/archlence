"""Cüzdan (ana sayfa toplamı) ↔ Kartlarım (hesap bakiyeleri) senkronizasyonu.

HATA (Aşama 2, madde 1.1): Bir hesap açılış bakiyesiyle eklendiğinde tutar
"Kartlarım"da (accounts.balance) görünüyor ama ana sayfadaki "Cüzdanım"
toplamında görünmüyordu. Ana sayfa toplamı yalnızca işlem defterinden
(gelir − gider) besleniyor; açılış bakiyesi ise transactions'a değil
accounts.balance + balance_events('account_opened')'e yazılıyordu.

Düzeltme: DashboardService.get_opening_baseline() açılış tabanını ayrı bir
büyüklük olarak döndürür ve ana sayfa toplamına eklenir. Böylece hesaplar +
işlemler senaryosunda ana sayfa toplamı, gerçek hesap bakiyeleri toplamına
(SUM(accounts.balance)) birebir eşitlenir — analizleri (tasarruf oranı, sağlık
skoru) açılış bakiyesini sahte gelir sayarak kirletmeden.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class WalletSyncTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _transaction_cashflow(self):
        """Ana sayfanın kullandığı ile aynı: tamamlanmış işlemlerin gelir−gider'i."""
        from database.db import COMPLETED_TX, get_connection, SECRET_KEY
        from utils.crypto import decrypt

        conn = get_connection()
        try:
            rows = conn.execute(
                f"SELECT amount, type FROM transactions WHERE {COMPLETED_TX}"
            ).fetchall()
        finally:
            conn.close()
        total = 0.0
        for amount, t_type in rows:
            try:
                value = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                value = 0.0
            if t_type in ("income", "Gelir"):
                total += value
            elif t_type in ("expense", "Gider"):
                total -= value
        return round(total, 2)

    def test_initial_balance_appears_in_opening_baseline(self):
        """Asıl hata: açılış bakiyesi cüzdana yansımalı (defterde işlem yokken)."""
        from services.account_service import AccountService
        from services.queries import DashboardService

        AccountService.create_account(
            "Nakit Cüzdanım", "checking", initial_balance=5000
        )

        self.assertEqual(self._transaction_cashflow(), 0.0)
        self.assertEqual(DashboardService.get_opening_baseline(), 5000.0)

        home_total = self._transaction_cashflow() + DashboardService.get_opening_baseline()
        self.assertEqual(home_total, DashboardService.get_total_balance())

    def test_credit_card_debt_reduces_baseline(self):
        """Kredi kartı açılış borcu işaretli girer; taban borç kadar azalır."""
        from services.account_service import AccountService
        from services.queries import DashboardService

        AccountService.create_account(
            "Kart", "credit_card", initial_balance=1000, credit_limit=5000
        )
        self.assertEqual(DashboardService.get_opening_baseline(), -1000.0)

    def test_home_total_matches_net_worth_after_transactions(self):
        """Hesap + işlem senaryosunda ana sayfa toplamı = net servet."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService
        from services.queries import DashboardService

        account_id = AccountService.create_account(
            "Nakit", "checking", initial_balance=5000
        )
        TransactionService.add_transaction(
            account_id=account_id, amount=1000, transaction_type="income",
            category="Maaş", description="maaş",
        )
        TransactionService.add_transaction(
            account_id=account_id, amount=300, transaction_type="expense",
            category="Market", description="market",
        )

        home_total = self._transaction_cashflow() + DashboardService.get_opening_baseline()
        self.assertEqual(home_total, 5700.0)
        self.assertEqual(home_total, DashboardService.get_total_balance())
        self.assertEqual(home_total, AccountService.get_net_worth()["net"])

    def test_deleting_card_removes_its_baseline(self):
        """Kart silinince açılış tabanı da düşmeli (yetim taban kalmamalı).

        Silme yolu balance_events'i de temizlediğinden, sentetik bir açılış
        işlemi yerine defter tabanını kullanmak silme sonrası çift-sayım
        bırakmaz — bu testin koruduğu değişmez budur.
        """
        from services.account_service import AccountService
        from services.queries import DashboardService

        card_id = AccountService.create_account(
            "Geçici Kart", "credit_card", initial_balance=1000, credit_limit=5000
        )
        self.assertEqual(DashboardService.get_opening_baseline(), -1000.0)
        AccountService.delete_credit_card(card_id)
        self.assertEqual(DashboardService.get_opening_baseline(), 0.0)


if __name__ == "__main__":
    unittest.main()
