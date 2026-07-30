import logging
import unittest
from decimal import Decimal
from unittest import mock

from services.financial_summary_service import summarize_transactions
from utils.errors import FinancialDataIntegrityError
from utils.logging_config import SensitiveDataFilter


class FinancialSummaryIntegrityTest(unittest.TestCase):
    def test_decimal_summary_is_ui_independent(self):
        rows = [
            {"id": 1, "amount": "enc-1", "type": "income",
             "importance": "main"},
            {"id": 2, "amount": "enc-2", "type": "expense",
             "importance": "extra"},
        ]
        with mock.patch(
            "services.financial_summary_service.decrypt",
            side_effect=["0.10", "0.03"],
        ):
            result = summarize_transactions(rows)

        self.assertEqual(result.total_income, Decimal("0.10"))
        self.assertEqual(result.total_expense, Decimal("0.03"))
        self.assertEqual(result.net, Decimal("0.07"))

    def test_one_corrupt_record_invalidates_entire_summary(self):
        rows = [
            {"id": 41, "amount": "good", "type": "income",
             "importance": "main"},
            {"id": 42, "amount": "corrupt", "type": "expense",
             "importance": "extra"},
        ]
        from utils.errors import IntegrityVerificationError
        with mock.patch(
            "services.financial_summary_service.decrypt",
            side_effect=["100", IntegrityVerificationError("invalid")],
        ):
            with self.assertRaises(FinancialDataIntegrityError) as raised:
                summarize_transactions(rows)

        self.assertEqual(raised.exception.table, "transactions")
        self.assertEqual(raised.exception.record_id, 42)
        self.assertEqual(raised.exception.field, "amount")


class LogRedactionTest(unittest.TestCase):
    def test_sensitive_values_and_ciphertext_are_redacted(self):
        record = logging.LogRecord(
            "archlence", logging.ERROR, __file__, 1,
            "token=super-secret AEADv1:QUJDREVGRw==", (), None,
        )
        self.assertTrue(SensitiveDataFilter().filter(record))
        rendered = record.getMessage()
        self.assertNotIn("super-secret", rendered)
        self.assertNotIn("QUJDREVGRw", rendered)
        self.assertIn("[REDACTED]", rendered)


if __name__ == "__main__":
    unittest.main()
