import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_connection, DEFAULT_ACCOUNT_ID
from services.savings_service import SavingsService, STATUS_ACTIVE, STATUS_COMPLETED


def _get_balance():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM accounts WHERE id = ?", (DEFAULT_ACCOUNT_ID,))
        return cur.fetchone()["balance"]
    finally:
        conn.close()


def _set_balance(amount):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ?",
            (float(amount), DEFAULT_ACCOUNT_ID),
        )
        conn.commit()
    finally:
        conn.close()


class SavingsServiceTest(unittest.TestCase):
    """İzole bir geçici veritabanında çalışır — gerçek finance.db'ye DOKUNMAZ.

    DÜZELTME: Eskiden gerçek finance.db üzerinde çalışıyordu ve
    DEFAULT_ACCOUNT_ID'nin (=1) zaten bir bakiyesi olduğunu varsayıyordu.
    Bu, geliştiricinin yerel makinesinde hep işe yarıyordu (aylardır
    biriken gerçek hesap verisi vardı) ama iki gerçek sorun taşıyordu:
    (1) taze bir kurulumda/CI checkout'unda `accounts` tablosu BOŞTUR —
    varsayılan hesap seed'i bilerek kaldırıldı ("taze kurulum kullanıcıya
    ait olmayan bakiye üretmez" sözleşmesi, bkz. OrphanTransactionGuardTest)
    — bu yüzden `_get_balance()` `None` dönüyor ve `None["balance"]`
    `TypeError` fırlatıyordu (CI'da Faz 0 test job'ının ilk çalışmasında
    yakalandı); (2) test her koşuda GERÇEK kullanıcının bakiyesini 10.000'e
    set edip sonra geri yüklüyordu — tearDown'a hiç ulaşmadan bir hata
    olsaydı gerçek bakiye test değerinde takılı kalırdı.

    SavingsService.deposit_to_goal/withdraw_from_goal/delete_goal hepsi
    `account_id=DEFAULT_ACCOUNT_ID` varsayılanını kullanıyor; testler bunu
    değiştirmeden çağırdığından, izole DB'de İLK oluşturulan hesabın id'si
    (autoincrement ile 1) DEFAULT_ACCOUNT_ID'yle eşleşir — böylece hiçbir
    çağrı sitesini account_id geçirecek şekilde değiştirmeye gerek kalmadı.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        initialize_database()

        from services.account_service import AccountService
        AccountService.create_account(
            "Test Hesabı", "checking", initial_balance=0.0
        )

        _set_balance(10000.0)
        self.balance_before = _get_balance()
        self.goal_id = SavingsService.create_goal(
            "Test Yaz Tatili (Bali)", 50000.0, "2026-08-01"
        )

    def tearDown(self):
        try:
            SavingsService.delete_goal(self.goal_id)
            self.assertAlmostEqual(
                _get_balance(), self.balance_before, places=2,
                msg="Hedef temizliği sonrası test bakiyesi başlangıca dönmedi",
            )
        finally:
            self._patcher.stop()
            os.unlink(self.db_path)

    def test_deposit_isolates_from_main_balance(self):
        """1.000 TL aktarımda ana bakiye azalmalı, hedef aynı tutarda artmalı."""
        goal = SavingsService.deposit_to_goal(self.goal_id, 1000.0)
        self.assertAlmostEqual(_get_balance(), self.balance_before - 1000.0, places=2)
        self.assertAlmostEqual(goal["current_amount"], 1000.0, places=2)
        self.assertEqual(goal["status"], STATUS_ACTIVE)
        self.assertEqual(goal["goal_name"], "Test Yaz Tatili (Bali)")

    def test_withdraw_returns_to_main_balance(self):
        SavingsService.deposit_to_goal(self.goal_id, 1000.0)
        goal = SavingsService.withdraw_from_goal(self.goal_id, 400.0)
        self.assertAlmostEqual(_get_balance(), self.balance_before - 600.0, places=2)
        self.assertAlmostEqual(goal["current_amount"], 600.0, places=2)

    def test_insufficient_balance_is_atomic(self):
        """Bakiye yetmiyorsa NE bakiye NE hedef değişmeli (yarım işlem yok)."""
        huge = _get_balance() + 1_000_000.0
        with self.assertRaises(ValueError):
            SavingsService.deposit_to_goal(self.goal_id, huge)
        self.assertAlmostEqual(_get_balance(), self.balance_before, places=2)
        goals = [g for g in SavingsService.get_goals() if g["id"] == self.goal_id]
        self.assertAlmostEqual(goals[0]["current_amount"], 0.0, places=2)

    def test_overdraw_from_goal_rejected(self):
        SavingsService.deposit_to_goal(self.goal_id, 100.0)
        with self.assertRaises(ValueError):
            SavingsService.withdraw_from_goal(self.goal_id, 500.0)
        self.assertAlmostEqual(_get_balance(), self.balance_before - 100.0, places=2)

    def test_goal_completion_status(self):
        """Hedefe ulaşınca status 'tamamlandi' olmalı; tamamlanana ekleme reddedilmeli."""
        # Testin ana bakiyeye takılmaması için hedefi küçük tutarla tamamla
        small_goal = SavingsService.create_goal("Test Mini Hedef", 200.0)
        try:
            goal = SavingsService.deposit_to_goal(small_goal, 200.0)
            self.assertEqual(goal["status"], STATUS_COMPLETED)
            with self.assertRaises(ValueError):
                SavingsService.deposit_to_goal(small_goal, 50.0)
            # Çekim tamamlanmışlığı geri düşürmeli
            goal = SavingsService.withdraw_from_goal(small_goal, 50.0)
            self.assertEqual(goal["status"], STATUS_ACTIVE)
        finally:
            SavingsService.delete_goal(small_goal)

    def test_goal_name_encrypted_at_rest(self):
        """goal_name DB'de düz metin durmamalı."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT goal_name FROM savings_goals WHERE id = ?", (self.goal_id,))
            raw = cur.fetchone()["goal_name"]
        finally:
            conn.close()
        self.assertNotIn("Bali", str(raw))


if __name__ == "__main__":
    unittest.main()
