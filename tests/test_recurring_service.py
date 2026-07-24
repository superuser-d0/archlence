import os
import tempfile
import unittest
from unittest import mock


class RecurringServiceTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()

        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def test_digital_subscription_enables_switch_without_permanent_binding(self):
        from services.recurring_service import apply_category_trigger

        switch = mock.Mock(active=False)
        self.assertTrue(apply_category_trigger("Dijital Abonelik", switch))
        self.assertTrue(switch.active)

        # Yardımcı yalnız seçim anında çalışır; kullanıcı sonradan kapatabilir.
        switch.active = False
        self.assertFalse(switch.active)
        self.assertFalse(apply_category_trigger("Süpermarket", switch))
        self.assertFalse(switch.active)

    def test_recurrence_day_is_saved_and_returned(self):
        from database.db import (
            get_active_recurring_payments,
            insert_recurring_payment,
        )
        from services.recurring_service import next_due_for_recurrence

        next_due = next_due_for_recurrence("2026-07-24", "monthly", 31)
        self.assertEqual(next_due, "2026-08-31")
        self.assertEqual(
            next_due_for_recurrence("2026-02-28", "monthly", 31),
            "2026-03-31",
        )
        insert_recurring_payment(
            "Netflix",
            229.99,
            "Dijital Abonelik",
            "monthly",
            next_due,
            False,
            recurrence_day=31,
        )

        payment = get_active_recurring_payments()[0]
        self.assertEqual(payment["recurrence_day"], 31)
        self.assertEqual(payment["next_due_date"], "2026-08-31")

    def test_new_category_is_available_and_reusable(self):
        from services.queries import CategoryService

        names_first = [
            row["name"] for row in CategoryService.get_categories("expense")
        ]
        names_second = [
            row["name"] for row in CategoryService.get_categories("expense")
        ]
        self.assertIn("Dijital Abonelik", names_first)
        self.assertEqual(names_first, names_second)


if __name__ == "__main__":
    unittest.main()
