"""Shared Decimal boundaries and explicit financial rounding rules."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from enum import Enum


class FinancialPrecision(Enum):
    FIAT = Decimal("0.01")
    PRECIOUS_METAL_QUANTITY = Decimal("0.0001")
    EQUITY_QUANTITY = Decimal("0.000001")
    CRYPTO_QUANTITY = Decimal("0.00000001")
    PERCENT = Decimal("0.01")
    UNIT_PRICE = Decimal("0.00000001")


def decimal_from(value: object) -> Decimal:
    """Return a finite Decimal without importing binary-float artefacts."""
    if isinstance(value, bool):
        raise ValueError("Boolean is not a financial number.")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Financial value is not numeric.") from exc
    if not result.is_finite():
        raise ValueError("Financial value must be finite.")
    return result


def quantize_financial(
    value: object,
    precision: FinancialPrecision = FinancialPrecision.FIAT,
) -> Decimal:
    return decimal_from(value).quantize(precision.value, rounding=ROUND_HALF_EVEN)


def fiat(value: object) -> Decimal:
    return quantize_financial(value, FinancialPrecision.FIAT)


def percentage(value: object) -> Decimal:
    return quantize_financial(value, FinancialPrecision.PERCENT)


def quantity(value: object, asset_type: str) -> Decimal:
    kind = str(asset_type or "").strip().casefold()
    if kind in {"altın", "gold", "precious_metal", "precious metal"}:
        precision = FinancialPrecision.PRECIOUS_METAL_QUANTITY
    elif kind in {"hisse", "stock", "equity"}:
        precision = FinancialPrecision.EQUITY_QUANTITY
    elif kind in {"kripto", "crypto", "cryptocurrency"}:
        precision = FinancialPrecision.CRYPTO_QUANTITY
    else:
        precision = FinancialPrecision.UNIT_PRICE
    return quantize_financial(value, precision)
