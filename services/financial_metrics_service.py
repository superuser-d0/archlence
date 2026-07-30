"""UI-independent financial metric contract with explicit data quality."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Iterable, TypeVar

from services.financial_summary_service import (
    FinancialSummary,
    summarize_transactions,
)
from utils.errors import FinancialDataIntegrityError, KeyUnavailableError
from utils.logging_config import log_integrity_error, report_error


T = TypeVar("T")


class DataQuality(str, Enum):
    VALID = "valid"
    PARTIAL = "partial"
    STALE = "stale"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class MetricResult(Generic[T]):
    value: T | None
    quality: DataQuality
    error_id: str | None = None

    @property
    def is_definitive(self) -> bool:
        return self.quality is DataQuality.VALID


class FinancialMetricsService:
    """The only UI-facing entry point for transaction summary reliability."""

    def summarize(self, rows: Iterable[object]) -> MetricResult[FinancialSummary]:
        try:
            return MetricResult(
                value=summarize_transactions(rows),
                quality=DataQuality.VALID,
            )
        except FinancialDataIntegrityError as exc:
            # Metadata only: table/id/field are safe, financial values are not.
            return MetricResult(
                value=None,
                quality=DataQuality.INVALID,
                error_id=log_integrity_error(exc),
            )
        except KeyUnavailableError as exc:
            return MetricResult(
                value=None,
                quality=DataQuality.UNAVAILABLE,
                error_id=report_error("financial_metric_key_unavailable", exc),
            )
