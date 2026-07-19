import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.init_db import initialize_database
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


class SavingsServiceTest(unittest.TestCase):
    """Gerçek finance.db üzerinde çalışır; her test kendi açtığı hedefi silip
    bakiyeyi başlangıç değerine geri döndürür (delete_goal iadesi sayesinde)."""

    def setUp(self):
        initialize_database()  # savings_goals tablosu idempotent oluşsun
        self.balance_before = _get_balance()
        self.goal_id = SavingsService.create_goal(
            "Test Yaz Tatili (Bali)", 50000.0, "2026-08-01"
        )

    def tearDown(self):
        SavingsService.delete_goal(self.goal_id)
        self.assertAlmostEqual(
            _get_balance(), self.balance_before, places=2,
            msg="Temizlik sonrası bakiye başlangıca dönmedi",
        )

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
