import sqlite3
from contextlib import closing
from scripts.audit.test_adversarial_reproductions import _TemporaryProfile


class DebtPaymentAtomicityTest(_TemporaryProfile):
    def test_fault_rolls_back_transaction_balance_and_progress(self):
        from database.db import insert_debt
        from services.debt_payment_service import DebtPaymentService
        account = self.create_account(); insert_debt("Debt", 300, 100, 3, 1, 1)
        with closing(sqlite3.connect(self.db_path)) as conn:
            debt = conn.execute("SELECT id FROM active_debts").fetchone()[0]
        with self.assertRaises(OSError):
            DebtPaymentService.pay_auto(debt, account, 1, "2026-08", lambda _: (_ for _ in ()).throw(OSError("fault")))
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute("SELECT paid_installments,last_auto_pay_date FROM active_debts").fetchone()
            self.assertEqual((row[0], row[1]), (0, None)); self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 0)
        self.assertEqual(self.balance(account), 1000.0)
