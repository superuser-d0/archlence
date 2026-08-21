"""Hesaplar görünümündeki 60 saniyelik arka plan tazeleme döngüsünün
yaşam döngüsü. Denetimde bulunan hata: `Clock.schedule_interval` bir kez
kuruluyor ve HİÇBİR YERDE iptal edilmiyordu — sürecin ömrü boyunca, hangi
ekran görünür olursa olsun çalışmaya devam ediyordu.

Her iki koruma da saf Python: `_silent_background_refresh` ve
`stop_active_assets_refresh` gerçek bir Kivy penceresi olmadan, sahte bir
`self` ile doğrudan çağrılabilir (aynı kalıp: tests/test_pin_lazy_migration.py).
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class _FakeBento:
    def __init__(self, parent):
        self.parent = parent


class SelfCancelWhenScreenGoneTest(unittest.TestCase):
    """Ekran yok edildiğinde döngü kendini iptal etmeli (callback False
    döndürünce Kivy onu zamanlayıcı listesinden düşürür)."""

    def setUp(self):
        from mixins.account_mixin import AccountMixin
        self.refresh = AccountMixin._silent_background_refresh

    def test_returns_false_when_bento_widget_was_never_created(self):
        app = mock.Mock()
        app._active_assets_bento = None
        result = self.refresh(app, 0)
        self.assertIs(result, False, "döngü kendini iptal etmeliydi")
        self.assertIsNone(app._active_assets_refresh_event)

    def test_returns_false_when_bento_was_removed_from_the_tree(self):
        """Ekran yıkıldığında widget'ın parent'ı None olur — asıl senaryo."""
        app = mock.Mock()
        app._active_assets_bento = _FakeBento(parent=None)
        result = self.refresh(app, 0)
        self.assertIs(result, False)
        self.assertIsNone(app._active_assets_refresh_event)

    def test_keeps_running_while_the_view_is_still_mounted(self):
        """Görünüm hâlâ ağaçtayken döngü DURMAMALI — aksi hâlde düzeltme,
        özelliğin kendisini kapatmış olurdu."""
        app = mock.Mock()
        app._active_assets_bento = _FakeBento(parent=object())
        with mock.patch("services.asset_service.start_data_warmup") as warmup:
            result = self.refresh(app, 0)
        self.assertNotEqual(result, False, "çalışmaya devam etmeliydi")
        warmup.assert_called_once()


class ExplicitStopTest(unittest.TestCase):
    def setUp(self):
        from mixins.account_mixin import AccountMixin
        self.stop = AccountMixin.stop_active_assets_refresh

    def test_cancels_and_clears_a_live_event(self):
        app = mock.Mock()
        event = mock.Mock()
        app._active_assets_refresh_event = event
        self.stop(app)
        event.cancel.assert_called_once()
        self.assertIsNone(app._active_assets_refresh_event)

    def test_is_safe_when_no_event_was_ever_scheduled(self):
        """Hesaplar sekmesi hiç açılmadan uygulama kapatılırsa (on_stop yine
        çağrılır) hata vermemeli."""
        app = mock.Mock()
        app._active_assets_refresh_event = None
        self.stop(app)
        self.assertIsNone(app._active_assets_refresh_event)


class AppShutdownHookTest(unittest.TestCase):
    def test_on_stop_stops_the_refresh_loop(self):
        import main
        app = mock.Mock()
        main.ArchlenceApp.on_stop(app)
        app.stop_active_assets_refresh.assert_called_once()

    def test_on_stop_never_raises_even_if_cancelling_fails(self):
        """Kapanış yolu hiçbir koşulda istisna fırlatmamalı."""
        import main
        app = mock.Mock()
        app.stop_active_assets_refresh.side_effect = RuntimeError("beklenmedik")
        main.ArchlenceApp.on_stop(app)


if __name__ == "__main__":
    unittest.main()
