"""Hesap ekleme akışındaki üç kullanıcı bildirimli hata.

1. TAB bir sonraki alana geçmek yerine metnin içine sekme karakteri yazıyordu
   (kullanıcı bunu "imleç 4 boşluk ilerledi" diye görüyor).
2. Kart numarası zorunlu görünüyordu; oysa kartsız hesap da olmalı.
3. "Henüz hesap eklenmedi…" etiketi hesap eklendikten sonra da ekranda
   kalıyordu.

Testler Kivy penceresi AÇMADAN çalışır: hepsi ya saf servis çağrısı ya da
widget özelliği kontrolü. `render_accounts` testi `_asset_data_cache`
snapshot'ını doğrudan kurar — fonksiyon zaten yalnızca oradan çizer ve cache
"ready" değilken iskelet gösterip erken döner.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class CardNumberIsOptionalTest(unittest.TestCase):
    """Kart numarası olmadan hesap açılabilmeli — hem kod hem ETİKET."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def test_checking_account_without_a_card_number(self):
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            name="Nakit", account_type="checking", initial_balance=250.0)
        self.assertIsNotNone(account_id)

    def test_credit_card_without_a_card_number(self):
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            name="Kart", account_type="credit_card",
            initial_balance=0.0, credit_limit=5000.0)
        self.assertIsNotNone(account_id)

    def test_hint_says_the_field_is_optional(self):
        """Asıl sorun koddaki bir engel DEĞİL, ipucunun sessizliğiydi:
        alan zaten opsiyoneldi ama etiket bunu söylemediği için kullanıcı
        zorunlu sanıyordu. Kesim günü alanı aynı kalıbı zaten kullanıyor.

        DİKKAT — `_t(...)` ÜZERİNDEN doğrulamayın: Türkçe modda `tr()`
        anahtarı olduğu gibi geri döndürür, dolayısıyla sözlükte ne yazarsa
        yazsın assert geçer (ilk yazımda bu tuzağa düşüldü, test dişsizdi).
        Doğrulama, mixin'in kullandığı GERÇEK etikete ve onun İngilizce
        karşılığına yapılır.
        """
        import inspect
        from mixins import account_mixin
        from ui.i18n import EN

        source = inspect.getsource(account_mixin.AccountMixin)
        self.assertIn(
            "Kart Numarası (opsiyonel", source,
            "arayüzdeki etiket alanın opsiyonel olduğunu söylemeli",
        )

        english = EN.get(
            "Kart Numarası (opsiyonel — kartsız hesap için boş bırakın)")
        self.assertIsNotNone(english, "İngilizce çeviri eksik")
        self.assertIn("optional", english.casefold())


class _FocusStub:
    """`chain_focus`'un dokunduğu üç özniteliği taşıyan asgari nesne.

    KivyMD widget'ı BİLEREK kullanılmıyor: `chain_focus` saf bağlama
    mantığı ve gerçek bir `MDTextField` kurmak çalışan bir `Window`
    istiyor. Stub, testi hem hızlı hem de headless'ta çalışır kılıyor.
    """

    def __init__(self):
        self.write_tab = True
        self.focus_next = None
        self.focus_previous = None


class ChainFocusTest(unittest.TestCase):
    """TAB zincirinin bağlama mantığı — Kivy gerektirmez."""

    def test_links_fields_into_a_ring(self):
        import ui.theme as ftheme

        first, second, third = _FocusStub(), _FocusStub(), _FocusStub()
        ftheme.chain_focus([first, second, third])

        self.assertIs(first.focus_next, second)
        self.assertIs(second.focus_next, third)
        self.assertIs(third.focus_next, first, "sondan sonra başa dönmeli")
        self.assertIs(first.focus_previous, third)

    def test_disables_writing_a_literal_tab(self):
        """Kullanıcının gördüğü '4 boşluk' semptomu tam olarak buydu."""
        import ui.theme as ftheme

        fields = [_FocusStub(), _FocusStub()]
        ftheme.chain_focus(fields)
        self.assertTrue(all(not f.write_tab for f in fields))

    def test_skips_none_entries(self):
        """Çağıran koşullu alanları elemek zorunda kalmasın."""
        import ui.theme as ftheme

        first, second = _FocusStub(), _FocusStub()
        ftheme.chain_focus([first, None, second, None])

        self.assertIs(first.focus_next, second)
        self.assertIs(second.focus_next, first)

    def test_single_field_still_stops_tab_from_writing(self):
        """Halka anlamsız ama sekme yazılması yine de engellenmeli."""
        import ui.theme as ftheme

        only = _FocusStub()
        ftheme.chain_focus([only])
        self.assertFalse(only.write_tab)
        self.assertIsNone(only.focus_next)


class TabWithRealWidgetsTest(unittest.TestCase):
    """Gerçek MDTextField ile uçtan uca TAB davranışı.

    Headless pakette atlanır; yerel geliştirmede ve pencereli ortamda
    `make_text_field`'in varsayılanını ve gerçek tuş olayını doğrular.
    """

    @classmethod
    def setUpClass(cls):
        """Pencere kontrolü BURADA, modül düzeyinde DEĞİL.

        `@skipUnless(...)` dekoratörünün ifadesi IMPORT anında çalışır;
        orada `kivy.core.window`'u içeri almak Kivy'nin metrik/pencere
        başlatmasını test toplama aşamasında tetikleyip TÜM paketi
        kırıyordu (125 hata). Tembel kontrol bu yan etkiyi önlüyor.
        """
        from kivymd.app import MDApp

        running = MDApp.get_running_app()
        if running is not None:
            cls.app = running
            return
        try:
            cls.app = MDApp()
        except Exception as exc:  # headless: Window None -> AttributeError
            raise unittest.SkipTest(
                f"gerçek Kivy Window gerekiyor: {exc!r}") from exc

    def test_make_text_field_disables_writing_a_literal_tab(self):
        import ui.theme as ftheme

        field = ftheme.make_text_field("Test", self.app.theme_cls)
        self.assertFalse(field.write_tab)

    def test_pressing_tab_moves_focus_and_leaves_the_text_alone(self):
        from kivymd.uix.textfield import MDTextField
        import ui.theme as ftheme

        first, second = MDTextField(), MDTextField()
        ftheme.chain_focus([first, second])
        first.focus = True
        first.keyboard_on_key_down(None, (9, "tab"), "\t", [])

        self.assertFalse(first.focus)
        self.assertTrue(second.focus)
        self.assertEqual(first.text, "", "metne sekme karakteri yazılmamalı")


class EmptyStateDisappearsAfterAddingAnAccountTest(unittest.TestCase):
    """"Henüz hesap eklenmedi…" etiketi eklendikten sonra kaldırılmıyordu.

    Kök neden: temizlik döngüsü yalnızca `_archlence_loading` işaretli
    widget'ları siliyordu; boş-durum etiketinin hiçbir işareti yoktu, bu
    yüzden hesap kartlarının altında asılı kalıyordu.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    class _Box:
        """`render_accounts`'un konteynerden istediği asgari arayüz.

        Gerçek `MDBoxLayout` KULLANILMIYOR: KivyMD widget'ları çalışan bir
        `MDApp`/`Window` istiyor, headless test paketinde ikisi de yok.
        Test edilen şey zaten temizlik MANTIĞI — hangi çocuğun kaldırıldığı —
        KivyMD'nin çizim davranışı değil.
        """

        def __init__(self):
            self.children = []

        def add_widget(self, widget, *args, **kwargs):
            widget.parent = self
            self.children.insert(0, widget)

        def remove_widget(self, widget):
            if widget in self.children:
                self.children.remove(widget)
                widget.parent = None

        def clear_widgets(self):
            for child in list(self.children):
                self.remove_widget(child)

    class _Label:
        """`MDLabel` yerine geçen yer tutucu; yalnızca `text` taşır."""

        def __init__(self, **kwargs):
            self.text = kwargs.get("text", "")
            self.parent = None

        def bind(self, **kwargs):
            pass

        def setter(self, name):
            return lambda *args: None

    def _app_with_containers(self):
        """`render_accounts` için gereken asgari sahte `self`."""
        from mixins.account_mixin import AccountMixin

        cards = self._Box()
        accounts = self._Box()

        class _Ids(dict):
            def __getattr__(self, name):
                try:
                    return self[name]
                except KeyError as exc:
                    raise AttributeError(name) from exc

        class _Root:
            pass

        root = _Root()
        root.ids = _Ids(cards_container=cards, accounts_container=accounts)

        outer = self

        class _App(AccountMixin):
            def __init__(self):
                self.root = root


                placeholder = outer._Box()
                accounts.add_widget(placeholder)
                self._active_assets_bento = placeholder
                self._active_assets_refresh_event = object()

            def _update_account_summary(self, summary):
                pass

            def _apply_active_assets_result(self, result):
                pass

            def _render_account_widget(self, acc, cards_box, accounts_box,
                                       recent, current=None):
                widget = current or outer._Box()
                widget._archlence_account_id = acc["id"]
                if getattr(widget, "parent", None) is None:
                    accounts_box.add_widget(widget)
                return widget

        return _App(), accounts

    def _empty_labels(self, container):
        from ui.i18n import tr as _t
        wanted = _t("Henüz hesap eklenmedi — yukarıdaki butondan ekleyebilirsin.")
        return [child for child in container.children
                if getattr(child, "text", None) == wanted]

    def _set_snapshot(self, accounts):
        import services.asset_service as asset_service
        asset_service._asset_data_cache = {
            "summary": {"cash": 0, "card_debt": 0, "net": 0},
            "accounts": accounts,
            "recent": {},
            "active_assets_result": None,
            "ready": True,
        }
        asset_service._account_cache_stale = False

    def test_label_shows_when_empty_then_goes_away_once_an_account_exists(self):
        app, accounts_box = self._app_with_containers()

        self._set_snapshot([])
        with mock.patch("kivymd.uix.label.MDLabel", self._Label):
            app.render_accounts()
        self.assertEqual(
            len(self._empty_labels(accounts_box)), 1,
            "hesap yokken yönlendirme metni görünmeli",
        )

        self._set_snapshot([{
            "id": 1, "name": "Nakit", "balance": 250.0,
            "account_type": "checking", "credit_limit": 0,
            "statement_date": None, "masked_number": None,
            "network_logo": None, "has_card_number": False,
        }])
        with mock.patch("kivymd.uix.label.MDLabel", self._Label):
            app.render_accounts()
        self.assertEqual(
            len(self._empty_labels(accounts_box)), 0,
            "hesap eklendikten sonra etiket KALDIRILMALI — asıl hata buydu",
        )


if __name__ == "__main__":
    unittest.main()
