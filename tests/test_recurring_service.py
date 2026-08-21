import os
import tempfile
import unittest
from datetime import date
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

    def test_due_recurring_income_is_added_to_balance(self):
        from database.db import (
            get_active_recurring_payments,
            insert_recurring_payment,
            managed_connection,
            process_due_recurring_payment,
        )
        from services.account_service import AccountService
        from utils.crypto import decrypt
        from database.db import SECRET_KEY

        account_id = AccountService.create_account(
            "Maaş Hesabı", "checking", initial_balance=1000,
        )
        insert_recurring_payment(
            "Maaş", 5000, "Maaş", "monthly", date.today().isoformat(),
            True, account_id=account_id, recurrence_day=15,
            transaction_type="income",
        )
        payment = get_active_recurring_payments()[0]
        self.assertEqual(payment["transaction_type"], "income")

        process_due_recurring_payment(payment)

        account = AccountService.get_account(account_id)
        self.assertEqual(account["balance"], 6000)
        with managed_connection() as conn:
            row = conn.execute(
                "SELECT type, amount FROM transactions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            event = conn.execute(
                "SELECT delta, source FROM balance_events "
                "WHERE entity_type='account' AND entity_id=? ORDER BY id DESC LIMIT 1",
                (account_id,),
            ).fetchone()
        self.assertEqual(row["type"], "income")
        self.assertEqual(float(decrypt(row["amount"], SECRET_KEY)), 5000)
        self.assertEqual((event["delta"], event["source"]),
                         (5000, "recurring_payment"))

    def test_current_month_income_decision_is_explicit_and_date_safe(self):
        from services.recurring_service import initial_recurring_income_date

        today = date(2026, 7, 29)
        self.assertIsNone(initial_recurring_income_date(today, 15, False))
        self.assertEqual(
            initial_recurring_income_date(today, 15, True), today,
        )
        self.assertEqual(
            initial_recurring_income_date(today, 31, True),
            date(2026, 7, 31),
        )
        self.assertEqual(
            initial_recurring_income_date(date(2026, 2, 10), 31, True),
            date(2026, 2, 28),
        )


if __name__ == "__main__":
    unittest.main()
