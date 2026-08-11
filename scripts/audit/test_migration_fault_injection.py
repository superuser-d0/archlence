"""Intentionally failing migration crash-consistency reproduction."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


class _FaultCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, parameters=()):
        normalized = " ".join(sql.split())
        if normalized.startswith(
            "ALTER TABLE accounts ADD COLUMN credit_limit"
        ):
            raise OSError("injected migration write failure")
        return self._cursor.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _FaultConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _FaultCursor(self._connection.cursor())

    def __getattr__(self, name):
        return getattr(self._connection, name)


class MigrationCrashConsistencyReproduction(unittest.TestCase):
    def test_failed_column_migration_does_not_leave_unbackfilled_guard(self):
        with tempfile.TemporaryDirectory(prefix="archlence-migration-fault-") as tmp:
            db_path = Path(tmp) / "finance.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    "CREATE TABLE accounts ("
                    "id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "type TEXT NOT NULL, balance REAL DEFAULT 0)"
                )
                conn.execute(
                    "INSERT INTO accounts VALUES (1,'Legacy Card','credit',-100)"
                )
                conn.commit()

            from database import db as db_module
            from database import init_db

            real = sqlite3.connect(db_path)
            real.row_factory = sqlite3.Row
            caught = None
            with mock.patch.object(
                init_db, "get_connection", return_value=_FaultConnection(real)
            ):
                try:
                    init_db.initialize_database()
                except OSError as exc:
                    caught = exc
            # Process exit closes the leaked connection and rolls back its open
            # DML transaction, but the first ALTER ran before that transaction.
            real.close()

            with mock.patch.object(db_module, "DB_NAME", str(db_path)):
                init_db.initialize_database()  # next-launch recovery attempt

            with closing(sqlite3.connect(db_path)) as conn:
                columns = [
                    row[1] for row in conn.execute("PRAGMA table_info(accounts)")
                ]
                account_type = conn.execute(
                    "SELECT account_type FROM accounts WHERE id=1"
                ).fetchone()[0]
            print(
                "AUDIT_STATE migration_fault "
                f"caught_exception={type(caught).__name__ if caught else 'NONE'} "
                f"account_type_column={'account_type' in columns} "
                f"account_type_after_retry={account_type!r}"
            )
            self.assertIsNotNone(caught)
            self.assertEqual(
                account_type,
                "credit_card",
                "partial ALTER guard prevents retry from backfilling legacy row",
            )


if __name__ == "__main__":
    unittest.main()
