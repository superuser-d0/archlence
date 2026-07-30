import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from datetime import date
from unittest import mock


from tests.fixtures import AccountFixtureMixin


class BudgetTrackingServiceTest(AccountFixtureMixin, unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database
        initialize_database()
        # İşlem yazan yardımcılar (_expense) bir hesap gerektirir; varsayılan
        # hesap seed'i kaldırıldığı için testin kendi hesabını kurması gerekir.
        self.account_id = self.create_test_account(
            name="Bütçe Testi Vadesiz", balance=1_000_000.0)

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def _plan(
            self, *, year, month, amount, category=None, name=None,
            rollover=0, template=0, threshold=80, tx_type="expense"):
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO monthly_budget_plan
               (type, name, amount, target_month, target_year, category_name,
                rollover_enabled, is_template, alert_threshold_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tx_type, name or category or "Serbest", amount, month, year,
                category, rollover, template, threshold,
            ),
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id

    def _expense(self, category, amount, when):
        from services.transaction_service import TransactionService
        TransactionService.add_transaction(
            account_id=self.account_id,
            amount=amount,
            transaction_type="expense",
            category=category,
            description=category,
            transaction_date=f"{when} 12:00:00",
            enforce_credit_limit=False,
        )

    def test_old_schema_is_migrated_and_backfilled(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE monthly_budget_plan")
        conn.execute("""
            CREATE TABLE monthly_budget_plan (
                id INTEGER PRIMARY KEY, type TEXT, name TEXT,
                amount REAL, target_month INTEGER
            )
        """)
        conn.execute(
            "INSERT INTO monthly_budget_plan(type,name,amount,target_month) "
            "VALUES ('expense','Eski Kayıt',100,1)"
        )
        conn.commit()
        conn.close()

        from database.init_db import initialize_database
        initialize_database()
        conn = sqlite3.connect(self.db_path)
        columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(monthly_budget_plan)"
            )
        }
        migrated_year = conn.execute(
            "SELECT target_year FROM monthly_budget_plan"
        ).fetchone()[0]
        conn.close()
        self.assertTrue({
            "target_year", "category_name", "rollover_enabled",
            "is_template", "alert_threshold_pct",
        }.issubset(columns))
        self.assertEqual(migrated_year, date.today().year)

    def test_target_year_keeps_same_month_plans_separate(self):
        from services.budget_service import calculate_monthly_budget
        self._plan(year=2026, month=1, amount=100, category="Süpermarket")
        self._plan(year=2027, month=1, amount=700, category="Süpermarket")
        self.assertEqual(
            calculate_monthly_budget(1, 2026)["planned_expense"], 100
        )
        self.assertEqual(
            calculate_monthly_budget(1, 2027)["planned_expense"], 700
        )

    def test_category_progress_calculates_actual_pct_and_remaining(self):
        from services.budget_service import get_category_budget_progress
        self._plan(
            year=2026, month=5, amount=500, category="Süpermarket",
            threshold=75,
        )
        self._expense("Süpermarket", 125, "2026-05-10")
        progress = get_category_budget_progress(5, 2026)[0]
        self.assertEqual(progress["planned"], 500)
        self.assertEqual(progress["actual"], 125)
        self.assertEqual(progress["pct"], 25)
        self.assertEqual(progress["remaining"], 375)
        self.assertEqual(progress["alert_threshold_pct"], 75)

    def test_rollover_disabled_positive_and_negative(self):
        from services.budget_service import get_effective_limit
        # Pozitif devir: 1000 - 700 = +300.
        self._plan(
            year=2025, month=12, amount=1000, category="Süpermarket"
        )
        self._expense("Süpermarket", 700, "2025-12-15")
        self._plan(
            year=2026, month=1, amount=500, category="Süpermarket",
            rollover=1,
        )
        self.assertEqual(
            get_effective_limit("Süpermarket", 1, 2026), 800
        )

        # Kapalı kategori önceki ayı görmez.
        self._plan(year=2025, month=12, amount=400, category="Ulaşım")
        self._plan(
            year=2026, month=1, amount=250, category="Ulaşım",
            rollover=0,
        )
        self.assertEqual(get_effective_limit("Ulaşım", 1, 2026), 250)

        # Negatif devir: 300 - 450 = -150; yeni 500 → 350.
        self._plan(year=2025, month=12, amount=300, category="Kıyafet")
        self._expense("Kıyafet", 450, "2025-12-20")
        self._plan(
            year=2026, month=1, amount=500, category="Kıyafet",
            rollover=1,
        )
        self.assertEqual(get_effective_limit("Kıyafet", 1, 2026), 350)

    def test_suggestion_uses_last_three_completed_months(self):
        from services.budget_service import suggest_category_budget
        today = date.today()

        def shifted(delta):
            index = today.year * 12 + today.month - 1 + delta
            return index // 12, index % 12 + 1

        for delta, amount in ((-1, 300), (-2, 200), (-3, 100)):
            year, month = shifted(delta)
            self._expense(
                "Süpermarket", amount, f"{year}-{month:02d}-10"
            )
        self.assertEqual(suggest_category_budget("Süpermarket"), 200)
        self.assertIsNone(suggest_category_budget("Olmayan Kategori"))

    def test_template_override_affects_only_selected_month(self):
        from services.budget_service import calculate_monthly_budget
        self._plan(
            year=2026, month=7, amount=400, category="Süpermarket",
            template=1,
        )
        self.assertEqual(
            calculate_monthly_budget(8, 2026)["planned_expense"], 400
        )
        self._plan(
            year=2026, month=8, amount=550, category="Süpermarket",
            template=0,
        )
        self.assertEqual(
            calculate_monthly_budget(8, 2026)["planned_expense"], 550
        )
        self.assertEqual(
            calculate_monthly_budget(9, 2026)["planned_expense"], 400
        )

    def test_future_subscription_is_reserved_from_monthly_budget(self):
        from database.db import insert_recurring_payment
        from services.budget_service import calculate_monthly_budget
        self._plan(
            year=2026, month=8, amount=1000, name="Maaş Planı",
            tx_type="income",
        )
        insert_recurring_payment(
            "Netflix", 229.99, "Dijital Abonelik", "monthly",
            "2026-08-31", False, recurrence_day=31,
        )
        result = calculate_monthly_budget(8, 2026)
        self.assertEqual(result["reserved_recurring"], Decimal("229.99"))
        self.assertEqual(result["remaining_budget"], Decimal("770.01"))
        self.assertEqual(
            calculate_monthly_budget(7, 2026)["reserved_recurring"], 0
        )

    # ── Aşama 2, madde 2.1: planı yıl sonuna kadar uygula ────────────────────
    def test_apply_plan_copies_concrete_items_to_remaining_months(self):
        from services.budget_service import (
            apply_plan_to_year_end, get_effective_plan_items,
        )
        self._plan(year=2026, month=10, amount=5000, category="Kira")
        self._plan(year=2026, month=10, amount=1200, category="Market")

        copied = apply_plan_to_year_end(10, 2026)
        # Ekim → Kasım, Aralık: 2 kalem × 2 ay = 4 kopya.
        self.assertEqual(copied, 4)
        for month in (11, 12):
            cats = {row["category_name"]
                    for row in get_effective_plan_items(month, 2026)}
            self.assertIn("Kira", cats)
            self.assertIn("Market", cats)

    def test_apply_plan_is_idempotent(self):
        from services.budget_service import apply_plan_to_year_end
        self._plan(year=2026, month=11, amount=5000, category="Kira")
        first = apply_plan_to_year_end(11, 2026)
        second = apply_plan_to_year_end(11, 2026)
        self.assertEqual(first, 1)   # yalnız Aralık'a kopyalanır
        self.assertEqual(second, 0)  # ikinci onay kopya üretmez

    def test_apply_plan_skips_existing_identity(self):
        from services.budget_service import apply_plan_to_year_end
        self._plan(year=2026, month=11, amount=5000, category="Kira")
        # Aralık'ta zaten farklı tutarlı bir Kira var; korunmalı, ezilmemeli.
        self._plan(year=2026, month=12, amount=9999, category="Kira")
        copied = apply_plan_to_year_end(11, 2026)
        self.assertEqual(copied, 0)


class PlannerMonthRangeTest(unittest.TestCase):
    """Ay seçici ufku: bulunduğumuz aydan Aralık'a (madde 2.1)."""

    def test_january_lists_all_months(self):
        from mixins.budget_mixin import planner_month_range
        self.assertEqual(planner_month_range(date(2026, 1, 15)), list(range(1, 13)))

    def test_july_lists_july_to_december(self):
        from mixins.budget_mixin import planner_month_range
        self.assertEqual(planner_month_range(date(2026, 7, 25)), [7, 8, 9, 10, 11, 12])

    def test_december_lists_only_december(self):
        from mixins.budget_mixin import planner_month_range
        self.assertEqual(planner_month_range(date(2026, 12, 1)), [12])


if __name__ == "__main__":
    unittest.main()
