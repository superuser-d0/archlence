import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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

    def test_what_if_labels_have_real_turkish_translations(self):
        set_language("tr")
        self.assertEqual(tr("What-If\nSandbox"), "Varsayım\nAlanı")
        self.assertEqual(tr("What-If Sandbox"), "Varsayım Alanı")
        set_language("en")
        self.assertEqual(tr("What-If\nSandbox"), "What-If\nSandbox")
        self.assertEqual(tr("What-If Sandbox"), "What-If Sandbox")

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
        ignored = {"", "ARCHLENCE"}
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

    def test_language_refresh_reconciles_bottom_navigation_header_texture(self):
        """KivyMD header tab.text'i kopyalasa da son dil dokusu zorla uzlaştırılır."""
        import os
        os.environ.setdefault("ARCHLENCE_HEADLESS", "1")
        from main import ArchlenceApp

        label = SimpleNamespace(text="Ayarlar", texture_update=mock.Mock())
        header = SimpleNamespace(
            ids=SimpleNamespace(_label=label),
            canvas=SimpleNamespace(ask_update=mock.Mock()),
        )
        tab = SimpleNamespace(text="Settings", header=header)
        nav = SimpleNamespace(
            ids=SimpleNamespace(
                tab_manager=SimpleNamespace(screens=[tab])
            )
        )
        app = ArchlenceApp.__new__(ArchlenceApp)
        app.root = SimpleNamespace(ids={"bottom_nav": nav})
        app._refresh_text_textures = mock.Mock()

        app._refresh_language_widgets()

        self.assertEqual(label.text, "Settings")
        label.texture_update.assert_called_once_with()
        header.canvas.ask_update.assert_called_once_with()
        app._refresh_text_textures.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
