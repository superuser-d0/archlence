"""Intentionally failing v0.0.9 audit reproductions.

This module is deliberately outside ``tests/`` so ``run_tests.py`` remains a
release-candidate signal.  Run it explicitly:

    python -m unittest scripts.audit.test_adversarial_reproductions -v

Every test uses a temporary database/key/archive.  A failure means the named
production invariant is *not* currently enforced; it is audit evidence, not a
test-suite regression to hide with skip/xfail.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest import mock

from utils.errors import FinancialDataIntegrityError, IntegrityVerificationError


class _TemporaryProfile(unittest.TestCase):
    PASSPHRASE = "yalnizca-audit-icin-parola"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="archlence-audit-")
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "finance.db"
        self.key_path = self.root / "encryption.key"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)
        os.chmod(self.key_path, 0o600)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()

        from database.init_db import initialize_database

        initialize_database()

    def tearDown(self):
        self.key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def create_account(self, balance=1000.0):
        from services.account_service import AccountService

        return AccountService.create_account(
            "Audit Hesabı", "checking", initial_balance=balance
        )

    def balance(self, account_id):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]


class BackupAuthenticityReproduction(_TemporaryProfile):
    def test_plaintext_financial_state_cannot_be_rewritten_with_a_new_hash(self):
        """A manifest digest must be authenticated, not attacker-replaceable."""
        from services.backup_service import create_backup, verify_backup
        from services.transaction_service import TransactionService

        account_id = self.create_account()
        TransactionService.add_transaction(
            account_id, 125.50, "expense", "Market", "Sentetik kayıt"
        )
        package = self.root / "original.archlence-backup"
        create_backup(
            package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )

        unpacked = self.root / "rewritten"
        unpacked.mkdir()
        with zipfile.ZipFile(package) as archive:
            archive.extractall(unpacked)

        with closing(sqlite3.connect(unpacked / "finance.db")) as conn:
            conn.execute(
                "UPDATE accounts SET balance=777777.77 WHERE id=?",
                (account_id,),
            )
            conn.commit()

        metadata_path = unpacked / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["database_sha256"] = hashlib.sha256(
            (unpacked / "finance.db").read_bytes()
        ).hexdigest()
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        rewritten = self.root / "rewritten.archlence-backup"
        with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in ("finance.db", "metadata.json", "key.recovery.json"):
                archive.write(unpacked / name, name)

        caught = None
        try:
            verify_backup(rewritten, self.PASSPHRASE)
        except IntegrityVerificationError as exc:
            caught = exc
        print(
            "AUDIT_STATE backup_authenticity "
            "before_balance=874.5 after_balance=777777.77 "
            f"expected_exception=IntegrityVerificationError "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'}"
        )
        self.assertIsNotNone(
            caught, "DB ve manifest birlikte değiştirildiğinde backup kabul edildi"
        )


class RecurringIdempotencyReproduction(_TemporaryProfile):
    def _payment(self, account_id, *, amount=100.0, auto_deduct=False):
        from database.db import (
            get_active_recurring_payments,
            insert_recurring_payment,
        )

        insert_recurring_payment(
            "Audit Aboneliği",
            amount,
            "Dijital Platformlar",
            "monthly",
            date.today().isoformat(),
            auto_deduct,
            account_id=account_id,
            recurrence_day=date.today().day,
        )
        return get_active_recurring_payments()[0]

    def test_retrying_the_same_due_object_has_one_financial_effect(self):
        from database.db import get_connection, process_due_recurring_payment

        account_id = self.create_account()
        payment = self._payment(account_id)

        process_due_recurring_payment(payment)
        process_due_recurring_payment(payment)  # retry/stale UI object

        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions "
                "WHERE category='Dijital Platformlar'"
            ).fetchone()[0]
            due = conn.execute(
                "SELECT next_due_date FROM recurring_payments WHERE id=?",
                (payment["id"],),
            ).fetchone()[0]
        after_balance = self.balance(account_id)
        print(
            "AUDIT_STATE recurring_retry "
            f"before_balance=1000.0 after_balance={after_balance} "
            f"transaction_count={count} before_due={date.today().isoformat()} "
            f"after_due={due} expected_exception=NONE caught_exception=NONE"
        )
        self.assertEqual(count, 1, "aynı vade iki işlem üretti")
        self.assertEqual(after_balance, 900.0)

    def test_refund_retry_cannot_credit_the_same_charge_twice(self):
        from database.db import process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge

        account_id = self.create_account()
        payment = self._payment(account_id)
        process_due_recurring_payment(payment)

        first = refund_current_period_charge(payment["id"])
        second = refund_current_period_charge(payment["id"])

        with closing(sqlite3.connect(self.db_path)) as conn:
            counts = conn.execute(
                "SELECT type, COUNT(*) FROM transactions GROUP BY type"
            ).fetchall()
        after_balance = self.balance(account_id)
        print(
            "AUDIT_STATE recurring_refund_retry "
            f"before_balance=1000.0 after_balance={after_balance} "
            f"first_refund={first} second_refund={second} "
            f"transaction_counts={dict(counts)} "
            "expected_exception=NONE caught_exception=NONE"
        )

        self.assertEqual(first, 100.0)
        self.assertEqual(second, 0.0, "aynı tahsilat ikinci kez iade edildi")
        self.assertEqual(after_balance, 1000.0)

    def test_corrupt_auto_amount_fails_closed_without_advancing_due_date(self):
        from database.db import get_active_recurring_payments, get_connection

        account_id = self.create_account()
        payment = self._payment(account_id, auto_deduct=True)
        original_due = payment["next_due_date"]
        with get_connection() as conn:
            conn.execute(
                "UPDATE recurring_payments SET amount=? WHERE id=?",
                ("AEADv1:bozuk-zarf", payment["id"]),
            )
            conn.commit()

        degraded = get_active_recurring_payments()[0]
        self.assertFalse(degraded["amount_is_valid"])
        from database.db import process_due_recurring_payment

        caught = None
        try:
            process_due_recurring_payment(degraded)
        except FinancialDataIntegrityError as exc:
            caught = exc

        with get_connection() as conn:
            row = conn.execute(
                "SELECT next_due_date FROM recurring_payments WHERE id=?",
                (payment["id"],),
            ).fetchone()
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
        print(
            "AUDIT_STATE corrupt_recurring_amount "
            f"before_due={original_due} after_due={row['next_due_date']} "
            f"transaction_count={tx_count} balance={self.balance(account_id)} "
            "expected_exception=FinancialDataIntegrityError "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'}"
        )
        self.assertIsNotNone(caught)
        self.assertEqual(row["next_due_date"], original_due)
        self.assertEqual(tx_count, 0)


class CrossTransactionAtomicityReproduction(_TemporaryProfile):
    @staticmethod
    def _immediate_thread(target=None, daemon=None):
        target()
        return mock.Mock(start=mock.Mock())

    def test_asset_sale_credit_and_asset_removal_are_one_transaction(self):
        from database.db import get_connection, insert_asset
        from mixins.asset_mixin import AssetMixin

        account_id = self.create_account()
        insert_asset("Audit Altını", "AUD", "Altın", 100.0, 2.0)
        with get_connection() as conn:
            asset_id = conn.execute("SELECT id FROM active_assets").fetchone()[0]

        screen = AssetMixin.__new__(AssetMixin)
        for name in (
            "load_active_assets",
            "load_asset_history",
            "load_recent_transactions",
            "safe_refresh_charts",
        ):
            setattr(screen, name, mock.Mock())
        asset = {
            "id": asset_id,
            "asset_name": "Audit Altını",
            "asset_code": "AUD",
            "quantity": 2.0,
            "purchase_price": 100.0,
        }

        with mock.patch(
            "database.db.delete_asset", side_effect=OSError("injected crash")
        ), mock.patch("mixins.asset_mixin.Clock"), mock.patch(
            "threading.Thread", self._immediate_thread
        ):
            screen._execute_sell(asset, 150.0)

        with get_connection() as conn:
            asset_count = conn.execute(
                "SELECT COUNT(*) FROM active_assets WHERE id=?", (asset_id,)
            ).fetchone()[0]
            sale_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE category='Varlık Satışı'"
            ).fetchone()[0]
        after_balance = self.balance(account_id)
        print(
            "AUDIT_STATE asset_sale_fault "
            f"before_balance=1000.0 after_balance={after_balance} "
            f"before_asset_count=1 after_asset_count={asset_count} "
            f"before_sale_count=0 after_sale_count={sale_count} "
            "injected_exception=OSError caught_by_ui_worker=yes"
        )
        self.assertEqual(asset_count, 1, "fault sonrası varlık korunmalı")
        self.assertEqual(sale_count, 0, "fault sonrası nakit işlemi rollback olmalı")
        self.assertEqual(after_balance, 1000.0)

    def test_debt_progress_rolls_back_when_ledger_write_fails(self):
        from database.db import get_connection, insert_debt
        from mixins.recurring_mixin import RecurringMixin

        account_id = self.create_account()
        insert_debt(
            "Audit Borcu",
            300.0,
            100.0,
            3,
            is_auto_pay=1,
            auto_pay_day=1,
        )
        screen = RecurringMixin.__new__(RecurringMixin)

        with mock.patch(
            "services.transaction_service.TransactionService.add_transaction",
            side_effect=OSError("injected ledger failure"),
        ), mock.patch("mixins.recurring_mixin.Clock"), mock.patch(
            "mixins.recurring_mixin.threading.Thread", self._immediate_thread
        ):
            screen.process_due_auto_deductions()

        with get_connection() as conn:
            row = conn.execute(
                "SELECT paid_installments, last_auto_pay_date "
                "FROM active_debts"
            ).fetchone()
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
        print(
            "AUDIT_STATE debt_ledger_fault "
            "before_paid=0 before_last_auto_pay=NULL "
            f"after_paid={row['paid_installments']} "
            f"after_last_auto_pay={row['last_auto_pay_date']} "
            f"transaction_count={tx_count} balance={self.balance(account_id)} "
            "injected_exception=OSError caught_by_auto_worker=yes"
        )
        self.assertEqual(tx_count, 0)
        self.assertEqual(row["paid_installments"], 0)
        self.assertIsNone(row["last_auto_pay_date"])


if __name__ == "__main__":
    unittest.main()
