"""Tekrarlanan ödeme formu ve vade günü için Kivy'den bağımsız kurallar."""

import calendar
from datetime import date

from database.db import _advance_due_date


SUBSCRIPTION_CATEGORY = "Dijital Abonelik"


def apply_category_trigger(category, recurring_switch) -> bool:
    """Dijital abonelik seçildiyse switch'i bir kez açar.

    Sonrasında kalıcı bir binding kurulmaz; kullanıcı switch'i manuel olarak
    tekrar kapatabilir.
    """
    should_enable = str(category).strip() == SUBSCRIPTION_CATEGORY
    if should_enable:
        recurring_switch.active = True
    return should_enable


def next_due_for_recurrence(
        from_date: str | date, frequency: str, recurrence_day: int) -> str:
    """Bir sonraki periyodu seçilen ay gününe sabitleyerek döndürür."""
    day = int(recurrence_day)
    if not 1 <= day <= 31:
        raise ValueError("Tekrarlama günü 1 ile 31 arasında olmalıdır.")
    source = from_date if isinstance(from_date, date) else date.fromisoformat(from_date)
    advanced = date.fromisoformat(_advance_due_date(source.isoformat(), frequency))
    valid_day = min(day, calendar.monthrange(advanced.year, advanced.month)[1])
    return advanced.replace(day=valid_day).isoformat()
