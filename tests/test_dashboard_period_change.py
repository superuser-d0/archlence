import datetime
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")

from services.dashboard_period_service import (
    calculate_balance_change,
    percentage_change,
    period_bounds,
)


class DashboardPeriodChangeTest(unittest.TestCase):
    TODAY = datetime.date(2026, 8, 6)

    def test_period_boundaries_are_inclusive_and_canonical(self):
        expected = {
            "Bugün": datetime.date(2026, 8, 6),
            "1 Hafta": datetime.date(2026, 7, 31),
            "1 Ay": datetime.date(2026, 7, 8),
            "1 Yıl": datetime.date(2025, 8, 7),
        }
        for label, start in expected.items():
            with self.subTest(label=label):
                self.assertEqual(period_bounds(label, self.TODAY), (start, self.TODAY))

    def _result(self, label, start_balance, current):
        return calculate_balance_change(
            label,
            current,
            today=self.TODAY,
            balance_reader=lambda _day: {
                "total_balance": start_balance,
                "basis": "replay",
            },
        )

    def test_positive_change(self):
        result = self._result("1 Ay", 1000, 1250)
        self.assertEqual(result["nominal_change"], 250)
        self.assertEqual(result["percentage"], 25.0)

    def test_negative_change(self):
        result = self._result("1 Yıl", 800, 600)
        self.assertEqual(result["nominal_change"], -200)
        self.assertEqual(result["percentage"], -25.0)

    def test_zero_start_does_not_invent_one_hundred_percent(self):
        self.assertIsNone(percentage_change(0, 100))

    def test_no_data_is_zero_change(self):
        result = self._result("Bugün", 0, 0)
        self.assertEqual(result["nominal_change"], 0)
        self.assertEqual(result["percentage"], 0.0)

    def test_missing_period_baseline_is_explicitly_unavailable(self):
        result = self._result("1 Hafta", None, 500)
        self.assertIsNone(result["nominal_change"])
        self.assertIsNone(result["percentage"])

    def test_missing_snapshot_can_replay_ledger(self):
        result = calculate_balance_change(
            "1 Ay",
            900,
            today=self.TODAY,
            balance_reader=lambda _day: {
                "total_balance": 750,
                "basis": "replay",
                "snapshot_date": None,
            },
        )
        self.assertEqual(result["nominal_change"], 150)
        self.assertEqual(result["percentage"], 20.0)

    def test_stale_background_result_is_ignored_after_filter_change(self):
        import main

        app = SimpleNamespace(home_filter="1 Yıl", root=object())
        # If the stale-filter guard regresses this tries to access root.ids and
        # raises; returning cleanly proves the obsolete Today result is ignored.
        main.ArchlenceApp._apply_dashboard_metrics(
            app,
            {"filter_text": "Bugün"},
        )


if __name__ == "__main__":
    unittest.main()
