import math
import unittest

from services.projection_service import (
    project_final_wealth,
    project_wealth_series,
    simulate_scenario,
)


class ProjectionServiceTest(unittest.TestCase):

    def test_rk4_matches_analytic_solution(self):
        initial = 10000.0
        income_minus_expense = 25.0
        rate = 0.0001
        days = 30
        expected = (
            (initial + income_minus_expense / rate) * math.exp(rate * days)
            - income_minus_expense / rate
        )

        actual = project_final_wealth(
            initial, daily_income=75.0, daily_expense=50.0,
            days=days, r=rate,
        )

        self.assertAlmostEqual(actual, expected, places=6)

    def test_series_contains_day_zero_and_horizon(self):
        series = project_wealth_series(100.0, 10.0, 5.0, days=3, r=0.0)

        self.assertEqual([day for day, _value in series], [0, 1, 2, 3])
        self.assertEqual(series[0][1], 100.0)
        self.assertEqual(series[-1][1], 115.0)

    def test_scenario_applies_income_and_expense_deltas(self):
        result = simulate_scenario(
            1000.0, 100.0, 80.0,
            income_delta_pct=20.0,
            expense_delta_pct=-25.0,
            days=1,
            r=0.0,
        )

        self.assertEqual(result["inputs"]["scenario_daily_income"], 120.0)
        self.assertEqual(result["inputs"]["scenario_daily_expense"], 60.0)
        self.assertEqual(result["base_final"], 1020.0)
        self.assertEqual(result["scenario_final"], 1060.0)

    def test_one_time_expense_can_drive_wealth_negative(self):
        result = simulate_scenario(
            500.0, 0.0, 25.0, days=30, r=0.0,
            one_time_adjustment=-1000.0,
        )

        self.assertTrue(result["goes_negative"])
        self.assertLess(result["scenario_final"], 0)

    def test_365_day_projection_is_finite(self):
        result = simulate_scenario(
            25000.0, 300.0, 250.0, days=365, r=0.0001,
        )

        self.assertEqual(len(result["scenario_series"]), 366)
        self.assertTrue(math.isfinite(result["scenario_final"]))

    def test_negative_horizon_is_rejected(self):
        with self.assertRaises(ValueError):
            project_wealth_series(100.0, 10.0, 5.0, days=-1)


if __name__ == "__main__":
    unittest.main()
