"""Passing property/integration probes for the v0.0.9 Phase 2 audit.

Hypothesis is an audit-only environment dependency.  These tests use generated
data and temporary profiles; they are intentionally not discovered by the
normal release suite.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from decimal import Decimal

from hypothesis import given, settings, strategies as st

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile
from utils.app_paths import LEGACY_CBC_PASSWORD
from utils.financial_decimal import fiat


def semantic_state_hash(path):
    """Hash stable financial rows, not SQLite page-layout bytes."""
    tables = (
        "accounts",
        "transactions",
        "balance_events",
        "savings_goals",
        "active_assets",
        "asset_history",
        "active_debts",
        "recurring_payments",
    )
    snapshot = {}
    with closing(sqlite3.connect(path)) as conn:
        for table in tables:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                snapshot[table] = []
                continue
            columns = [
                row[1] for row in conn.execute(f"PRAGMA table_info({table})")
            ]
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            snapshot[table] = [dict(zip(columns, row)) for row in rows]
    encoded = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FinancialPropertyAudit(_TemporaryProfile):
    @settings(max_examples=80, deadline=None, derandomize=True)
    @given(
        cents=st.integers(min_value=1, max_value=99_999_999_999),
        installments=st.integers(min_value=2, max_value=12),
    )
    def test_installment_quantization_and_remainder_preserve_principal(
        self, cents, installments
    ):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        principal = Decimal(cents) / Decimal(100)
        account_id = AccountService.create_account(
            f"Property Card {cents}-{installments}",
            "credit_card",
            credit_limit=1_000_000_000_000.0,
        )
        TransactionService.add_transaction(
            account_id,
            float(principal),
            "expense",
            "Property",
            "Installment property",
            installments=installments,
            detect_subscription=False,
        )
        plan = TransactionService.get_installment_plans(account_id)[0]
        monthly = Decimal(str(plan["monthly_amount"]))
        total = Decimal(str(plan["total_amount"]))


        self.assertEqual(monthly, fiat(principal / installments))
        self.assertEqual(total, principal)


    def test_real_installment_schedule_sums_to_the_principal(self):
        """Taksit planı ÜRETİMDEN okunarak anaparaya eşitlenmeli.

        Uygulamada taksit başına satır YOK; plan tek bir `monthly_amount` ve
        `paid_installments` sayacıyla temsil ediliyor ve kalan borç
        `get_installment_plans` tarafından `anapara - aylık x ödenen` olarak
        TÜRETİLİYOR. Dolayısıyla gerçek "son taksit", ödenen sayacı n-1'e
        getirildiğinde üretimin raporladığı `remaining_amount`tır.

        Bu test o değeri üretimden OKUR; hesaplamaz. Önceki property
        assertion'ı son taksiti kendisi türetiyordu ve bu yüzden totolojikti.
        """
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        cases = (
            ("100.01", 2),
            ("100.02", 12),
            ("1000.00", 3),
            ("12500.00", 12),
            ("0.01", 3),
            ("999999999.99", 12),
        )
        for amount_text, installments in cases:
            with self.subTest(principal=amount_text, installments=installments):
                principal = Decimal(amount_text)
                account_id = AccountService.create_account(
                    f"Schedule {amount_text}-{installments}",
                    "credit_card",
                    credit_limit=10_000_000_000.0,
                )
                TransactionService.add_transaction(
                    account_id, float(principal), "expense", "Schedule",
                    f"{installments} taksit", installments=installments,
                    detect_subscription=False,
                )
                plan_id = TransactionService.get_installment_plans(
                    account_id
                )[0]["id"]


                schedule = []
                previous = None
                for paid in range(installments):
                    self._set_paid_installments(plan_id, paid)
                    plan = TransactionService.get_installment_plans(
                        account_id
                    )[0]
                    remaining = Decimal(str(plan["remaining_amount"]))
                    self.assertEqual(
                        -remaining.as_tuple().exponent <= 2, True,
                        f"kalan borç kuruştan ince: {remaining}",
                    )
                    if previous is not None:
                        schedule.append(previous - remaining)
                    previous = remaining

                schedule.append(previous)

                self.assertEqual(
                    len(schedule), installments,
                    "taksit sayısı istenenle eşleşmiyor",
                )
                self.assertEqual(
                    sum(schedule), principal,
                    f"taksitlerin toplamı anaparayı tutmuyor: "
                    f"{sum(schedule)} != {principal}",
                )
                for step in schedule:
                    self.assertEqual(
                        -Decimal(str(step)).as_tuple().exponent <= 2, True,
                        f"taksit kuruştan ince: {step}",
                    )

    def _set_paid_installments(self, plan_id, paid):
        from database.db import managed_connection

        with managed_connection() as conn:
            conn.execute(
                "UPDATE installment_plans SET paid_installments = ? "
                "WHERE id = ?",
                (paid, plan_id),
            )
            conn.commit()

    @settings(max_examples=60, deadline=None, derandomize=True)
    @given(cents=st.integers(min_value=1, max_value=99_999_999))
    def test_savings_deposit_withdraw_roundtrip(self, cents):
        from services.account_service import AccountService
        from services.savings_service import SavingsService

        amount = Decimal(cents) / Decimal(100)
        account_id = AccountService.create_account(
            f"Savings Account {cents}", "checking", initial_balance=10_000_000
        )
        goal_id = SavingsService.create_goal(
            f"Savings Goal {cents}", 100_000_000
        )
        SavingsService.deposit_to_goal(goal_id, amount, account_id)
        SavingsService.withdraw_from_goal(goal_id, amount, account_id)

        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
            goal_amount = conn.execute(
                "SELECT current_amount FROM savings_goals WHERE id=?",
                (goal_id,),
            ).fetchone()[0]
            event_delta = conn.execute(
                "SELECT SUM(delta) FROM balance_events "
                "WHERE source IN ('savings_deposit','savings_withdraw') "
                "AND entity_id IN (?,?)",
                (account_id, goal_id),
            ).fetchone()[0]
        self.assertEqual(fiat(balance), Decimal("10000000.00"))
        self.assertEqual(fiat(goal_amount), Decimal("0.00"))
        self.assertEqual(fiat(event_delta), Decimal("0.00"))

    def test_failed_savings_write_preserves_state(self):
        from services.savings_service import SavingsService

        account_id = self.create_account()
        goal_id = SavingsService.create_goal("Rollback goal", 100)
        before = semantic_state_hash(self.db_path)
        with self.assertRaises(ValueError):
            SavingsService.withdraw_from_goal(goal_id, 1, account_id)
        self.assertEqual(semantic_state_hash(self.db_path), before)

    @settings(max_examples=80, deadline=None, derandomize=True)
    @given(
        cents=st.integers(min_value=-99_999_999_999, max_value=99_999_999_999)
    )
    def test_encrypt_decrypt_serialize_preserves_fiat_value(self, cents):
        from utils.crypto import decrypt, encrypt

        value = Decimal(cents) / Decimal(100)
        encoded = encrypt(str(value), LEGACY_CBC_PASSWORD)
        decoded = decrypt(encoded, LEGACY_CBC_PASSWORD)
        encoded_again = encrypt(decoded, LEGACY_CBC_PASSWORD)
        decoded_again = decrypt(encoded_again, LEGACY_CBC_PASSWORD)
        self.assertEqual(fiat(decoded), value)
        self.assertEqual(fiat(decoded_again), value)

    def test_backup_restore_preserves_semantic_financial_state_hash(self):
        from services.backup_service import create_backup, restore_backup
        from services.transaction_service import TransactionService

        account_id = self.create_account()
        for amount in ("0.01", "0.10", "0.29", "999.99", "1000.00"):
            TransactionService.add_transaction(
                account_id,
                float(Decimal(amount)),
                "expense",
                "Property",
                f"amount={amount}",
                detect_subscription=False,
            )
        before = semantic_state_hash(self.db_path)
        package = self.root / "state-hash.archlence-backup"
        create_backup(
            package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )
        restored_db = self.root / "restored" / "finance.db"
        restored_key = self.root / "restored" / "encryption.key"
        restore_backup(
            package,
            self.PASSPHRASE,
            db_path=restored_db,
            key_path=restored_key,
        )
        self.assertEqual(semantic_state_hash(restored_db), before)


if __name__ == "__main__":
    import unittest

    unittest.main()
