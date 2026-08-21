"""`load_active_assets` içindeki "bugünkü değişim" hesabının hata dalı.

Bu dalın hiç testi yoktu. `_compute_today_liquid_delta` geniş bir
`except Exception` ile sarılıydı; ölçülen üç tipe
(`sqlite3.Error, OSError, ArchlenceError`) daraltıldı.

Dalın ÖNEMİ konumundan geliyor: hesap, varlık listesinin ekrana basıldığı
`_apply(cached, ...)` çağrısından ÖNCE yapılıyor. Buradan kaçan bir istisna
daemon thread'i öldürür — o zaman ne önbellek render'ı ne de final render
çalışır, `_asset_load_inflight` True'da kalır ve "Varlıklar hazırlanıyor…"
iskeleti KALICI olarak ekranda kalır. Yani bu dal, sessizce bir "sonsuz
spinner" muhafızı.
"""
import sqlite3
import threading
import unittest
from unittest import mock

from utils.errors import FinancialDataIntegrityError, KeyUnavailableError


class _ExistingCard:
    """Mevcut bir varlık kartı.

    Bunu bırakmak GEREKLİ: `load_active_assets` liste boşken KivyMD
    iskeletini (MDSpinner) kuruyor, o da çalışan bir MDApp istiyor. Zaten
    kart varken iskelet atlanıyor — testin ilgilendiği dal da bu.
    """
    _archlence_asset_id = 1


class _StubContainer:
    def __init__(self):
        self.children = (_ExistingCard(),)
        self.cleared = 0
        self.added = []

    def clear_widgets(self):
        self.cleared += 1

    def add_widget(self, widget):
        self.added.append(widget)


class _StubIds(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _StubRoot:
    def __init__(self):
        self.ids = _StubIds(active_assets_container=_StubContainer())


class TodayDeltaFailureTest(unittest.TestCase):
    """Bugünkü değişim hesaplanamasa da varlık listesi ÇİZİLMELİ."""

    def _app(self, delta_error):
        from mixins.asset_mixin import AssetMixin

        class App(AssetMixin):
            def __init__(self):
                self.root = _StubRoot()
                self.rendered = []
                self.finished = []
                self.summaries = []

            def _compute_today_liquid_delta(self):
                raise delta_error

            def render_active_assets_chunked(self, enriched, on_complete=None):
                self.rendered.append(list(enriched))
                if on_complete is not None:
                    on_complete()

            def _finish_active_asset_load(self, today_delta):
                self.finished.append(today_delta)

            def _update_cached_asset_summary(self, today_delta):
                self.summaries.append(today_delta)

        return App()

    def _run_load(self, app):
        """`load_active_assets`'i thread ve Clock olmadan senkron çalıştırır."""
        started = []

        class _SyncThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                started.append(True)
                self._target()

        assets = [{"id": 1, "asset_code": "BTC-USD"}]
        with mock.patch.object(threading, "Thread", _SyncThread), \
             mock.patch("kivy.clock.Clock.schedule_once",
                        lambda cb, _t=0: cb(0)), \
             mock.patch("database.db.get_all_assets", return_value=assets), \
             mock.patch("services.price_service.enrich_assets_from_cache",
                        return_value=assets), \
             mock.patch("services.price_service.fetch_asset_prices_async",
                        lambda a, callback=None, force_refresh=False:
                        callback(a) if callback else None):
            app.load_active_assets()
        self.assertTrue(started, "arka plan işi hiç başlamadı")

    def _assert_survives(self, error):
        app = self._app(error)
        self._run_load(app)

        self.assertTrue(app.rendered, f"{type(error).__name__}: liste çizilmedi")
        self.assertTrue(app.finished, f"{type(error).__name__}: yükleme bitmedi")

        self.assertIsNone(app.finished[-1])

    def test_sqlite_error_does_not_strand_the_asset_list(self):
        self._assert_survives(sqlite3.OperationalError("no such table"))

    def test_os_error_does_not_strand_the_asset_list(self):
        self._assert_survives(FileNotFoundError("veri dizini yok"))

    def test_archlence_error_does_not_strand_the_asset_list(self):
        self._assert_survives(
            FinancialDataIntegrityError("transactions", 1, "amount",
                                        reason=ValueError("bozuk")))

    def test_key_unavailable_does_not_strand_the_asset_list(self):
        self._assert_survives(KeyUnavailableError("anahtar yok"))


if __name__ == "__main__":
    unittest.main()
