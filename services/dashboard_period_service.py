"""Canonical dashboard periods and balance-change calculations.

The dashboard previously compared the current period's cash flow with the
previous period's cash flow.  That is a growth-rate comparison, not a balance
change, and it produced a misleading +/-100% whenever the previous period had
no transactions.  This module keeps the selected period, nominal balance
change, and percentage on one shared definition.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from utils.financial_decimal import decimal_from


PERIOD_DAYS = {
    "Bugün": 1,
    "1 Hafta": 7,
    "1 Ay": 30,
    "1 Yıl": 365,
}


def period_bounds(filter_text: str, today: date | None = None) -> tuple[date | None, date]:
    """Return the inclusive date window for a canonical dashboard filter."""
    end = today or date.today()
    days = PERIOD_DAYS.get(filter_text)
    if days is None:
        return None, end
    return end - timedelta(days=days - 1), end


def percentage_change(starting_balance, current_balance) -> float | None:
    """Return balance change percent without inventing a zero baseline.

    A move away from an actual zero balance has no finite percentage, so the UI
    shows an unavailable marker.  Zero to zero is the one well-defined no-change
    case and returns 0%.
    """
    if starting_balance is None:
        return None
    start = decimal_from(starting_balance)
    current = decimal_from(current_balance)
    if start == 0:
        return 0.0 if current == 0 else None
    return float(((current - start) / abs(start)) * Decimal("100"))


def calculate_balance_change(
    filter_text: str,
    current_balance,
    *,
    today: date | None = None,
    balance_reader=None,
) -> dict:
    """Calculate the selected period's nominal and percentage balance change.

    ``balance_reader`` follows ``history_service.get_balance_at`` and makes the
    boundary behaviour independently testable.  The baseline is the end of the
    day immediately before the inclusive period begins.
    """
    start, end = period_bounds(filter_text, today)
    current = decimal_from(current_balance)
    if start is None:
        return {
            "start_date": None,
            "end_date": end,
            "starting_balance": None,
            "nominal_change": current,
            "percentage": None,
        }

    if balance_reader is None:
        from services.history_service import get_balance_at
        balance_reader = get_balance_at

    baseline_date = start - timedelta(days=1)
    baseline = balance_reader(baseline_date)
    starting = baseline.get("total_balance") if baseline else None
    if starting is None:
        nominal = None
    else:
        nominal = current - decimal_from(starting)

    return {
        "start_date": start,
        "end_date": end,
        "baseline_date": baseline_date,
        "starting_balance": None if starting is None else decimal_from(starting),
        "nominal_change": nominal,
        "percentage": percentage_change(starting, current),
    }
