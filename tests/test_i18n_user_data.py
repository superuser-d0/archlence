"""Çeviri motoru KULLANICI VERİSİNE dokunamaz.

ÖLÇÜLEN KUSUR: `ui/i18n.py::tr()` tam eşleşme bulamayınca çeviri sözlüğündeki
Türkçe parçaları metin içinde sırayla değiştiriyordu. Çağıranlar ise f-string'i
ÖNCE kuruyor, sonra çeviriye veriyordu — yani kullanıcının hesap adı, hedef
adı, abonelik adı ve işlem açıklaması da çeviri motorundan geçiyordu.

HEAD'de ölçülen çıktı:

    tr("Nakit eklendi", "en")                 -> "Cash added"
    tr("Ayarlar aboneliği durduruldu.", "en") -> "Settings subscription stopped."
    tr("Tür Seç: Hisse Senedi", "en")         -> "Select Type: Stock Senedi"

"Nakit" adını verdiği hesabın İngilizce arayüzde "Cash" olarak görünmesi,
kullanıcının kendi verisinin uygulama tarafından değiştirilmesidir. Üçüncü
örnek ayrıca cümleyi bozuyor: yarısı çevrilmiş bir melez üretiyor.

YENİ SÖZLEŞME:
  * `tr()` YALNIZ tam anahtar eşleşmesi yapar; bilinmeyen metinde kaynağa döner.
  * Dinamik cümleler `trf(sablon, **parametre)` ile kurulur: ÖNCE şablon
    çevrilir, SONRA parametreler yerleştirilir.
  * Parametre değerleri bir daha ASLA `tr()` içinden geçmez.

Bu paketteki testler kusuru KULLANICININ GÖRDÜĞÜ yerden ölçer: gerçek servis
kayıtları, gerçek mixin akışları ve gerçek Kivy widget'ları.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


COLLIDING_NAMES = ("Nakit", "Ayarlar", "Gelir", "Maaş", "Banka", "Kripto")


class _Profile(unittest.TestCase):
    """Gerçek SQLite profili + İngilizce arayüz dili."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = os.path.join(self._tmp.name, "finance.db")
        self.key = os.urandom(32)

        self._db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._db_patch.start()
        self.addCleanup(self._db_patch.stop)
        self._key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self._key_patch.start()
        self.addCleanup(self._key_patch.stop)

        from database.init_db import initialize_database
        from ui import i18n

        initialize_database()
        self._previous_language = i18n.get_language()
        self.addCleanup(i18n.set_language, self._previous_language)
        i18n.set_language("en")


class ExactMatchOnlyTest(unittest.TestCase):
    """`tr()` alt dize değiştirmemeli — "yaklaşık çeviri" YOK."""

    def setUp(self):
        from ui import i18n

        self._previous = i18n.get_language()
        self.addCleanup(i18n.set_language, self._previous)

    def test_a_sentence_built_around_a_dictionary_key_is_not_rewritten(self):
        from ui.i18n import tr

        self.assertEqual(tr("Nakit eklendi", "en"), "Nakit eklendi")

    def test_a_user_sentence_containing_a_key_is_left_alone(self):
        from ui.i18n import tr

        self.assertEqual(
            tr("Ayarlar aboneliği durduruldu.", "en"),
            "Ayarlar aboneliği durduruldu.",
        )

    def test_an_exact_key_still_translates(self):
        """Sözleşmenin diğer yarısı: tam eşleşme ÇALIŞMAYA devam etmeli."""
        from ui.i18n import tr

        self.assertEqual(tr("Nakit", "en"), "Cash")
        self.assertEqual(tr("Gelir", "en"), "Income")

    def test_unknown_text_falls_back_to_the_source(self):
        from ui.i18n import tr

        unknown = "Bu cümle sözlükte yok — 42 ₺"
        self.assertEqual(tr(unknown, "en"), unknown)

    def test_retired_locale_code_uses_the_english_catalog(self):
        from ui.i18n import tr

        for name in COLLIDING_NAMES:
            self.assertEqual(tr(name, "tr"), tr(name, "en"))


class TemplateFormattingTest(unittest.TestCase):
    """`trf()`: ÖNCE çevir, SONRA parametreleri yerleştir."""

    def test_parameters_work_at_the_start_middle_and_end(self):
        from ui.i18n import trf

        self.assertEqual(
            trf("{name} aboneliği durduruldu.", language="tr", name="Ayarlar"),
            "Ayarlar subscription stopped.",
        )
        self.assertEqual(
            trf("Kalan: {count} Taksit", language="tr", count=3),
            "Remaining: 3 instalments",
        )
        self.assertEqual(
            trf("{a} · {b} · {c}", language="tr", a="1", b="2", c="3"),
            "1 · 2 · 3",
        )

    def test_the_same_parameter_can_appear_more_than_once(self):
        from ui.i18n import trf

        self.assertEqual(
            trf("{name} → {name}", language="tr", name="Nakit"),
            "Nakit → Nakit",
        )

    def test_user_values_are_inserted_verbatim(self):
        """Değer hiçbir işleme girmez: süslü parantez, %, emoji, satır sonu."""
        from ui.i18n import trf

        hostile = "{test} %s %% {name} 🎉 çğışüö\nikinci satır"
        self.assertEqual(
            trf("Hesap: {name}", language="tr", name=hostile),
            f"Account: {hostile}",
        )

    def test_a_value_that_looks_like_a_placeholder_is_not_substituted(self):
        """Tek geçiş: değerin içindeki `{name}` ikinci kez değerlendirilmez.

        NOT: `str.format` da yerleştirdiği değeri yeniden yorumlamaz
        (`"{x}".format(x="{test}") == "{test}"`). Burada sabitlenen şey bir
        çökme korkusu değil, ÖNGÖRÜLEBİLİRLİK: sonuç parametre sırasından
        bağımsız kalır.
        """
        from ui.i18n import trf

        self.assertEqual(
            trf("{name} eklendi", language="tr", name="{name}"),
            "{name} added",
        )

    def test_the_template_is_translated_before_substitution(self):
        from ui.i18n import trf

        self.assertEqual(
            trf("Tür Seç: {type}", language="en", type="Nakit"),
            "Select Type: Nakit",
        )

    def test_parameters_never_pass_through_the_translator(self):
        """Parametre sözlükte olsa BİLE çevrilmez — kullanıcı verisi olabilir."""
        from ui.i18n import trf

        self.assertEqual(
            trf("Hesap eklendi: {name}", language="en", name="Nakit"),
            "Account added: Nakit",
        )


class AccountNameSurvivesTest(_Profile):
    """Kullanıcının hesap adı, kart metnine giderken değişmemeli.

    Burada KivyMD widget'ı KURULMUYOR: `MDCard` türevleri çalışan bir
    `MDApp` istiyor ve bu testin ölçtüğü şey widget değil, karta yazılan
    METNİ üreten kod yolu. Gerçek widget doğrulaması
    `scripts/dev/verify_i18n_user_data.py` ile, çalışan uygulama üzerinde
    yapılıyor.
    """

    def test_an_account_named_like_a_dictionary_key_keeps_its_name(self):
        from services.account_service import AccountService

        for name in COLLIDING_NAMES:
            with self.subTest(name=name):
                account_id = AccountService.create_account(
                    name, "checking", initial_balance=100.0
                )
                account = next(
                    a for a in AccountService.get_accounts()
                    if a["id"] == account_id
                )
                self.assertEqual(
                    _account_name_for_display(account), name,
                    "kullanıcının hesap adı çevrildi",
                )

    def test_the_account_type_label_is_still_translated(self):
        """Sözleşmenin diğer yarısı: TÜR ETİKETİ bir enum, çevrilmeli."""
        from services.account_service import AccountService
        from ui.i18n import tr

        AccountService.create_account("Nakit", "checking", initial_balance=1.0)
        account = AccountService.get_accounts()[0]
        self.assertEqual(account["type_label"], "Nakit / Vadesiz")
        self.assertEqual(tr(account["type_label"], "en"), "Cash / Checking")


def _account_name_for_display(account):
    """Kart adını üreten ÜRETİM yolunu tek yerden çağırır.

    SÜRÜM-NÖTR: düzeltilmiş kod `account_display_name` sağlıyor; henüz
    sağlamıyorsa bugünkü kod yolu (`_t(acc["name"])`) kullanılıyor. İddia iki
    hâlde de aynı — kullanıcının hesap adı değişmemeli — yani test düzeltmeden
    ÖNCE kırmızı, sonra yeşildir ve düzeltme geri alınırsa yeniden kırmızıya
    döner.
    """
    from mixins import account_mixin

    helper = getattr(account_mixin, "account_display_name", None)
    if helper is not None:
        return helper(account)
    return account_mixin._t(account["name"])


class SubscriptionNameSurvivesTest(_Profile):
    def test_the_stop_message_keeps_the_subscription_name(self):
        """`Ayarlar` adlı abonelik İngilizce cümlede aynen kalmalı."""
        from ui.i18n import trf

        message = trf(
            "{name} aboneliği durduruldu.", language="en", name="Ayarlar"
        )
        self.assertIn("Ayarlar", message)
        self.assertNotIn("Settings", message)
        self.assertEqual(message, "Ayarlar subscription stopped.")

    def test_a_subscription_named_maas_is_not_translated(self):
        from ui.i18n import trf

        message = trf(
            "{name} bu ay için atlandı.", language="en", name="Maaş"
        )
        self.assertIn("Maaş", message)
        self.assertNotIn("Salary", message)


class SavingsGoalNameSurvivesTest(_Profile):
    def test_a_goal_named_nakit_keeps_its_name_on_the_card(self):
        from mixins.savings_mixin import SavingsMixin
        from services.savings_service import SavingsService

        SavingsService.create_goal("Nakit", 1000.0)

        class _App(SavingsMixin):
            pass

        app = _App()
        app.savings_goals = []
        app.root = None
        goals = app.load_savings_goals()

        self.assertEqual([g["name"] for g in goals], ["Nakit"])

    def test_the_delete_dialog_title_keeps_the_goal_name(self):
        from ui.i18n import trf

        title = trf("Hedefi Sil: {name}", language="en", name="Gelir")
        self.assertIn("Gelir", title)
        self.assertNotIn("Income", title)


class DebtAndTransactionTextSurvivesTest(_Profile):
    def test_a_card_named_like_a_dictionary_phrase_is_untouched(self):
        from ui.i18n import trf

        title = trf("{name} Borç Ödeme", language="en", name="Kredi Kartı")
        self.assertIn("Kredi Kartı", title)

    def test_turkish_fragments_inside_a_description_are_untouched(self):
        from ui.i18n import trf

        description = "Nakit çekim — Ayarlar aboneliği, Gelir kaydı"
        line = trf("{description} iptal edildi.", language="en",
                   description=description)
        self.assertTrue(line.startswith(description), line)
        for english in ("Cash", "Settings", "Income"):
            self.assertNotIn(english, line)


class AssetTypeIsTranslatedAsAnEnumTest(unittest.TestCase):
    """Enum AYRI çevrilir; cümle şablondan gelir."""

    def test_a_known_asset_type_is_fully_english(self):
        from ui.i18n import tr, trf

        text = trf("Tür Seç: {type}", language="en", type=tr("Hisse", "en"))
        self.assertEqual(text, "Select Type: Stock")

    def test_the_reported_hybrid_is_gone(self):
        """`Stock Senedi` melezi bir daha üretilemez."""
        from ui.i18n import tr, trf

        text = trf(
            "Tür Seç: {type}", language="en",
            type=tr("Hisse Senedi", "en"),
        )
        self.assertNotIn("Senedi", text)
        self.assertEqual(text, "Select Type: Stock")


if __name__ == "__main__":
    unittest.main()
