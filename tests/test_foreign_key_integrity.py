"""`transactions.account_id -> accounts.id` GERÇEKTEN zorlanmalı.

ÖLÇÜLEN KUSUR: kısıt şemada duruyordu ama hiçbir şey yapmıyordu. SQLite'ta
foreign key zorlaması BAĞLANTI BAŞINA ve VARSAYILAN OLARAK KAPALIDIR
(geriye dönük uyumluluk kararı, 3.6.19'dan beri böyle). Ölçüm:

    >>> conn = get_connection()
    >>> conn.execute("PRAGMA foreign_keys").fetchone()[0]
    0
    >>> conn.execute("INSERT INTO transactions (account_id, ...) VALUES (999999, ...)")

    >>> conn.execute("PRAGMA foreign_key_check").fetchall()
    [<ihlal>]

Yani var olmayan bir hesaba işlem yazmak serbestti ve şema bunu yasakladığını
sanıyordu. Öksüz bir işlem, hiçbir hesabın bakiyesine bağlı olmayan ama
raporlarda görünen para demektir.

FAIL-CLOSED: mevcut öksüz kayıtlar SESSİZCE SİLİNMEZ, başka hesaba
BAĞLANMAZ ve finansal geçmiş yeniden yazılmaz. Açılış durur ve hangi
tablonun hangi satırının hangi ebeveyni kaybettiğini söyler; kararı
kullanıcı verir.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from utils.errors import FinancialDataIntegrityError

_TX_INSERT = (
    "INSERT INTO transactions "
    "(account_id, amount, type, category, description, transaction_date) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)


class ForeignKeyEnforcementTest(unittest.TestCase):
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

        from database.init_db import initialize_database

        initialize_database()

    def test_every_connection_has_foreign_keys_on(self):
        from database.db import get_connection

        with closing(get_connection()) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_managed_connection_inherits_the_same_guarantee(self):
        from database.db import managed_connection

        with managed_connection() as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_transaction_for_a_missing_account_is_refused(self):
        from database.db import get_connection

        with closing(get_connection()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    _TX_INSERT,
                    (999999, "x", "expense", "Test", "y", "2026-01-01 00:00:00"),
                )
                conn.commit()

    def test_deleting_an_account_with_transactions_is_refused(self):
        """Ebeveyni çocuklardan önce silmek artık sessizce geçmiyor."""
        from database.db import get_connection
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Silme Hesabı", "checking", initial_balance=500
        )
        TransactionService.add_transaction(
            account_id, 10.0, "expense", "Market", "test"
        )
        with closing(get_connection()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
                conn.commit()

    def test_normal_account_and_transaction_lifecycle_still_works(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Normal Hesap", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            account_id, 250.0, "expense", "Market", "alışveriş"
        )
        TransactionService.add_transaction(
            account_id, 100.0, "income", "Maaş", "ek gelir"
        )
        self.assertAlmostEqual(
            AccountService.get_account(account_id)["balance"], 850.0
        )

    def test_credit_card_deletion_is_still_atomic_with_enforcement_on(self):
        """`delete_credit_card` çocukları ebeveynden ÖNCE siliyor; sıra doğru."""
        from database.db import get_connection
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Kart", "credit_card", initial_balance=0, credit_limit=10000
        )
        TransactionService.add_transaction(
            card_id, 300.0, "expense", "Market", "kart harcaması"
        )
        AccountService.delete_credit_card(card_id)

        with closing(get_connection()) as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT id FROM accounts WHERE id = ?", (card_id,)
                ).fetchone()
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
                    (card_id,),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("PRAGMA foreign_key_check").fetchall(), []
            )


class FullResetWithEnforcementTest(unittest.TestCase):
    """Tam veri silme, zorlama açıkken de çalışmalı.

    `main.py::delete_all_data` tabloları `sqlite_master` sırasıyla siliyor ve
    o sıra `accounts`'ı `transactions`'tan ÖNCE getiriyor. Zorlama açılınca bu
    döngü `FOREIGN KEY constraint failed` ile düşüyordu — ölçüldü. Bu test o
    sırayı birebir tekrarlar ve `PRAGMA defer_foreign_keys` çözümünü sabitler.
    """

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

        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        initialize_database()
        account_id = AccountService.create_account(
            "Sıfırlanacak", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            account_id, 50.0, "expense", "Market", "silinecek"
        )

    def test_wiping_every_table_in_schema_order_still_commits(self):
        from database.db import managed_connection

        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            cursor.execute("PRAGMA defer_foreign_keys = ON")
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
            names = [row["name"] for row in cursor.fetchall()]
            self.assertLess(names.index("accounts"), names.index("transactions"))
            for name in names:
                cursor.execute(f'DELETE FROM "{name.replace(chr(34), chr(34) * 2)}"')
            cursor.execute("DELETE FROM sqlite_sequence")
            conn.commit()

        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("PRAGMA foreign_key_check").fetchall(), []
            )

    def test_deferred_enforcement_still_refuses_a_genuinely_broken_commit(self):
        """Erteleme zorlamayı KAPATMAZ: commit'te tutarsızlık varsa reddedilir."""
        from database.db import managed_connection

        with self.assertRaises(sqlite3.IntegrityError):
            with managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN")
                cursor.execute("PRAGMA defer_foreign_keys = ON")
                cursor.execute(
                    _TX_INSERT,
                    (555555, "x", "expense", "T", "y", "2026-01-01 00:00:00"),
                )
                conn.commit()


class OrphanedLegacyDatabaseTest(unittest.TestCase):
    """Kısıt zorlanmadan yazılmış eski profiller fail-closed olmalı."""

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

        from database.init_db import initialize_database

        initialize_database()

    def _inject_orphan(self):
        """FK zorlaması KAPALI bir ham bağlantıyla öksüz satır yazar.

        Eski sürümün yaptığının birebir aynısı — bu yüzden `get_connection`
        değil, çıplak `sqlite3.connect` kullanılıyor.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                _TX_INSERT,
                (424242, "x", "expense", "Eski", "öksüz", "2026-01-01 00:00:00"),
            )
            conn.commit()

    def test_orphaned_rows_stop_startup_instead_of_being_repaired(self):
        from database.init_db import initialize_database

        self._inject_orphan()
        with closing(sqlite3.connect(self.db_path)) as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
                (424242,),
            ).fetchone()[0]
        self.assertEqual(before, 1)

        with self.assertRaises(FinancialDataIntegrityError) as caught:
            initialize_database()


        message = str(caught.exception)
        self.assertIn("transactions", message)
        self.assertIn("accounts", str(caught.exception.reason))


        with closing(sqlite3.connect(self.db_path)) as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
                (424242,),
            ).fetchone()[0]
        self.assertEqual(after, 1)

    def test_a_clean_database_upgrades_without_complaint(self):
        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Temiz", "checking", initial_balance=100
        )
        TransactionService.add_transaction(
            account_id, 10.0, "expense", "Market", "temiz"
        )
        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA foreign_key_check").fetchall(), []
            )


class BackupRefusesOrphanedDatabaseTest(unittest.TestCase):
    """Restore edilecek DB'deki ihlal, restore'dan ÖNCE yakalanmalı."""

    PASSPHRASE = "test-kurtarma-parolasi-2026"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.package = root / "backup.archlence-backup"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)
        os.chmod(self.key_path, 0o600)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Yedek", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            self.account_id, 125.50, "expense", "Market", "açıklama"
        )

    def test_a_package_holding_orphaned_rows_is_refused(self):
        from services.backup_service import create_backup
        from utils.errors import IntegrityVerificationError

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                _TX_INSERT,
                (777777, "x", "expense", "Eski", "öksüz", "2026-01-01 00:00:00"),
            )
            conn.commit()

        with self.assertRaises(IntegrityVerificationError):
            create_backup(
                self.package,
                self.PASSPHRASE,
                db_path=self.db_path,
                key_path=self.key_path,
            )

    def test_a_clean_package_still_verifies(self):
        from services.backup_service import create_backup, verify_backup

        create_backup(
            self.package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )
        self.assertEqual(
            verify_backup(self.package, self.PASSPHRASE)["key"], self.key
        )


if __name__ == "__main__":
    unittest.main()
