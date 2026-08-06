import os
import unittest

os.environ.setdefault("KIVY_NO_ARGS", "1")

from ui.chart_localization import (
    format_chart_day,
    localized_month_abbreviation,
    trend_legend_labels,
)
from ui.i18n import set_language, tr


class ChartLocalizationTest(unittest.TestCase):
    def tearDown(self):
        set_language("tr")

    def test_english_chart_labels_and_asset_types(self):
        set_language("en")
        self.assertEqual(trend_legend_labels(True), ["Expense", "Income", "Opening Balance"])
        self.assertEqual(localized_month_abbreviation(8), "Aug")
        self.assertEqual(format_chart_day(__import__("datetime").date(2026, 8, 6)), "06 Aug")
        self.assertEqual(
            [tr(value) for value in ("Döviz", "Altın", "Hisse", "Kripto")],
            ["Currency", "Gold", "Stock", "Crypto"],
        )

    def test_turkish_chart_labels_still_work(self):
        set_language("tr")
        self.assertEqual(trend_legend_labels(True), ["Gider", "Gelir", "Açılış Bakiyesi"])
        self.assertEqual(localized_month_abbreviation(8), "Ağu")


if __name__ == "__main__":
    unittest.main()
