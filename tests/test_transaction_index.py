"""`transactions.account_id` indeksi — yapısal kapı.

ÖLÇÜLEN DURUM: şemada `FOREIGN KEY(account_id) REFERENCES accounts(id)` vardı
ama o sütunda İNDEKS YOKTU. SQLite ebeveyn tarafına (PRIMARY KEY) indeks
zorlar, çocuk tarafına zorlamaz. `PRAGMA index_list(transactions)` boş
dönüyordu ve her account_id filtresi tam tarama yapıyordu:

    SELECT ... WHERE account_id = ?           ->  SCAN transactions
    SELECT COUNT(*) ... WHERE account_id = ?  ->  SCAN transactions

100.000 işlem / 8 hesap üzerinde ölçülen medyanlar:

    bağımlılık sayımı    13,858 ms  ->  0,587 ms   (23,6x)
    hesap silme taraması 21,528 ms  ->  6,236 ms   (3,5x)
    hesap ekstresi       16,737 ms  -> 15,058 ms   (1,1x — ORDER BY hâlâ
                                                    geçici B-tree kuruyor)

ASIL GARANTİ SÜRE DEĞİL, PLANDIR. Süre eşiği makineye, diske ve dosya
önbelleğine bağlı olurdu; sorgu planı deterministik. Süre ölçümü
`scripts/audit/measure_transaction_index.py` içinde, kapı burada.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

INDEX_NAME = "idx_transactions_account_id"


class TransactionIndexTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "finance.db"
        self.key = os.urandom(32)
        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

    def _indexes(self, path=None):
        with closing(sqlite3.connect(path or self.db_path)) as conn:
            return {
                row[1] for row in conn.execute("PRAGMA index_list(transactions)")
            }

    def _plan(self, sql, path=None):
        with closing(sqlite3.connect(path or self.db_path)) as conn:
            return " | ".join(
                str(row[-1])
                for row in conn.execute("EXPLAIN QUERY PLAN " + sql, (1,))
            )

    def test_a_fresh_schema_has_the_index(self):
        from database.init_db import initialize_database

        initialize_database()
        self.assertIn(INDEX_NAME, self._indexes())

    def test_an_upgraded_schema_gets_the_same_index(self):
        """Eski kuşaktan gelen profil de aynı indeksi almalı."""
        from database.init_db import initialize_database

        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        self.assertNotIn(INDEX_NAME, self._indexes())

        initialize_database()
        self.assertIn(INDEX_NAME, self._indexes())

    def test_creating_the_index_is_idempotent(self):
        from database.init_db import initialize_database

        initialize_database()
        initialize_database()
        initialize_database()
        self.assertEqual(
            len([name for name in self._indexes() if name == INDEX_NAME]), 1
        )

    def test_account_filtered_queries_use_the_index(self):
        from database.init_db import initialize_database

        initialize_database()
        for sql in (
            "SELECT id FROM transactions WHERE account_id = ?",
            "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
            "SELECT id, amount FROM transactions WHERE account_id = ? "
            "ORDER BY transaction_date DESC LIMIT 50",
        ):
            with self.subTest(sql=sql[:48]):
                plan = self._plan(sql)
                self.assertIn(INDEX_NAME, plan, plan)
                self.assertNotIn("SCAN transactions", plan, plan)

    def test_the_index_changes_neither_rows_nor_their_order(self):
        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        initialize_database()
        account_id = AccountService.create_account(
            "İndeks", "checking", initial_balance=100000
        )
        for index in range(25):
            TransactionService.add_transaction(
                account_id, 10.0 + index, "expense", "Market", f"kayıt-{index}"
            )

        query = (
            "SELECT id, account_id, transaction_date FROM transactions "
            "WHERE account_id = ? ORDER BY id"
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            with_index = conn.execute(query, (account_id,)).fetchall()
            conn.execute(f"DROP INDEX {INDEX_NAME}")
            conn.commit()
            without_index = conn.execute(query, (account_id,)).fetchall()

        self.assertEqual(with_index, without_index)
        self.assertEqual(len(with_index), 25)

    def test_the_balance_events_index_is_still_there(self):
        """Var olan indeks kaybolmamalı."""
        from database.init_db import initialize_database

        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            names = {
                row[1]
                for row in conn.execute("PRAGMA index_list(balance_events)")
            }
        self.assertIn("idx_balance_events_ts", names)


if __name__ == "__main__":
    unittest.main()
