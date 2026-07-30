import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from utils.errors import EncryptionError


class TransactionEncryptionFailureTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Fail Closed", "checking", initial_balance=1000
        )

    def tearDown(self):
        self.db_patch.stop()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_encryption_failure_writes_neither_plaintext_nor_transaction(self):
        from services.transaction_service import TransactionService

        secret_description = "çok hassas açıklama"
        with mock.patch(
            "services.transaction_service.encrypt",
            side_effect=EncryptionError("injected"),
        ):
            with self.assertRaises(EncryptionError):
                TransactionService.add_transaction(
                    self.account_id,
                    125.50,
                    "expense",
                    "Test",
                    secret_description,
                )

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT amount, description FROM transactions"
            ).fetchall()
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?",
                (self.account_id,),
            ).fetchone()[0]

        self.assertEqual(rows, [])
        self.assertEqual(balance, 1000.0)


if __name__ == "__main__":
    unittest.main()
