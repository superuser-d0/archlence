"""_renewal_description testleri (abonelik kartı 'yenilenir' metni).

BAĞLAM: Aktif abonelik kartı eskiden yalnızca ham veri gösteriyordu
('aylık · Sonraki ödeme: 2026-08-26'). Kullanıcı özellikle aylık abonelikler
için 'her ayın bilmem kaçında yenilenir' tarzı okunaklı bir Türkçe ifade
istedi. Bu paket doğru ünlü-uyumlu hal ekini (bkz. _turkish_day_ordinal) ve
her dört sıklık dalını (monthly/yearly/weekly/diğer) kilitler; ayrıca
İngilizce moda dönüldüğünde cümle kalıbının da doğru değiştiğini doğrular.
"""
import os
import unittest

os.environ.setdefault("KIVY_NO_ARGS", "1")


class EnglishOrdinalTest(unittest.TestCase):
    def test_standard_and_teen_exceptions(self):
        from mixins.insights_mixin import _english_ordinal

        cases = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 11: "11th",
                 12: "12th", 13: "13th", 21: "21st", 22: "22nd", 26: "26th"}
        for day, expected in cases.items():
            self.assertEqual(_english_ordinal(day), expected, msg=f"day={day}")


class RenewalDescriptionTest(unittest.TestCase):
    def setUp(self):
        from ui.i18n import set_language
        self.addCleanup(set_language, "en")
        set_language("en")

    def test_monthly(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "monthly", "next_due_date": "2026-08-26",
        })
        self.assertEqual(text, "Renews on the 26th of each month")

    def test_monthly_uses_recurrence_day_over_next_due_date_day(self):
        """Ayın son günlerinde (28/30/31) next_due_date kısa aya kayarsa
        recurrence_day gerçek niyeti korur."""
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "monthly", "next_due_date": "2026-02-28",
            "recurrence_day": 31,
        })
        self.assertEqual(text, "Renews on the 31st of each month")

    def test_yearly(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "yearly", "next_due_date": "2026-08-26",
        })
        self.assertEqual(text, "Renews every year on August 26th")

    def test_yearly_uses_the_localized_month_name(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "yearly", "next_due_date": "2026-04-15",
        })
        self.assertEqual(text, "Renews every year on April 15th")

    def test_weekly(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "weekly", "next_due_date": "2026-08-24",
        })
        self.assertEqual(text, "Renews every Monday")

    def test_biweekly_falls_back_to_frequency_and_date(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "biweekly", "next_due_date": "2026-08-26",
        })
        self.assertEqual(text, "biweekly  ·  Next: August 26")

    def test_malformed_date_falls_back_without_crashing(self):
        from mixins.insights_mixin import _renewal_description

        text = _renewal_description({
            "frequency": "monthly", "next_due_date": "",
        })
        self.assertIn("Next payment:", text)

    def test_monthly_english(self):
        from ui.i18n import set_language
        from mixins.insights_mixin import _renewal_description

        set_language("en")
        text = _renewal_description({
            "frequency": "monthly", "next_due_date": "2026-08-26",
        })
        self.assertEqual(text, "Renews on the 26th of each month")

    def test_weekly_english(self):
        from ui.i18n import set_language
        from mixins.insights_mixin import _renewal_description

        set_language("en")
        text = _renewal_description({
            "frequency": "weekly", "next_due_date": "2026-08-24",
        })
        self.assertEqual(text, "Renews every Monday")


if __name__ == "__main__":
    unittest.main()
