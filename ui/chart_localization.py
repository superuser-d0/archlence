"""Pure localization helpers shared by chart rendering and tests."""

from ui.i18n import tr as _t


_MONTH_KEYS = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)


def localized_month_abbreviation(month: int) -> str:
    if not 1 <= int(month) <= 12:
        raise ValueError("month must be between 1 and 12")
    return _t(_MONTH_KEYS[int(month) - 1])[:3]


def format_chart_day(day) -> str:
    return f"{day.day:02d} {localized_month_abbreviation(day.month)}"


def trend_legend_labels(has_opening=False):
    labels = [_t("Gider"), _t("Gelir")]
    if has_opening:
        labels.append(_t("Açılış Bakiyesi"))
    return labels
