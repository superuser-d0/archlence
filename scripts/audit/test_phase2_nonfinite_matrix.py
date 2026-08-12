"""Service-boundary non-finite matrix; failures are audit evidence."""
from __future__ import annotations

import sqlite3

from utils.errors import ArchlenceError
from contextlib import closing
from datetime import date

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile


class NonFiniteServiceMatrix(_TemporaryProfile):
    def _counts(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("transactions", "balance_events", "active_assets", "recurring_payments"))

    def test_account_creation_rejects_infinite_initial_balance(self):
        from services.account_service import AccountService
        caught = None
        try:
            account_id = AccountService.create_account("Inf open", "checking", float("inf"))
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:
            caught = exc
            account_id = None
        print(f"AUDIT_STATE nonfinite_account caught={type(caught).__name__ if caught else 'NONE'} id={account_id}")
        self.assertIsNotNone(caught)

    def test_savings_deposit_rejects_infinity_before_any_write(self):
        from services.savings_service import SavingsService
        account_id = self.create_account()
        goal_id = SavingsService.create_goal("Inf goal", 1000)
        before = self._counts()
        caught = None
        try:
            SavingsService.deposit_to_goal(goal_id, float("inf"), account_id)
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:
            caught = exc
        with closing(sqlite3.connect(self.db_path)) as conn:
            goal = conn.execute("SELECT current_amount FROM savings_goals WHERE id=?", (goal_id,)).fetchone()[0]
        print(f"AUDIT_STATE nonfinite_savings caught={type(caught).__name__ if caught else 'NONE'} before={before} after={self._counts()} balance={self.balance(account_id)!r} goal={goal!r}")
        self.assertIsNotNone(caught)
        self.assertEqual(self._counts(), before)

    def test_asset_purchase_rejects_infinity_before_any_write(self):
        from services.asset_purchase_service import AssetPurchaseService
        account_id = self.create_account()
        before = self._counts()
        caught = None
        try:
            AssetPurchaseService.create_purchase(asset_name="Inf", asset_code="INF", asset_type="Altın", purchase_price=float("inf"), quantity=1, account_id=account_id)
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:
            caught = exc
        print(f"AUDIT_STATE nonfinite_asset caught={type(caught).__name__ if caught else 'NONE'} before={before} after={self._counts()} balance={self.balance(account_id)!r}")
        self.assertIsNotNone(caught)
        self.assertEqual(self._counts(), before)

    def test_recurring_creation_rejects_infinite_amount(self):
        """Sonsuz tutar artık KAYIT sırasında reddediliyor — okuma/işleme değil.

        Eskiden `insert_recurring_payment` hiçbir doğrulama yapmıyordu:
        `nan`/`inf`/negatif/sıfır şifrelenip KALICI olarak yazılıyordu ve
        yalnızca tahsilat yolu duruyordu. Yazma sınırı kapatıldı; bu test
        onu ölçüyor, aşağıdaki test ise tahsilat yolunun kendi savunmasını
        (ikinci savunma hattı) ölçmeye devam ediyor.
        """
        from database.db import insert_recurring_payment
        account_id = self.create_account()
        before = self._counts()
        caught = None
        try:
            insert_recurring_payment("Inf recurring", float("inf"), "Inf", "monthly", date.today().isoformat(), False, account_id=account_id, recurrence_day=date.today().day)
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:
            caught = exc
        print(f"AUDIT_STATE nonfinite_recurring_insert caught={type(caught).__name__ if caught else 'NONE'} before={before} after={self._counts()}")
        self.assertIsNotNone(caught)
        self.assertEqual(self._counts(), before)

    def test_recurring_processing_rejects_infinite_amount_before_any_effect(self):
        from database.db import get_active_recurring_payments, insert_recurring_payment, process_due_recurring_payment
        account_id = self.create_account()
        insert_recurring_payment("Inf recurring", 10.0, "Inf", "monthly", date.today().isoformat(), False, account_id=account_id, recurrence_day=date.today().day)
        # Tahsilat yolu artık geçerli bir satırdan sonsuz tutar OKUYAMAZ;
        # sınandığı şey, sonsuz tutar taşıyan bir ödeme nesnesi (eski bir
        # yapının bıraktığı satır ya da yeni bir çağıran) elinde olduğunda
        # HİÇBİR etki üretmeden durması.
        payment = dict(get_active_recurring_payments()[0], amount=float("inf"))
        before = self._counts()
        caught = None
        try:
            process_due_recurring_payment(payment)
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:
            caught = exc
        print(f"AUDIT_STATE nonfinite_recurring caught={type(caught).__name__ if caught else 'NONE'} before={before} after={self._counts()} balance={self.balance(account_id)!r}")
        self.assertIsNotNone(caught)
        self.assertEqual(self._counts(), before)


if __name__ == "__main__":
    import unittest
    unittest.main()
