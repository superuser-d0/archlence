import unittest
from types import SimpleNamespace
from unittest import mock


class DashboardChartCacheTest(unittest.TestCase):
    def setUp(self):
        import services.asset_service as asset_service

        self.asset_service = asset_service
        self.original_revision = asset_service._financial_data_revision
        self.original_cache = asset_service._asset_data_cache
        self.original_stale = asset_service._account_cache_stale
        self.original_generation = asset_service._warmup_generation
        asset_service._financial_data_revision = 0

    def tearDown(self):
        self.asset_service._financial_data_revision = self.original_revision
        self.asset_service._asset_data_cache = self.original_cache
        self.asset_service._account_cache_stale = self.original_stale
        self.asset_service._warmup_generation = self.original_generation

    def test_balance_mutation_changes_chart_cache_key(self):
        before = self.asset_service.financial_chart_cache_key("Bugün")
        self.asset_service.mark_account_cache_stale()
        after = self.asset_service.financial_chart_cache_key("Bugün")

        self.assertNotEqual(before, after)

    def test_account_cache_invalidation_changes_chart_cache_key(self):
        before = self.asset_service.financial_chart_cache_key("1 Ay")
        self.asset_service.invalidate_asset_data_cache()
        after = self.asset_service.financial_chart_cache_key("1 Ay")

        self.assertNotEqual(before, after)

    def test_same_rendered_key_skips_all_chart_work(self):
        from ui.charts import DashboardChartManager

        key = self.asset_service.financial_chart_cache_key("Bugün")
        manager = SimpleNamespace(_rendered_cache_key=key)

        with mock.patch("threading.Thread") as thread_cls:
            started = DashboardChartManager.refresh_dashboard(manager, "Bugün")

        self.assertFalse(started)
        thread_cls.assert_not_called()

    def test_force_bypasses_warm_chart_cache(self):
        from ui.charts import DashboardChartManager

        key = self.asset_service.financial_chart_cache_key("Bugün")
        manager = SimpleNamespace(
            _rendered_cache_key=key,
            _refresh_generation=0,
            pie_widget=mock.Mock(),
            legend_widget=mock.Mock(),
            trend_chart=mock.Mock(),
            _set_chart_empty_state=mock.Mock(),
            _set_charts_loading=mock.Mock(),
        )

        with mock.patch("threading.Thread") as thread_cls:
            started = DashboardChartManager.refresh_dashboard(
                manager, "Bugün", force=True,
            )

        self.assertTrue(started)
        thread_cls.assert_called_once()


class RecentTransactionsIsolationTest(unittest.TestCase):
    def test_public_recent_loader_does_not_refresh_all_charts(self):
        from mixins.transaction_mixin import TransactionMixin

        app = SimpleNamespace(
            _refresh_recent_transactions=mock.Mock(),
            refresh_dashboard_data=mock.Mock(),
        )
        TransactionMixin.load_recent_transactions(app, "Günlük")

        app._refresh_recent_transactions.assert_called_once_with("Günlük")
        app.refresh_dashboard_data.assert_not_called()

    def test_assets_tab_requests_freshness_aware_dashboard_refresh(self):
        from mixins.transaction_mixin import TransactionMixin

        scheduled = []
        app = SimpleNamespace(
            _assets_tab_load_ev=None,
            refresh_dashboard_data=mock.Mock(),
            load_active_assets=mock.Mock(),
        )
        with mock.patch(
            "mixins.transaction_mixin.Clock.schedule_once",
            side_effect=lambda callback, _delay: scheduled.append(callback),
        ):
            TransactionMixin.on_assets_tab_enter(app)

        scheduled[0](0)
        app.refresh_dashboard_data.assert_called_once_with(
            reuse_if_fresh=True,
        )


if __name__ == "__main__":
    unittest.main()
