"""Additional intentionally failing Phase 2 audit reproductions.

This module is deliberately outside ``tests/``.  It writes only to temporary
profiles and must be invoked explicitly.  Failures document invariants that
production does not currently enforce; they are not product fixes.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from unittest import mock

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile
from utils.errors import ArchlenceError, DataMigrationError


class RestoreRollbackReproduction(_TemporaryProfile):
    def test_restore_failure_rolls_back_config_with_database_and_key(self):
        from services import backup_service

        account_id = self.create_account()
        config_path = self.root / "config.json"
        config_path.write_text('{"profile":"from-backup"}', encoding="utf-8")
        package = self.root / "with-config.archlence-backup"
        backup_service.create_backup(
            package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
            config_path=config_path,
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE accounts SET balance=4321 WHERE id=?", (account_id,)
            )
            conn.commit()
        config_path.write_text('{"profile":"current"}', encoding="utf-8")
        current_key = self.key_path.read_bytes()
        original_verify = backup_service.verify_database_key

        def fail_after_config_write(db_path, key):
            if (
                Path(db_path) == self.db_path
                and config_path.read_text(encoding="utf-8")
                == '{"profile":"from-backup"}'
            ):
                raise OSError("injected final verification failure")
            return original_verify(db_path, key)

        caught = None
        with mock.patch.object(
            backup_service,
            "verify_database_key",
            side_effect=fail_after_config_write,
        ):
            try:
                backup_service.restore_backup(
                    package,
                    self.PASSPHRASE,
                    db_path=self.db_path,
                    key_path=self.key_path,
                    config_path=config_path,
                    safety_backup_path=self.root / "safety.archlence-backup",
                )
            except DataMigrationError as exc:
                caught = exc

        print(
            "AUDIT_STATE restore_config_rollback "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'} "
            f"balance={self.balance(account_id)} "
            f"key_rolled_back={self.key_path.read_bytes() == current_key} "
            f"config_after={config_path.read_text(encoding='utf-8')}"
        )
        self.assertIsNotNone(caught)
        self.assertEqual(self.balance(account_id), 4321)
        self.assertEqual(self.key_path.read_bytes(), current_key)
        self.assertEqual(
            config_path.read_text(encoding="utf-8"),
            '{"profile":"current"}',
            "restore hatasında config eski state'e dönmedi",
        )


class InputBoundaryReproduction(_TemporaryProfile):
    def test_non_finite_transaction_is_rejected_without_database_change(self):
        from services.transaction_service import TransactionService

        account_id = self.create_account()
        caught = None
        try:
            TransactionService.add_transaction(
                account_id,
                float("nan"),
                "expense",
                "Audit",
                "NaN service boundary",
                detect_subscription=False,
            )


        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, ArchlenceError) as exc:
            caught = exc

        with closing(sqlite3.connect(self.db_path)) as conn:
            raw_balance = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
            ledger_count = conn.execute(
                "SELECT COUNT(*) FROM balance_events WHERE entity_id=?",
                (account_id,),
            ).fetchone()[0]
        print(
            "AUDIT_STATE nonfinite_transaction "
            f"caught_exception={type(caught).__name__ if caught else 'NONE'} "
            f"raw_balance={raw_balance!r} transaction_count={tx_count} "
            f"balance_event_count={ledger_count}"
        )
        self.assertIsInstance(
            caught,
            ValueError,
            "NaN domain doğrulaması yerine SQLite katmanında hata verdi",
        )
        self.assertEqual(raw_balance, 1000.0)
        self.assertEqual(tx_count, 0)
        self.assertEqual(ledger_count, 1)  # account_opened only


class ExportPermissionReproduction(_TemporaryProfile):
    def test_plaintext_csv_is_owner_only_on_posix(self):
        from services.migration_service import export_all_to_csv
        from services.transaction_service import TransactionService

        account_id = self.create_account()
        TransactionService.add_transaction(
            account_id,
            10.0,
            "expense",
            "Audit",
            "Plaintext export",
            detect_subscription=False,
        )
        export_path = self.root / "financial-export.csv"
        previous_umask = os.umask(0o022)
        try:
            export_all_to_csv(export_path)
        finally:
            os.umask(previous_umask)
        mode = stat.S_IMODE(export_path.stat().st_mode)
        print(
            "AUDIT_STATE csv_permissions "
            f"mode={oct(mode)} expected_mode=0o600 "
            f"contains_plaintext={b'Plaintext export' in export_path.read_bytes()}"
        )
        self.assertEqual(mode, 0o600, "çözülmüş finansal CSV grup/dünya okunabilir")


if __name__ == "__main__":
    import unittest

    unittest.main()


class NonFiniteCorruptionReproduction(_TemporaryProfile):
    """P0: Infinity bakiyeyi kalıcı olarak bozuyor ve toplamdan düşürüyor.

    Phase 2'nin ilk turunda yalnızca NaN sınanmıştı ve NaN gerçekten zararsız
    davranıyor: SQLite katmanında `IntegrityError` ile reddediliyor, işlem ve
    ledger olayı oluşmuyor, bakiye değişmiyor (yanlış katman, ama P2).

    Infinity TAMAMEN FARKLI davranıyor ve hiç sınanmamıştı.
    """

    def test_infinity_expense_corrupts_the_balance_and_the_portfolio_total(self):
        import sqlite3
        from contextlib import closing

        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        victim = AccountService.create_account(
            "Kurban", "checking", initial_balance=5000.0
        )
        AccountService.create_account(
            "Sağlam", "checking", initial_balance=2500.0
        )

        def state():
            with closing(sqlite3.connect(self.db_path)) as conn:
                return (
                    conn.execute(
                        "SELECT balance FROM accounts WHERE id=?", (victim,)
                    ).fetchone()[0],
                    conn.execute("SELECT SUM(balance) FROM accounts").fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM balance_events").fetchone()[0],
                )

        before_balance, before_total, before_events = state()
        self.assertEqual(before_total, 7500.0)

        raised = None
        try:
            TransactionService.add_transaction(
                victim, float("inf"), "expense", "T", "sonsuz",
                transaction_date="2026-08-01 10:00:00",
                detect_subscription=False,
            )
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, ArchlenceError) as exc:
            raised = type(exc).__name__

        after_balance, after_total, after_events = state()


        try:
            TransactionService.add_transaction(
                victim, float("inf"), "income", "T", "sonsuz2",
                transaction_date="2026-08-02 10:00:00",
                detect_subscription=False,
            )
        except (ValueError, TypeError, ArithmeticError, sqlite3.Error, ArchlenceError):
            pass
        null_balance, null_total, _ = state()

        print(
            "AUDIT_STATE nonfinite_infinity "
            f"raised={raised or 'NONE'} "
            f"balance={before_balance!r}->{after_balance!r}->{null_balance!r} "
            f"portfolio_total={before_total!r}->{after_total!r}->{null_total!r} "
            f"balance_events={before_events}->{after_events}"
        )

        self.assertIsNotNone(
            raised,
            "infinity tutar servis sınırında reddedilmeli",
        )
        self.assertEqual(
            after_balance, before_balance,
            "infinity bakiyeyi bozdu",
        )
        self.assertEqual(
            after_events, before_events,
            "reddedilmesi gereken işlem ledger olayı yazdı",
        )
        self.assertEqual(
            null_total, before_total,
            "bozulan hesap portföy toplamından sessizce düştü",
        )
