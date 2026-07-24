import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "mock")
os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
os.environ.setdefault("KIVY_DPI", "96")


class _Ids(dict):
    def __getattr__(self, name):
        return self[name]


class _Store:
    def clear(self):
        return None


class ResetFlowTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        fd, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.config_path)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()

        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        for path in (self.db_path, self.config_path):
            if os.path.exists(path):
                os.unlink(path)

    def test_factory_reset_invalidates_and_rewarms_only_seed_accounts(self):
        from database.db import get_connection
        from kivy.storage.jsonstore import JsonStore
        from main import ArchlenceApp
        from services import asset_service

        conn = get_connection()
        conn.execute("DELETE FROM accounts")
        conn.executemany(
            """INSERT INTO accounts
               (name,type,balance,account_type,credit_limit,statement_date)
               VALUES(?,?,?,?,?,?)""",
            [
                ("Yapıkredi", "credit", -500, "credit_card", 20000, 15),
                ("İş Bankası", "bank", 36710.01, "checking", 0, None),
            ],
        )
        conn.commit()
        conn.close()
        asset_service.refresh_account_cache_snapshot()
        self.assertEqual(
            {row["name"] for row in asset_service._asset_data_cache["accounts"]},
            {"Yapıkredi", "İş Bankası"},
        )

        # MDApp.__init__ gerçek Window ister; bu test yalnız reset metodunun
        # veri/cache sözleşmesini çalıştırdığı için EventDispatcher nesnesini
        # pencere oluşturmadan kurmak yeterlidir.
        app = ArchlenceApp.__new__(ArchlenceApp)
        app.language = "tr"
        app.store = _Store()
        app.config_store = JsonStore(self.config_path)
        app.config_store.put("display", style="Dark")
        app.config_store.put("language", code="tr")
        app.config_store.put("theme", name="premium")
        app.config_store.put(
            "security", pin_hash="old", salt="old", is_set=True
        )
        app.reset_input = SimpleNamespace(text="SİL")
        app.root = SimpleNamespace(ids=_Ids(
            screen_manager=SimpleNamespace(current="accounts")
        ))
        app.refresh_dashboard_data = mock.Mock()
        app.render_accounts = mock.Mock()
        app._assets_cache = [{"id": 99}]
        app._liquid_balance_cache = 36710.01
        app._asset_ui_loaded_at = time.monotonic()
        app._asset_load_inflight = True
        app._recurring_candidates = [{"name": "Eski aday"}]

        ready_states = []
        original_warmup = asset_service.start_data_warmup

        def observed_warmup(callback=None):
            ready_states.append(asset_service._asset_data_cache["ready"])
            return original_warmup(callback)

        with (
            mock.patch(
                "services.asset_service.start_data_warmup",
                side_effect=observed_warmup,
            ),
            mock.patch(
                "services.asset_service.fetch_active_non_try_total",
                side_effect=lambda callback: callback({
                    "total": 0.0, "asset_count": 0, "priced_count": 0,
                    "cached_count": 0, "complete": True,
                }),
            ),
            mock.patch("main.toast"),
        ):
            app.delete_all_data()

        deadline = time.monotonic() + 3
        while (
            not asset_service._asset_data_cache["ready"]
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)

        self.assertEqual(ready_states, [False])
        self.assertTrue(asset_service._asset_data_cache["ready"])
        self.assertEqual(
            {row["name"] for row in asset_service._asset_data_cache["accounts"]},
            {"Nakit", "Banka", "Kredi Kartı"},
        )
        self.assertNotIn(
            "Yapıkredi",
            {row["name"] for row in asset_service._asset_data_cache["accounts"]},
        )
        self.assertEqual(app._assets_cache, [])
        self.assertEqual(app._liquid_balance_cache, 0.0)
        self.assertEqual(app._recurring_candidates, [])
        self.assertFalse(app._asset_load_inflight)
        self.assertEqual(app._asset_ui_loaded_at, 0.0)
        self.assertFalse(app.config_store.exists("security"))
        self.assertEqual(app.config_store.get("display")["style"], "Dark")
        self.assertEqual(app.config_store.get("language")["code"], "tr")
        self.assertEqual(app.config_store.get("theme")["name"], "premium")
        self.assertEqual(app.root.ids.screen_manager.current, "pin_setup")


if __name__ == "__main__":
    unittest.main()
