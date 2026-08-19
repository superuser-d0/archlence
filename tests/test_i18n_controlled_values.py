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
    """"Yeni <tür> Ekle" başlığı — üretimdeki ifadenin aynısı."""

    def _title(self, selected_type):
        """`show_asset_form`un başlığı kurduğu İFADENİN kendisi.

        Diyaloğun tamamını kurmak çalışan bir `MDApp` ister; ölçülen şey
        başlık metnini üreten çağrı, widget değil. İfade üretim kodundan
        birebir alınmıştır ve `test_the_dialog_title_expression_matches_
        production` onun kaynakla aynı kaldığını sabitler.
        """
        from mixins.asset_mixin import _t, _tf

        return _tf("Yeni {asset_selected_type} Ekle",
                   asset_selected_type=_t(selected_type))

    def test_the_title_is_fully_english(self):
        self.in_english()
        self.assertEqual(self._title("Altın"), "Add New Gold")
        self.assertEqual(self._title("Hisse"), "Add New Stock")

    def test_the_title_stays_turkish_in_turkish(self):
        self.in_turkish()
        self.assertEqual(self._title("Altın"), "Yeni Altın Ekle")

    def test_the_dialog_title_expression_matches_production(self):
        """Bu testin taklit ettiği ifade üretimde GERÇEKTEN kullanılıyor mu?

        Taklit testinin kör noktası tam olarak budur: üretim değişirse
        taklit sessizce yalan söylemeye başlar. Kaynak metin kontrolü o
        sessizliği kapatıyor.
        """
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "mixins" / "asset_mixin.py").read_text(encoding="utf-8")
        self.assertIn(
            'title=_tf("Yeni {asset_selected_type} Ekle",\n'
            '                    asset_selected_type=_t(self._asset_selected_type)),',
            source,
        )


class GoldTypeSelectionTest(_LanguageCase):
    """Altın türü: ilk gösterim ve seçim sonrası metin."""

    def _initial_label(self):
        from mixins.asset_mixin import AssetMixin, _t, _tf

        first = AssetMixin._GOLD_TYPES[0][0]
        return _tf("Altın Türü: {label}", label=_t(first))

    def _selected_label(self, label):
        from mixins.asset_mixin import _t, _tf

        return _tf("Altın Türü: {label}", label=_t(label))

    def test_the_first_gold_type_is_translated(self):
        self.in_english()
        self.assertEqual(self._initial_label(), "Gold Type: Gram Gold")

    def test_every_gold_type_is_translated(self):
        from mixins.asset_mixin import AssetMixin

        self.in_english()
        for label, _symbol, _friendly in AssetMixin._GOLD_TYPES:
            with self.subTest(gold_type=label):
                rendered = self._selected_label(label)
                self.assertTrue(rendered.startswith("Gold Type: "), rendered)
                self.assertNotIn("Altın", rendered)

    def test_turkish_mode_keeps_the_turkish_gold_label(self):
        self.in_turkish()
        self.assertEqual(self._initial_label(), "Altın Türü: Gram Altın")

    def test_the_gold_expressions_match_production(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "mixins" / "asset_mixin.py").read_text(encoding="utf-8")
        self.assertIn(
            'text=_tf("Altın Türü: {label}", label=_t(gold_types[0][0])),',
            source,
        )
        self.assertIn(
            'gold_btn.text = _tf("Altın Türü: {label}", label=_t(label))',
            source,
        )


class RecurringCandidateTest(_LanguageCase):
    """Abonelik adayı kartı: sıklık ve kategori kontrollü etiket."""

    CANDIDATE = {
        "name": "Nakit",            # KULLANICI VERİSİ — çevrilmemeli
        "frequency": "monthly",
        "category": "Dijital Platformlar",
        "average_amount": 100.0,
        "monthly_cost": 100.0,
        "occurrences": 3,
        "last_seen": "2026-08-01",
    }

    def test_the_frequency_label_is_translated(self):
        from mixins.insights_mixin import _frequency_label, _t, _tf

        self.in_english()
        text = _tf("{name}  ·  {frequency}",
                   name=self.CANDIDATE["name"],
                   frequency=_t(_frequency_label(self.CANDIDATE["frequency"])))

        self.assertEqual(text, "Nakit  ·  monthly")
        self.assertNotIn("aylık", text)

    def test_every_frequency_key_has_an_english_label(self):
        from mixins.insights_mixin import _frequency_label
        from ui.i18n import tr

        self.in_english()
        for key in ("weekly", "biweekly", "monthly", "quarterly", "yearly"):
            with self.subTest(frequency=key):
                turkish = _frequency_label(key)
                english = tr(turkish)
                self.assertNotEqual(
                    english, turkish,
                    f"'{turkish}' İngilizce karşılığı olmadan cümleye giriyor",
                )

    def test_the_candidate_name_is_never_translated(self):
        """Kullanıcı verisi koruması bozulmamış olmalı."""
        from mixins.insights_mixin import _frequency_label, _t, _tf

        self.in_english()
        text = _tf("{name}  ·  {frequency}",
                   name="Ayarlar",
                   frequency=_t(_frequency_label("weekly")))
        self.assertTrue(text.startswith("Ayarlar"), text)

    def test_the_category_is_translated_as_a_label(self):
        from mixins.insights_mixin import _t, _tf

        self.in_english()
        text = _tf(
            "{amount} × {occurrences} kez  →  ayda {amount_1}\n"
            "Kategori: {category}  ·  Son: {last_seen}",
            amount="100,00", occurrences=3, amount_1="100,00",
            category=_t("Dijital Platformlar"), last_seen="2026-08-01",
        )
        # Karşılık sözlükten gelir (ürün kararı), test onu uydurmaz —
        # sabitlenen şey "kategori İngilizce cümlede Türkçe kalmıyor".
        self.assertIn(_t("Dijital Platformlar"), text)
        self.assertNotIn("Dijital Platformlar", text)

    def test_the_production_expressions_translate_their_labels(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "mixins" / "insights_mixin.py").read_text(encoding="utf-8")
        self.assertIn('frequency=_t(_frequency_label(cand["frequency"]))', source)
        self.assertIn('category=_t(cand["category"]),', source)


class LedgerSourceLabelTest(_LanguageCase):
    """Bakiye geçmişi: hesap tabanı ve kaynak etiketleri."""

    def test_the_basis_label_is_translated(self):
        from ui.i18n import tr

        self.in_english()
        self.assertEqual(tr("Günlük snapshot"), "Daily snapshot")
        self.assertEqual(tr("Defter replay"), "Ledger replay")

    def test_every_source_label_has_an_english_entry(self):
        from mixins.history_mixin import _SOURCE_LABELS
        from ui.i18n import tr

        self.in_english()
        for key, turkish in _SOURCE_LABELS.items():
            with self.subTest(source=key):
                self.assertNotEqual(
                    tr(turkish), turkish,
                    f"'{turkish}' İngilizce cümleye Türkçe giriyor",
                )

    def test_the_production_expressions_translate_their_labels(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "mixins" / "history_mixin.py").read_text(encoding="utf-8")
        self.assertIn("source=_t(_SOURCE_LABELS.get(source, source))", source)
        self.assertIn('value=_t("Günlük snapshot")', source)


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
    """Tekrarlayan işlem diyaloğunun sabit soru/açıklama çifti."""

    PAIRS = (
        ("Bu ayki gelir hesaba eklensin mi?",
         "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gelir hemen, "
         "gelmediyse seçilen günde eklenir."),
        ("Bu ayki gider hesaptan düşülsün mü?",
         "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gider hemen, "
         "gelmediyse seçilen günde düşülür."),
    )

    def test_both_pairs_are_fully_english(self):
        from ui.i18n import tr, trf

        self.in_english()
        for question, detail in self.PAIRS:
            with self.subTest(question=question):
                text = trf("{question}\n\n{detail}",
                           question=tr(question), detail=tr(detail))
                self.assertNotIn("seçilirse", text)
                self.assertNotIn("Bu ayki", text)

    def test_the_production_expression_translates_both(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "mixins" / "transaction_mixin.py").read_text(encoding="utf-8")
        self.assertIn("question=_t(question), detail=_t(detail)", source)


if __name__ == "__main__":
    unittest.main()
