import re
import unittest
from pathlib import Path

from ui.i18n import EN, get_language, set_language, tr


class I18nTestCase(unittest.TestCase):
    def tearDown(self):
        set_language("tr")

    def test_language_fallback_and_switch(self):
        self.assertEqual(set_language("en"), "en")
        self.assertEqual(tr("Ayarlar"), "Settings")
        self.assertEqual(tr("Bilinmeyen metin"), "Bilinmeyen metin")
        self.assertEqual(set_language("unsupported"), "tr")
        self.assertEqual(get_language(), "tr")

    def test_dynamic_ui_sentences_are_translated(self):
        set_language("en")
        self.assertEqual(tr("Taksit Sayısı: 6"), "Number of Installments: 6")
        self.assertEqual(tr("Aylık: 1.250 ₺"), "Monthly: 1.250 ₺")
        self.assertEqual(tr("Maaş"), "Salary")

    def test_every_static_kv_phrase_has_an_english_translation(self):
        ui_dir = Path(__file__).parents[1] / "ui"
        sources = [
            (ui_dir / "dashboard.kv").read_text(encoding="utf-8"),
            (ui_dir / "components.py").read_text(encoding="utf-8"),
        ]
        values = []
        for source in sources:
            values.extend(re.findall(
                r'app\.tr\("((?:[^"\\]|\\.)*)", app\.language\)', source
            ))
        ignored = {"", "FINORA", "ornek@finora.com"}
        missing = []
        for raw in values:
            value = raw.replace(r"\n", "\n").replace(r'\"', '"')
            if value not in ignored and value not in EN and any(ch.isalpha() for ch in value):
                missing.append(value)
        self.assertEqual(sorted(set(missing)), [])

    def test_account_dashboard_dynamic_phrases_are_translated(self):
        set_language("en")
        self.assertEqual(tr("Değişim (Bugün)"), "Change (Today)")
        self.assertEqual(tr("Nakit / Vadesiz"), "Cash / Checking")
        self.assertEqual(tr("3 TL dışı varlık • Canlı değer"), "3 non-TRY assets • Live value")


if __name__ == "__main__":
    unittest.main()
