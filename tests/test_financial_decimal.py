import unittest
from decimal import Decimal
from unittest import mock

from services import budget_service
from utils.errors import FinancialDataIntegrityError
from utils.financial_decimal import (
    FinancialPrecision,
    decimal_from,
    fiat,
    percentage,
    quantity,
)


class FinancialDecimalPolicyTest(unittest.TestCase):
    def test_binary_float_is_converted_through_text(self):
        self.assertEqual(decimal_from(0.1), Decimal("0.1"))

    def test_fiat_uses_bankers_rounding(self):
        self.assertEqual(fiat("1.005"), Decimal("1.00"))
        self.assertEqual(fiat("1.015"), Decimal("1.02"))

    def test_asset_quantity_rules_are_explicit(self):
        self.assertEqual(quantity("1.23456", "Altın"), Decimal("1.2346"))
        self.assertEqual(quantity("1.2345678", "Hisse"), Decimal("1.234568"))
        self.assertEqual(
            quantity("1.234567895", "Kripto"), Decimal("1.23456790")
        )

    def test_percentage_has_one_shared_precision(self):
        self.assertEqual(percentage("12.345"), Decimal("12.34"))
        self.assertEqual(
            FinancialPrecision.PERCENT.value, FinancialPrecision.FIAT.value
        )

    def test_non_finite_values_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal_from(value)


class BudgetIntegrityBoundaryTest(unittest.TestCase):
    def test_corrupt_encrypted_budget_value_never_becomes_zero(self):
        with mock.patch(
            "services.budget_service.decrypt",
            side_effect=ValueError("ciphertext rejected"),
        ):
            with self.assertRaises(FinancialDataIntegrityError) as raised:
                budget_service._amount(
                    "not-a-number",
                    table="monthly_budget_plan",
                    record_id=73,
                )
        self.assertEqual(raised.exception.record_id, 73)

    def test_budget_amount_is_decimal(self):
        self.assertEqual(
            budget_service._amount(
                "10.10", table="monthly_budget_plan", record_id=1
            ),
            Decimal("10.10"),
        )


if __name__ == "__main__":
    unittest.main()
