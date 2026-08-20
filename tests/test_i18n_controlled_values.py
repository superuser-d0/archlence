"""Kontrollü Türkçe değerler İngilizce cümlenin ortasında kalmamalı.

ÖLÇÜLEN KUSUR: `trf()` sözleşmesi doğruydu ama ÜRETİM çağrıları kontrollü
enum değerini şablona HAM veriyordu. `set_language("en")` altında ölçülen
çıktılar:

    Select Type: Hisse        (beklenen: Select Type: Stock)
    Add New Altın             (beklenen: Add New Gold)
    Gold Type: Gram Altın     (beklenen: Gold Type: Gram Gold)
    Type: Döviz               (beklenen: Type: Currency)

MEVCUT TESTİN KÖR NOKTASI: `trf("Tür Seç: {type}", type=tr("Hisse", "en"))`
yalnız YARDIMCININ kendisini doğruluyordu — parametreyi testin kendisi
çeviriyordu. Üretim yolu `tr()` çağırmadığı hâlde test yeşil kalıyordu.

Bu paket bu yüzden GERÇEK ÜRETİM METOTLARINI çağırır: dropdown handler'ları,
kart/diyalog metnini üreten fonksiyonlar. Parametreyi test değil, üretim
kodu hazırlar.

İÇ MANTIK DEĞİŞMEZ: `self._asset_selected_type` gibi alanlar Türkçe enum
değerini tutmaya devam eder ("Altın" karşılaştırmaları bozulmamalı);
çevrilen yalnız GÖRÜNTÜ değeridir. Bunu da ayrıca sınıyoruz.
"""

import os
import sys
import unittest

os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Button:
    """`MDRaisedButton` yerine geçen en küçük yüzey: yalnız `text`."""

    def __init__(self):
        self.text = ""


class _Menu:
    def __init__(self):
        self.dismissed = False

    def dismiss(self):
        self.dismissed = True


class _LanguageCase(unittest.TestCase):
    def setUp(self):
        from ui import i18n

        self._previous = i18n.get_language()
        self.addCleanup(i18n.set_language, self._previous)

    def in_english(self):
        from ui import i18n

        i18n.set_language("en")

    def in_turkish(self):
        from ui import i18n

        i18n.set_language("tr")


class AssetTypeSelectionTest(_LanguageCase):
    """Varlık türü: menü, seçim handler'ı ve form başlığı."""

    def _mixin(self, selected="Hisse"):
        from mixins.asset_mixin import AssetMixin

        app = AssetMixin.__new__(AssetMixin)
        app._asset_selected_type = selected
        app._asset_type_menu = _Menu()
        return app

    def test_selection_handler_shows_a_translated_type(self):
        """ÜRETİM YOLU: dropdown'dan tür seçildiğinde düğme metni."""
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        app = self._mixin()
        button = _Button()

        AssetMixin._select_asset_type_main(app, "Hisse", button)

        self.assertEqual(button.text, "Select Type: Stock")

    def test_every_asset_type_is_fully_translated_by_the_handler(self):
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        expected = {
            "Hisse": "Select Type: Stock",
            "Altın": "Select Type: Gold",
            "Tahvil": "Select Type: Bond",
            "Döviz": "Select Type: Currency",
            "Kripto": "Select Type: Crypto",
            "Diğer": "Select Type: Other",
        }
        for turkish, english in expected.items():
            with self.subTest(asset_type=turkish):
                app = self._mixin()
                button = _Button()
                AssetMixin._select_asset_type_main(app, turkish, button)
                self.assertEqual(button.text, english)

    def test_the_handler_keeps_the_turkish_value_for_business_logic(self):
        """İÇ MANTIK BOZULMAMALI: alan Türkçe enum değerini tutar."""
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        app = self._mixin()
        AssetMixin._select_asset_type_main(app, "Altın", _Button())

        self.assertEqual(app._asset_selected_type, "Altın")
        # Uygulamanın gerçekten yaptığı karşılaştırma.
        self.assertTrue(app._asset_selected_type == "Altın")

    def test_the_legacy_handler_also_translates(self):
        """İkinci (eski uyumluluk) dropdown handler'ı da aynı sözleşmede."""
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        app = self._mixin()
        button = _Button()
        menu = _Menu()

        AssetMixin._select_asset_type(app, "Döviz", button, menu)

        self.assertEqual(button.text, "Type: Currency")
        self.assertEqual(app._asset_selected_type, "Döviz")

    def test_turkish_mode_keeps_the_turkish_label(self):
        from mixins.asset_mixin import AssetMixin

        self.in_turkish()
        app = self._mixin()
        button = _Button()

        AssetMixin._select_asset_type_main(app, "Hisse", button)

        self.assertEqual(button.text, "Tür Seç: Hisse")

    def test_no_turkish_fragment_survives_in_english(self):
        """Genel kural: İngilizce çıktıda Türkçe enum parçası kalmamalı."""
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        for turkish in ("Hisse", "Altın", "Tahvil", "Döviz", "Kripto"):
            with self.subTest(asset_type=turkish):
                app = self._mixin()
                button = _Button()
                AssetMixin._select_asset_type_main(app, turkish, button)
                self.assertNotIn(turkish, button.text)


class AssetDialogTitleTest(_LanguageCase):
    """ÜRETİM YOLU: `asset_form_title` — diyaloğun gerçekten çağırdığı üretici."""

    def test_the_title_is_fully_english(self):
        from mixins.asset_mixin import asset_form_title

        self.in_english()
        self.assertEqual(asset_form_title("Altın"), "Add New Gold")
        self.assertEqual(asset_form_title("Hisse"), "Add New Stock")

    def test_every_asset_type_produces_an_english_title(self):
        from mixins.asset_mixin import asset_form_title

        self.in_english()
        for turkish in ("Hisse", "Altın", "Tahvil", "Döviz", "Kripto", "Diğer"):
            with self.subTest(asset_type=turkish):
                title = asset_form_title(turkish)
                self.assertTrue(title.startswith("Add New "), title)
                self.assertNotIn(turkish, title)

    def test_the_title_stays_turkish_in_turkish(self):
        from mixins.asset_mixin import asset_form_title

        self.in_turkish()
        self.assertEqual(asset_form_title("Altın"), "Yeni Altın Ekle")


class GoldTypeSelectionTest(_LanguageCase):
    """ÜRETİM YOLU: `gold_type_button_text` — düğmenin çağırdığı üretici."""

    def test_the_first_gold_type_is_translated(self):
        from mixins.asset_mixin import AssetMixin, gold_type_button_text

        self.in_english()
        first = AssetMixin._GOLD_TYPES[0][0]
        self.assertEqual(gold_type_button_text(first), "Gold Type: Gram Gold")

    def test_every_gold_type_is_translated(self):
        from mixins.asset_mixin import AssetMixin, gold_type_button_text

        self.in_english()
        for label, _symbol, _friendly in AssetMixin._GOLD_TYPES:
            with self.subTest(gold_type=label):
                rendered = gold_type_button_text(label)
                self.assertTrue(rendered.startswith("Gold Type: "), rendered)
                self.assertNotIn("Altın", rendered)

    def test_turkish_mode_keeps_the_turkish_gold_label(self):
        from mixins.asset_mixin import AssetMixin, gold_type_button_text

        self.in_turkish()
        first = AssetMixin._GOLD_TYPES[0][0]
        self.assertEqual(gold_type_button_text(first), "Altın Türü: Gram Altın")


class RecurringCandidateTest(_LanguageCase):
    """ÜRETİM YOLU: abonelik adayı kartının başlık ve ayrıntı üreticileri."""

    CANDIDATE = {
        "name": "Nakit",            # KULLANICI VERİSİ — çevrilmemeli
        "frequency": "monthly",
        "category": "Dijital Platformlar",
        "average_amount": 100.0,
        "monthly_cost": 100.0,
        "occurrences": 3,
        "last_seen": "2026-08-01",
    }

    @staticmethod
    def _format_amount(value):
        """Üretimdeki `_fmt` yerine sabit bir biçimlendirici.

        Para biçimlendirmesi bu testin konusu değil; ölçülen şey ÇEVİRİ.
        """
        return f"{value:,.2f}"

    def test_the_frequency_label_is_translated(self):
        from mixins.insights_mixin import recurring_candidate_title

        self.in_english()
        text = recurring_candidate_title(self.CANDIDATE)

        self.assertEqual(text, "Nakit  ·  monthly")
        self.assertNotIn("aylık", text)

    def test_the_candidate_name_is_never_translated(self):
        """Kullanıcı verisi koruması bozulmamış olmalı."""
        from mixins.insights_mixin import recurring_candidate_title

        self.in_english()
        text = recurring_candidate_title(dict(self.CANDIDATE, name="Ayarlar"))
        self.assertTrue(text.startswith("Ayarlar"), text)
        self.assertNotIn("Settings", text)

    def test_every_frequency_key_is_translated_by_the_title_builder(self):
        from mixins.insights_mixin import (
            _frequency_label, recurring_candidate_title,
        )

        self.in_english()
        for key in ("weekly", "biweekly", "monthly", "quarterly", "yearly"):
            with self.subTest(frequency=key):
                text = recurring_candidate_title(
                    dict(self.CANDIDATE, frequency=key)
                )
                self.assertNotIn(_frequency_label(key), text)

    def test_the_category_is_translated_in_the_detail_builder(self):
        from mixins.insights_mixin import recurring_candidate_detail
        from ui.i18n import tr

        self.in_english()
        text = recurring_candidate_detail(self.CANDIDATE, self._format_amount)

        # Karşılık sözlükten gelir (ürün kararı); sabitlenen şey kategorinin
        # İngilizce cümlede Türkçe KALMAMASI.
        self.assertIn(tr("Dijital Platformlar"), text)
        self.assertNotIn("Dijital Platformlar", text)
        self.assertNotIn("Kategori:", text)

    def test_turkish_mode_keeps_the_turkish_labels(self):
        from mixins.insights_mixin import recurring_candidate_title

        self.in_turkish()
        self.assertEqual(
            recurring_candidate_title(self.CANDIDATE), "Nakit  ·  aylık"
        )


class LedgerSourceLabelTest(_LanguageCase):
    """ÜRETİM YOLU: bakiye ayrıntısı ve defter kaynağı üreticileri."""

    RESULT = {
        "date": "2026-08-01",
        "savings_total": 1250.0,
        "basis": "snapshot",
    }

    @staticmethod
    def _format_amount(value):
        return f"{value:,.2f}"

    def test_the_basis_label_is_translated_by_the_builder(self):
        from mixins.history_mixin import balance_detail_text

        self.in_english()
        text = balance_detail_text(self.RESULT, self._format_amount)

        self.assertIn("Daily snapshot", text)
        self.assertNotIn("Günlük snapshot", text)

    def test_the_replay_basis_is_translated_too(self):
        from mixins.history_mixin import balance_detail_text

        self.in_english()
        text = balance_detail_text(
            dict(self.RESULT, basis="ledger"), self._format_amount
        )

        self.assertIn("Ledger replay", text)
        self.assertNotIn("Defter replay", text)

    def test_every_source_label_is_translated_by_the_builder(self):
        from mixins.history_mixin import _SOURCE_LABELS, ledger_source_text

        self.in_english()
        for key, turkish in _SOURCE_LABELS.items():
            with self.subTest(source=key):
                text = ledger_source_text(key, 3)
                self.assertNotIn(
                    turkish, text,
                    f"'{turkish}' İngilizce cümleye Türkçe giriyor",
                )
                self.assertTrue(text.endswith(" (3)"), text)

    def test_an_unknown_source_key_falls_back_to_itself(self):
        """Bilinmeyen kaynak anahtarı çökmemeli, olduğu gibi görünmeli."""
        from mixins.history_mixin import ledger_source_text

        self.in_english()
        self.assertEqual(ledger_source_text("bilinmeyen_kaynak", 1),
                         "bilinmeyen_kaynak (1)")

    def test_turkish_mode_keeps_the_turkish_basis(self):
        from mixins.history_mixin import balance_detail_text

        self.in_turkish()
        text = balance_detail_text(self.RESULT, self._format_amount)
        self.assertIn("Günlük snapshot", text)


class SecureOperationErrorTest(_LanguageCase):
    """`_secure_operation_error` başlıkları kontrollü uygulama metni."""

    HEADLINES = (
        "Backup oluşturulamadı",
        "Restore başarısız; mevcut veri korundu",
        "Migration geri alındı",
        "Kurtarma paketi oluşturulamadı",
        "Kurtarma paketi içe aktarılamadı",
        "Anahtar rotasyonu başlatılamadı",
        "Anahtar rotasyonu geri alındı",
    )

    def test_the_production_call_translates_the_message(self):
        """ÜRETİM YOLU: `_secure_operation_error` gerçekten çağrılıyor."""
        from unittest import mock

        from mixins.migration_mixin import MigrationMixin

        self.in_english()
        with mock.patch("mixins.migration_mixin.toast") as toast:
            MigrationMixin._secure_operation_error(
                "Backup oluşturulamadı", RuntimeError("boom")
            )
        shown = toast.call_args[0][0]
        self.assertEqual(
            shown,
            "Backup could not be created. Details were written to the "
            "application log.",
        )
        self.assertNotIn("oluşturulamadı", shown)

    def test_every_headline_has_an_english_entry(self):
        from ui.i18n import tr

        self.in_english()
        for headline in self.HEADLINES:
            with self.subTest(headline=headline):
                self.assertNotEqual(tr(headline), headline)


class RecurringQuestionTest(_LanguageCase):
    """ÜRETİM YOLU: `recurring_period_prompt` — diyaloğun çağırdığı üretici."""

    def test_both_prompts_are_fully_english(self):
        from mixins.transaction_mixin import (
            RECURRING_PERIOD_PROMPTS, recurring_period_prompt,
        )

        self.in_english()
        for is_income in (True, False):
            with self.subTest(is_income=is_income):
                text = recurring_period_prompt(is_income)
                question, detail = RECURRING_PERIOD_PROMPTS[is_income]
                self.assertNotIn(question, text)
                self.assertNotIn(detail, text)
                self.assertNotIn("seçilirse", text)

    def test_the_two_parts_are_separated_by_a_blank_line(self):
        """Şablonun yapısı da üretimden geliyor, testten değil."""
        from mixins.transaction_mixin import recurring_period_prompt

        self.in_english()
        self.assertEqual(len(recurring_period_prompt(True).split("\n\n")), 2)

    def test_turkish_mode_shows_the_turkish_pair(self):
        from mixins.transaction_mixin import (
            RECURRING_PERIOD_PROMPTS, recurring_period_prompt,
        )

        self.in_turkish()
        question, detail = RECURRING_PERIOD_PROMPTS[True]
        self.assertEqual(recurring_period_prompt(True),
                         f"{question}\n\n{detail}")


if __name__ == "__main__":
    unittest.main()
