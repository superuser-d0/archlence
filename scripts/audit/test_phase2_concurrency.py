"""Deterministic two-worker races for Phase 2; intentionally failing where noted."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import date
from unittest import mock

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile
from utils.errors import ArchlenceError


def _run_two_workers(action):
    """Release both workers at the same logical point; no sleep timing."""
    gate = threading.Barrier(3)
    failures = []

    def worker():
        try:
            gate.wait()
            action()
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError) as exc:  # evidence: controlled conflict is acceptable
            failures.append(type(exc).__name__)

    workers = [threading.Thread(target=worker) for _ in range(2)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(timeout=5)
    assert not any(worker.is_alive() for worker in workers)
    return failures


class ConcurrentRecurringReproduction(_TemporaryProfile):
    def _payment(self, account_id):
        from database.db import get_active_recurring_payments, insert_recurring_payment

        insert_recurring_payment(
            "Concurrent audit", 100.0, "Concurrent", "monthly",
            date.today().isoformat(), False, account_id=account_id,
            recurrence_day=date.today().day,
        )
        return get_active_recurring_payments()[0]

    def test_two_workers_charge_one_due_period_once(self):
        from database.db import get_connection, process_due_recurring_payment

        account_id = self.create_account()
        payment = self._payment(account_id)
        failures = _run_two_workers(lambda: process_due_recurring_payment(payment))
        with closing(get_connection()) as conn, conn:
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category='Concurrent'"
            ).fetchone()[0]
        print(
            "AUDIT_STATE concurrent_recurring "
            f"timeline=T0:read,T1:barrier,T2:write,T3:commit,T4:observe "
            f"transaction_count={tx_count} balance={self.balance(account_id)} "
            f"worker_failures={failures}"
        )
        self.assertEqual(tx_count, 1, "iki eşzamanlı worker aynı vadeyi yazdı")
        self.assertEqual(self.balance(account_id), 900.0)

    def test_two_workers_refund_one_charge_once(self):
        from database.db import get_connection, process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge

        account_id = self.create_account()
        payment = self._payment(account_id)
        process_due_recurring_payment(payment)
        failures = _run_two_workers(
            lambda: refund_current_period_charge(payment["id"])
        )
        with closing(get_connection()) as conn, conn:
            income_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE type='income'"
            ).fetchone()[0]
        print(
            "AUDIT_STATE concurrent_refund "
            f"timeline=T0:find-charge,T1:barrier,T2:insert,T3:commit,T4:observe "
            f"income_count={income_count} balance={self.balance(account_id)} "
            f"worker_failures={failures}"
        )
        self.assertEqual(income_count, 1, "iki worker aynı tahsilatı iade etti")
        self.assertEqual(self.balance(account_id), 1000.0)


class ConcurrentBoundedOperations(_TemporaryProfile):
    def test_two_savings_withdrawals_do_not_overdraw_goal(self):
        from services.savings_service import SavingsService

        account_id = self.create_account()
        goal_id = SavingsService.create_goal("Race savings", 100, current_amount=100)
        failures = _run_two_workers(
            lambda: SavingsService.withdraw_from_goal(goal_id, 100, account_id)
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            amount = conn.execute(
                "SELECT current_amount FROM savings_goals WHERE id=?", (goal_id,)
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM balance_events WHERE source='savings_withdraw'"
            ).fetchone()[0]
        print(
            "AUDIT_STATE concurrent_savings_withdraw "
            f"goal_amount={amount} balance={self.balance(account_id)} "
            f"withdraw_events={events} worker_failures={failures}"
        )
        self.assertGreaterEqual(amount, 0)
        self.assertLessEqual(self.balance(account_id), 1100.0)
        self.assertEqual(events, 2)  # account+goal event for exactly one withdrawal

    def test_two_card_charges_cannot_use_the_same_limit_snapshot(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Race card", "credit_card", credit_limit=100.0
        )


        original = AccountService.check_spending_allowed
        reached = threading.Barrier(2)

        def synchronized_check(*args, **kwargs):
            result = original(*args, **kwargs)
            if result[0]:
                try:
                    reached.wait(timeout=2)
                except threading.BrokenBarrierError:
                    pass
            return result

        with mock.patch.object(
            AccountService, "check_spending_allowed", side_effect=synchronized_check
        ):
            failures = _run_two_workers(
                lambda: TransactionService.add_transaction(
                    card_id, 60.0, "expense", "Race", "limit race",
                    detect_subscription=False,
                )
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id=?", (card_id,)
            ).fetchone()[0]
        card = AccountService.get_account(card_id)
        print(
            "AUDIT_STATE concurrent_card_limit "
            f"transaction_count={tx_count} debt={card['debt']} "
            f"available_limit={card['available_limit']} worker_failures={failures}"
        )
        self.assertLessEqual(card["debt"], 100.0, "iki stale limit kontrolü limiti aştı")


class ConcurrentAssetPurchaseReproduction(_TemporaryProfile):
    """Varlık alımı, kart harcamasıyla AYNI limit garantisine tabidir.

    NEDEN VAR: `467b269` limit kararını `add_transaction` içinde
    `BEGIN IMMEDIATE`'in arkasına aldı, ama `asset_purchase_service` aynı
    korumayı almadı — kontrolü kendi bağlantısını açan
    `check_spending_allowed` ile transaction'ın DIŞINDA yapıyordu. Üretildi:
    100 TL limitli kartta iki eşzamanlı alım borcu **120 TL** yapıyordu.

    Bugün UI'dan erişilebilir değildi (`asset_mixin`'de `_asset_purchase_inflight`
    kilidi var ve `_pick_funding_account` kredi kartı seçmiyor), ama invariant
    UI state'inde yaşıyordu, domain'de değil. Yeni bir çağıran onu baypas
    ederdi.
    """

    def test_two_purchases_cannot_use_the_same_limit_snapshot(self):
        from services.account_service import AccountService
        from services.asset_purchase_service import AssetPurchaseService

        card_id = AccountService.create_account(
            "Race card", "credit_card", credit_limit=100.0
        )


        original = AccountService.check_spending_allowed
        reached = threading.Barrier(2)

        def synchronized_check(*args, **kwargs):
            result = original(*args, **kwargs)
            if result[0]:
                try:
                    reached.wait(timeout=2)
                except threading.BrokenBarrierError:
                    pass
            return result

        with mock.patch.object(
            AccountService, "check_spending_allowed", side_effect=synchronized_check
        ):
            failures = _run_two_workers(
                lambda: AssetPurchaseService.create_purchase(
                    asset_name="Race", asset_code="RACE", asset_type="hisse",
                    quantity=1, purchase_price=60.0, account_id=card_id,
                    deduct_from_balance=True,
                )
            )
        card = AccountService.get_account(card_id)
        with closing(sqlite3.connect(self.db_path)) as conn:
            assets = conn.execute(
                "SELECT COUNT(*) FROM active_assets WHERE asset_code='RACE'"
            ).fetchone()[0]
            transactions = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id=?", (card_id,)
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM balance_events WHERE source='asset_purchase'"
            ).fetchone()[0]
        print(
            "AUDIT_STATE concurrent_asset_purchase "
            f"assets={assets} transactions={transactions} events={events} "
            f"debt={card['debt']} worker_failures={failures}"
        )


        self.assertLessEqual(
            card["debt"], 100.0,
            f"iki stale limit kontrolü limiti aştı (borç={card['debt']})",
        )


        self.assertEqual(
            len(failures), 1,
            f"tam olarak bir alım reddedilmeliydi, sonuç: {failures}",
        )


        self.assertEqual(assets, 1, "reddedilen alımın varlık satırı kalmış")
        self.assertEqual(transactions, 1, "reddedilen alımın işlemi kalmış")
        self.assertEqual(events, 1, "reddedilen alımın bakiye olayı kalmış")


if __name__ == "__main__":
    import unittest
    unittest.main()
