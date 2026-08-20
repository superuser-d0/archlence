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
        """Dinamik cümleler artık ŞABLONDAN kuruluyor.

        Bu test eskiden `tr("Taksit Sayısı: 6")` diyordu ve alt dize
        değiştiren fallback'e güveniyordu. O fallback kullanıcı verisini de
        çeviriyordu (bkz. tests/test_i18n_user_data.py); kaldırıldı.
        Sözleşme artık: şablon çevrilir, sayı sonradan yerleşir.
        """
        from ui.i18n import trf

        set_language("en")
        self.assertEqual(
            trf("Taksit Sayısı: {count}", count=6),
            "Number of Instalments: 6",
        )
        self.assertEqual(
            trf("Aylık: {monthly_payment} ₺", monthly_payment="1.250"),
            "Monthly: 1.250 ₺",
        )
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
        from ui.i18n import trf

        set_language("en")
        # Sabit etiketler TAM ANAHTAR olarak duruyor.
        self.assertEqual(tr("Değişim (Bugün)"), "Change (Today)")
        self.assertEqual(tr("Nakit / Vadesiz"), "Cash / Checking")
        # Sayı taşıyan cümle ise şablon + parametre.
        self.assertEqual(
            trf("{count} TL dışı varlık • Canlı değer", count=3),
            "3 non-TRY assets • Live value",
        )

    def test_every_forecast_state_is_a_complete_english_sentence(self):
        """Dinamik tutar eklenirken öngörü metni karma dile dönmemeli."""
        import os
        os.environ.setdefault("ARCHLENCE_HEADLESS", "1")
        from main import ArchlenceApp

        set_language("en")
        app = ArchlenceApp.__new__(ArchlenceApp)
        cases = [
            ({"insufficient_data": True}, "neutral"),
            ({"insufficient_data": False,
              "projected_month_end_balance": -250.0,
              "projected_surplus": -500.0, "savings_rate": -0.1}, "negative"),
            ({"insufficient_data": False,
              "projected_month_end_balance": 750.0,
              "projected_surplus": -50.0, "savings_rate": 0.0}, "warning"),
            ({"insufficient_data": False,
              "projected_month_end_balance": 2500.0,
              "projected_surplus": 800.0, "savings_rate": 0.2}, "positive"),
            ({"insufficient_data": False,
              "projected_month_end_balance": 1200.0,
              "projected_surplus": 100.0, "savings_rate": 0.05}, "neutral"),
        ]

        for forecast, expected_state in cases:
            with self.subTest(state=expected_state), mock.patch(
                "services.insights_service.generate_monthly_forecast",
                return_value=forecast,
            ):
                text, state = app._compute_monthly_forecast_text()
                self.assertEqual(state, expected_state)
                self.assertTrue(text.startswith("Based on the last 3 months"))
                for turkish_fragment in ("aylık", "işlem geçmişi", "bakiyeniz"):
                    self.assertNotIn(turkish_fragment, text)

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
