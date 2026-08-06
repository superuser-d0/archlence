"""Regression coverage for the Phase 2 asset-sale partial-commit defect."""
import sqlite3
from contextlib import closing

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile


class AssetSaleAtomicityTest(_TemporaryProfile):
    def test_fault_after_asset_write_rolls_back_asset_cash_and_ledger(self):
        from database.db import insert_asset
        from services.asset_sale_service import AssetSaleService

        account_id = self.create_account()
        insert_asset("Audit", "AUD", "Altın", 100, 2)
        with closing(sqlite3.connect(self.db_path)) as conn:
            asset_id = conn.execute("SELECT id FROM active_assets").fetchone()[0]
        before = (self.balance(account_id), 1, 0)
        with self.assertRaises(OSError):
            AssetSaleService.sell(asset_id, 150, account_id, _fault_hook=lambda _: (_ for _ in ()).throw(OSError("fault")))
        with closing(sqlite3.connect(self.db_path)) as conn:
            after = (self.balance(account_id), conn.execute("SELECT COUNT(*) FROM active_assets").fetchone()[0], conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
        self.assertEqual(after, before)

    def test_full_sale_has_one_asset_and_one_cash_effect(self):
        from database.db import insert_asset
        from services.asset_sale_service import AssetSaleService
        account_id = self.create_account()
        insert_asset("Audit", "AUD", "Altın", 100, 2)
        with closing(sqlite3.connect(self.db_path)) as conn:
            asset_id = conn.execute("SELECT id FROM active_assets").fetchone()[0]
        self.assertEqual(AssetSaleService.sell(asset_id, 150, account_id), 300.0)
        self.assertEqual(self.balance(account_id), 1300.0)
