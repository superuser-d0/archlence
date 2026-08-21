"""Backup hash'i dosyayı bir bütün olarak belleğe almamalı.

ÖLÇÜLEN DURUM: `create_backup` ve `_verify_staged` `finance.db`'nin
SHA-256'sını `hashlib.sha256(db_copy.read_bytes()).hexdigest()` ile
hesaplıyordu. `read_bytes()` dosyanın TAMAMINI ek bir Python `bytes` nesnesi
olarak tahsis eder ve paket sınırı 256 MiB olduğuna göre bu, tek bir hash için
çeyrek gigabaytlık bir tepe demek. Ölçüldü (`tracemalloc`, tepe tahsis):

    dosya      read_bytes        streaming      azalma
     32 MiB    33.563.440         2.106.462     %93,7
     64 MiB    67.117.872         2.106.462     %96,9
    128 MiB   134.226.736         2.106.462     %98,4

Streaming'in tepesi dosya boyutundan BAĞIMSIZ. Bu dosyadaki kapı da tam olarak
onu sabitliyor: süreye değil, ÖLÇEKLENMEYE bakıyor — süre eşiği makineye bağlı
olurdu, bellek ölçeklenmesi değil.
"""
import hashlib
import os
import tempfile
import tracemalloc
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.backup_service import (
    _HASH_CHUNK,
    _sha256_file,
    create_backup,
    verify_backup,
)

#: Kapı için kullanılan boyutlar. CI'da hızlı kalsın diye küçük ama aradaki
#: dört kat, doğrusal büyümeyi görünür kılmaya yeter.
SMALL_MIB = 4
LARGE_MIB = 16


def _write_file(path, mebibytes):
    block = b"archlence-hash-benchmark-block\n" * 33_000  # ~1 MiB
    block = block[:1024 * 1024]
    with open(path, "wb") as handle:
        for _ in range(mebibytes):
            handle.write(block)
    return path


class Sha256FileContractTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def test_the_digest_is_byte_for_byte_identical(self):
        for size in (0, 1, _HASH_CHUNK - 1, _HASH_CHUNK, _HASH_CHUNK + 1):
            with self.subTest(size=size):
                path = self.root / f"blob-{size}.bin"
                path.write_bytes(os.urandom(size))
                self.assertEqual(
                    _sha256_file(path),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )

    def test_the_chunk_size_is_fixed_and_sane(self):
        self.assertEqual(_HASH_CHUNK, 1024 * 1024)

    def test_peak_memory_does_not_grow_with_the_file(self):
        small = _write_file(self.root / "small.bin", SMALL_MIB)
        large = _write_file(self.root / "large.bin", LARGE_MIB)

        def peak(function, path):
            tracemalloc.start()
            try:
                function(path)
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        small_peak = peak(_sha256_file, small)
        large_peak = peak(_sha256_file, large)

        # DOĞRUSAL DEĞİL: dosya 4 katına çıktığında tepe tahsis 4 katına
        # çıkmamalı. Eski yaklaşımda bu oran tam olarak 4,0 olurdu.
        self.assertLess(
            large_peak, small_peak * 2,
            f"tepe bellek dosyayla büyüdü: {small_peak:,} -> {large_peak:,}",
        )
        # Ve mutlak olarak da dosyadan çok küçük kalmalı.
        self.assertLess(large_peak, LARGE_MIB * 1024 * 1024 // 4)

    def test_the_old_approach_is_the_one_that_grows(self):
        """Karşılaştırma kapısı: kusurun kendisi ölçülebilir kalsın."""
        small = _write_file(self.root / "small2.bin", SMALL_MIB)
        large = _write_file(self.root / "large2.bin", LARGE_MIB)

        def peak(path):
            tracemalloc.start()
            try:
                hashlib.sha256(Path(path).read_bytes()).hexdigest()
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        self.assertGreater(peak(large), peak(small) * 2)

    def test_the_file_handle_is_released_on_the_error_path(self):
        path = _write_file(self.root / "boom.bin", 1)
        real_update = hashlib.sha256().update

        class _Boom(RuntimeError):
            pass

        def exploding_sha256(*args, **kwargs):
            digest = hashlib.new("sha256")

            class _Wrapper:
                def update(self, data):
                    raise _Boom("enjekte edilen hata")

                def hexdigest(self):
                    return digest.hexdigest()

            return _Wrapper()

        with mock.patch("services.backup_service.hashlib.sha256",
                        exploding_sha256):
            with self.assertRaises(_Boom):
                _sha256_file(path)

        # Windows açık handle'ı olan dosyayı sildirmez; silinebiliyorsa
        # tanıtıcı gerçekten kapanmış demektir.
        path.unlink()
        self.assertFalse(path.exists())
        del real_update


class BackupWithoutWholeFileReadsTest(unittest.TestCase):
    """`finance.db` için `Path.read_bytes` YASAK iken tur tamamlanmalı."""

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
        account_id = AccountService.create_account(
            "Yedek", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            account_id, 125.50, "expense", "Market", "açıklama"
        )

    def _forbid_database_read_bytes(self):
        real = Path.read_bytes

        def guarded(self_):
            if str(self_).endswith("finance.db"):
                raise AssertionError(
                    "finance.db bir bütün olarak belleğe alındı"
                )
            return real(self_)

        return mock.patch.object(Path, "read_bytes", guarded)

    def test_create_and_verify_never_slurp_the_database(self):
        with self._forbid_database_read_bytes():
            result = create_backup(
                self.package, self.PASSPHRASE,
                db_path=self.db_path, key_path=self.key_path,
            )
            verified = verify_backup(self.package, self.PASSPHRASE)

        self.assertEqual(verified["key"], self.key)
        self.assertEqual(
            result["database_sha256"],
            verified["metadata"]["database_sha256"],
        )

    def test_the_recorded_digest_matches_the_staged_database(self):
        import zipfile

        create_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
        )
        with closing(zipfile.ZipFile(self.package)) as archive:
            payload = archive.read("finance.db")
            import json

            metadata = json.loads(archive.read("metadata.json"))
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            metadata["database_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
