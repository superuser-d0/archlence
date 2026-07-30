"""UI-independent financial aggregation with explicit data-quality failure."""

from dataclasses import dataclass
from decimal import Decimal

from database.db import SECRET_KEY
from utils.crypto import decrypt
from utils.errors import (
    DecryptionError,
    FinancialDataIntegrityError,
    KeyUnavailableError,
)
from utils.financial_decimal import decimal_from


@dataclass(frozen=True)
class FinancialSummary:
    main_income: Decimal = Decimal("0")
    extra_income: Decimal = Decimal("0")
    essential_expense: Decimal = Decimal("0")
    extra_expense: Decimal = Decimal("0")

    @property
    def total_income(self):
        return self.main_income + self.extra_income

    @property
    def total_expense(self):
        return self.essential_expense + self.extra_expense

    @property
    def net(self):
        return self.total_income - self.total_expense


def decrypt_decimal(value, *, table, record_id, field="amount"):
    """Decrypt one financial value or invalidate the whole derived result."""
    try:
        plaintext = decrypt(str(value), SECRET_KEY)
        amount = decimal_from(plaintext)
        return amount
    except KeyUnavailableError:
        raise
    except (DecryptionError, TypeError, ValueError) as exc:
        raise FinancialDataIntegrityError(
            table, record_id, field, reason=exc
        ) from exc


def summarize_transactions(rows):
    """Aggregate rows containing id, amount, type and importance.

    A single unreadable contributing row invalidates the summary. Returning a
    partial or zero-adjusted result is intentionally forbidden.
    """
    buckets = {
        "main_income": Decimal("0"),
        "extra_income": Decimal("0"),
        "essential_expense": Decimal("0"),
        "extra_expense": Decimal("0"),
    }
    for row in rows:
        amount = decrypt_decimal(
            row["amount"],
            table="transactions",
            record_id=row["id"],
        )
        tx_type = row["type"]
        importance = row["importance"] or "extra"
        if tx_type in ("income", "Gelir"):
            key = "main_income" if importance == "main" else "extra_income"
        elif tx_type in ("expense", "Gider"):
            key = (
                "essential_expense"
                if importance == "main"
                else "extra_expense"
            )
        else:
            continue
        buckets[key] += amount
    return FinancialSummary(**buckets)
