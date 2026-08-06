import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from tests.fixtures import AccountFixtureMixin


class AssetPurchaseAtomicityTest(AccountFixtureMixin, unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database

        initialize_database()
        self.account_id = self.create_test_account(
            name="Asset test", balance=10_000.0
        )

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def _counts(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return (
                conn.execute("SELECT COUNT(*) FROM active_assets").fetchone()[0],
                conn.execute(
                    "SELECT COUNT(*) FROM transactions "
                    "WHERE category='Varlık Alımı'"
                ).fetchone()[0],
            )

    def test_purchase_commits_asset_transaction_balance_and_ledger_once(self):
        from services.asset_purchase_service import AssetPurchaseService

        result = AssetPurchaseService.create_purchase(
            asset_name="Gram Altın",
            asset_code="GC=F",
            asset_type="Altın",
            purchase_price=100.0,
            quantity=2.0,
            account_id=self.account_id,
        )
        self.assertEqual(self._counts(), (1, 1))
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (self.account_id,)
            ).fetchone()[0]
            event = conn.execute(
                "SELECT delta, source, ref_id FROM balance_events "
                "WHERE source='asset_purchase'"
            ).fetchone()
        self.assertEqual(balance, 9_800.0)
        self.assertEqual(event[0], -200.0)
        self.assertEqual(event[1], "asset_purchase")
        self.assertEqual(event[2], result["transaction_id"])

    def test_cash_amount_is_quantised_to_kurus_not_a_raw_float_product(self):
        """Cüzdandan çıkan tutar kuruşa yuvarlanmış olmalı.

        `invested_amount = price * qty` ham çarpımı hem bakiyeden düşülüyor
        hem de işlem tutarı olarak ŞİFRELENİP SAKLANIYORDU, yani ikili kayan
        nokta artıkları deftere kalıcı giriyordu:

            142,30 x 17          -> 2419.1000000000004
            2.456,78 x 0,12345678 -> 303.3061479684  (on ondalıklı bir LİRA)

        Fiyat ve miktar ayrı sütunlarda tam hassasiyetle durduğu için burada
        bilgi kaybı yok; yuvarlanan yalnızca nakit hareketidir.
        """
        from decimal import Decimal
        from services.asset_purchase_service import AssetPurchaseService
        from utils.crypto import decrypt
        from services.transaction_service import SECRET_KEY

        for price, qty, expected in (
            ("142.30", "17.0", Decimal("2419.10")),
            ("2456.78", "0.12345678", Decimal("303.31")),
            ("67234.56", "0.003125", Decimal("210.11")),
        ):
            with self.subTest(price=price, quantity=qty):
                account_id = self.create_test_account(
                    name=f"Nakit {price}-{qty}", balance=100_000.0
                )
                AssetPurchaseService.create_purchase(
                    asset_name="Test", asset_code="TST", asset_type="Kripto",
                    purchase_price=float(price), quantity=float(qty),
                    account_id=account_id,
                )
                with closing(sqlite3.connect(self.db_path)) as conn:
                    stored, = conn.execute(
                        "SELECT amount FROM transactions "
                        "WHERE account_id=? AND category='Varlık Alımı'",
                        (account_id,),
                    ).fetchone()
                    balance, = conn.execute(
                        "SELECT balance FROM accounts WHERE id=?",
                        (account_id,),
                    ).fetchone()

                # Saklanan metin tam olarak kuruşlu tutar olmalı — ne
                # "2419.1000000000004" ne de "303.3061479684".
                self.assertEqual(
                    Decimal(decrypt(str(stored), SECRET_KEY)), expected
                )
                # Bakiyeden düşülen de aynı tutar olmalı.
                self.assertEqual(
                    Decimal(str(balance)), Decimal("100000.00") - expected
                )

    def test_failure_after_asset_insert_rolls_back_every_row(self):
        from services.asset_purchase_service import AssetPurchaseService

        with mock.patch(
            "services.asset_purchase_service.adjust_account_balance",
            side_effect=sqlite3.OperationalError("injected"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                AssetPurchaseService.create_purchase(
                    asset_name="Rollback",
                    asset_code="ROLL",
                    asset_type="Diğer",
                    purchase_price=10.0,
                    quantity=1.0,
                    account_id=self.account_id,
                )
        self.assertEqual(self._counts(), (0, 0))

    def test_existing_asset_does_not_change_wallet_or_create_expense(self):
        from services.asset_purchase_service import AssetPurchaseService

        result = AssetPurchaseService.create_purchase(
            asset_name="Eski Altın",
            asset_code="GC=F",
            asset_type="Altın",
            purchase_price=100.0,
            quantity=2.0,
            deduct_from_balance=False,
        )

        self.assertEqual(self._counts(), (1, 0))
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (self.account_id,)
            ).fetchone()[0]
            ledger_count = conn.execute(
                "SELECT COUNT(*) FROM balance_events "
                "WHERE source='asset_purchase'"
            ).fetchone()[0]
        self.assertEqual(balance, 10_000.0)
        self.assertEqual(ledger_count, 0)
        self.assertIsNone(result["transaction_id"])
        self.assertFalse(result["deducted_from_balance"])

    def test_existing_asset_can_be_added_without_any_wallet_account(self):
        from services.asset_purchase_service import AssetPurchaseService

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("DELETE FROM accounts")
            conn.commit()

        result = AssetPurchaseService.create_purchase(
            asset_name="Eski Bitcoin",
            asset_code="BTC-USD",
            asset_type="Kripto",
            purchase_price=100.0,
            quantity=1.0,
            deduct_from_balance=False,
        )

        self.assertEqual(self._counts(), (1, 0))
        self.assertFalse(result["deducted_from_balance"])

    def test_frozen_account_is_rejected_before_asset_insert(self):
        from services.account_service import AccountService
        from services.asset_purchase_service import AssetPurchaseService

        AccountService.set_card_frozen(self.account_id, True)
        with self.assertRaisesRegex(ValueError, "dondur"):
            AssetPurchaseService.create_purchase(
                asset_name="Frozen",
                asset_code="FRZN",
                asset_type="Diğer",
                purchase_price=10.0,
                quantity=1.0,
                account_id=self.account_id,
            )
        self.assertEqual(self._counts(), (0, 0))


class _ImmediateTasks:
    def __init__(self):
        self.submissions = 0

    def submit(self, _key, work, *, on_success, on_error, **_kwargs):
        self.submissions += 1
        try:
            on_success(work(None))
        except Exception as exc:
            on_error(exc)


class AssetPurchaseUiBoundaryTest(unittest.TestCase):
    def _app(self):
        from mixins.asset_mixin import AssetMixin

        class App(AssetMixin):
            def __init__(self):
                self.background_tasks = _ImmediateTasks()
                self.calls = []

            def load_active_assets(self, **_kwargs):
                self.calls.append("assets")
                raise RuntimeError("injected UI failure")

            def load_asset_history(self):
                self.calls.append("history")

            def load_recent_transactions(self):
                self.calls.append("recent")

            def safe_refresh_charts(self):
                self.calls.append("charts")

        return App()

    def test_post_commit_ui_failure_does_not_show_creation_failure(self):
        app = self._app()
        result = {"asset_id": 1, "transaction_id": 2}
        with mock.patch(
            "services.asset_purchase_service.AssetPurchaseService.create_purchase",
            return_value=result,
        ), mock.patch(
            "mixins.asset_mixin.Clock.schedule_once",
            side_effect=lambda callback, _delay: callback(0),
        ), mock.patch(
            "mixins.asset_mixin.toast"
        ) as toast, mock.patch(
            "utils.logging_config.get_logger"
        ):
            app._submit_asset_purchase(
                "Altın", "GC=F", "Altın", 100, 1,
                "başarılı", "başarısız",
            )
        self.assertEqual(app.calls, ["assets", "history", "recent", "charts"])
        toast.assert_called_once_with("başarılı")

    def test_double_submit_is_coalesced(self):
        app = self._app()
        app._asset_purchase_inflight = True
        app._submit_asset_purchase(
            "Altın", "GC=F", "Altın", 100, 1,
            "başarılı", "başarısız",
        )
        self.assertEqual(app.background_tasks.submissions, 0)

    def test_no_deduction_choice_reaches_service(self):
        app = self._app()
        with mock.patch(
            "services.asset_purchase_service.AssetPurchaseService.create_purchase",
            return_value={"asset_id": 1, "transaction_id": None},
        ) as create_purchase, mock.patch(
            "mixins.asset_mixin.Clock.schedule_once",
            side_effect=lambda callback, _delay: callback(0),
        ), mock.patch(
            "mixins.asset_mixin.toast"
        ), mock.patch(
            "utils.logging_config.get_logger"
        ):
            app._submit_asset_purchase(
                "Eski Altın", "GC=F", "Altın", 100, 1,
                "başarılı", "başarısız", deduct_from_balance=False,
            )

        self.assertFalse(
            create_purchase.call_args.kwargs["deduct_from_balance"]
        )

    def test_dialog_content_height_reserves_title_and_actions(self):
        from mixins.asset_mixin import responsive_dialog_content_height

        self.assertEqual(
            responsive_dialog_content_height(521, 420, 170, 240), 351
        )
        self.assertEqual(
            responsive_dialog_content_height(900, 420, 170, 240), 420
        )


if __name__ == "__main__":
    unittest.main()
