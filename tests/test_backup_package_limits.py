"""Gelen backup paketi, açılmadan ve mevcut profile dokunulmadan sınanmalı.

ÖLÇÜLEN KUSURLAR (ikisi de bu dosyadaki testlerle sabitleniyor):

1. KAYNAK TÜKETİMİ. `verify_backup` üyeleri `ZipInfo.file_size`, toplam
   açılmış boyut ve sıkıştırma oranı sınanmadan `archive.extract` ile diske
   yazıyordu. Ölçüldü: 8.514 baytlık bir paket `finance.db` üyesini
   **8.388.608 bayta** açtı ve ret ancak bu yazımdan SONRA, authentication
   adımında geldi. Sınır yok demek, paket boyutunun 1000 katı disk demek.

2. ÇİFT AÇMA. `restore_backup` paketi önce kendisi extract ediyor, sonra
   `verify_backup` aynı paketi İKİNCİ kez açıyordu. Saldırgan kontrollü bir
   pakette bu, maliyeti ikiye katlamanın yanı sıra "doğrulanmadan diske
   yazma" penceresini de ikiye katlıyordu.

Ayrıca: gelen paket, mevcut veritabanına/anahtara dokunulmadan ÖNCE
doğrulanmalı. Eski sırada güvenlik yedeği (tam bir `create_backup` turu)
saldırganın gönderdiği paket hiç sınanmadan önce çalışıyordu.
"""
import hashlib
import io
import os
import sqlite3
import struct
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.backup_service import (
    create_backup,
    restore_backup,
    verify_backup,
)
from utils.errors import DataMigrationError, IntegrityVerificationError


class BackupPackageLimitTest(unittest.TestCase):
    PASSPHRASE = "test-kurtarma-parolasi-2026"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.config_path = root / "config.json"
        self.package = root / "backup.archlence-backup"
        self.hostile = root / "hostile.archlence-backup"
        self.safety = root / "safety.archlence-backup"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)
        os.chmod(self.key_path, 0o600)
        self.config_path.write_text('{"tema": "koyu"}', encoding="utf-8")

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
            "Yedek Hesabı", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            self.account_id, 125.50, "expense", "Market", "Gizli açıklama"
        )
        create_backup(
            self.package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
            config_path=str(self.config_path),
        )


    def _valid_members(self):
        with zipfile.ZipFile(self.package) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def _build(self, members, path=None, *, compresslevel=9):
        """`members`: {ad: bayt} ya da {ad: (ZipInfo, bayt)}."""
        path = path or self.hostile
        with zipfile.ZipFile(
            path, "w", zipfile.ZIP_DEFLATED, compresslevel=compresslevel
        ) as archive:
            for name, payload in members.items():
                if isinstance(payload, tuple):
                    info, data = payload
                    archive.writestr(info, data)
                else:
                    archive.writestr(name, payload)
        return path

    def _profile_fingerprint(self):
        return (
            hashlib.sha256(self.db_path.read_bytes()).hexdigest(),
            hashlib.sha256(self.key_path.read_bytes()).hexdigest(),
            hashlib.sha256(self.config_path.read_bytes()).hexdigest(),
        )

    def _restore(self, package):
        return restore_backup(
            package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
            config_path=str(self.config_path),
            safety_backup_path=self.safety,
        )


    def test_zip_bomb_is_rejected_before_the_payload_reaches_disk(self):
        members = self._valid_members()
        members["finance.db"] = b"\0" * (8 * 1024 * 1024)
        self._build(members)

        with zipfile.ZipFile(self.hostile) as archive:
            info = archive.getinfo("finance.db")
        self.assertGreater(info.file_size / info.compress_size, 500)

        largest = {"bytes": 0}
        real_open = io.open

        def spy(file, mode="r", *args, **kwargs):
            handle = real_open(file, mode, *args, **kwargs)
            if "w" in str(mode) and "finance.db" in str(file):
                handle = _SizeSpy(handle, largest)
            return handle

        with mock.patch("io.open", spy):
            with self.assertRaises(IntegrityVerificationError):
                verify_backup(self.hostile, self.PASSPHRASE)
        self.assertLess(
            largest["bytes"], 1024 * 1024,
            "zip bombası reddedilmeden önce diske megabaytlarca yazıldı",
        )

    def test_member_larger_than_its_limit_is_rejected(self):
        from services.backup_service import MAX_SMALL_MEMBER_BYTES

        members = self._valid_members()
        members["metadata.json"] = b"x" * (MAX_SMALL_MEMBER_BYTES + 1)
        self._build(members, compresslevel=0)
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_total_uncompressed_size_is_bounded(self):
        from services.backup_service import MAX_TOTAL_BYTES

        self.assertGreater(MAX_TOTAL_BYTES, 0)
        self.assertLess(MAX_TOTAL_BYTES, 2 * 1024 * 1024 * 1024)

    def test_a_lying_header_is_caught_by_the_real_byte_counter(self):
        """ZIP başlığındaki `file_size` GÜVENİLİR DEĞİL — akışın kendisi sayılmalı."""
        from services.backup_service import MAX_SMALL_MEMBER_BYTES

        members = self._valid_members()
        members["metadata.json"] = b"y" * (MAX_SMALL_MEMBER_BYTES + 4096)
        self._build(members)

        real_infolist = zipfile.ZipFile.infolist

        def lying_infolist(archive):
            infos = []
            for info in real_infolist(archive):
                clone = zipfile.ZipInfo(info.filename, info.date_time)
                clone.compress_type = info.compress_type
                clone.external_attr = info.external_attr
                clone.flag_bits = info.flag_bits
                clone.header_offset = info.header_offset
                clone.CRC = info.CRC
                clone.compress_size = info.compress_size

                clone.file_size = min(info.file_size, 64)
                infos.append(clone)
            return infos

        with mock.patch.object(zipfile.ZipFile, "infolist", lying_infolist):
            with self.assertRaises(IntegrityVerificationError):
                verify_backup(self.hostile, self.PASSPHRASE)


    def test_unexpected_member_is_rejected(self):
        members = self._valid_members()
        members["notlar.txt"] = b"merhaba"
        self._build(members)
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_duplicate_member_is_rejected(self):
        members = self._valid_members()
        with zipfile.ZipFile(self.hostile, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
            archive.writestr("finance.db", b"ikinci kopya")
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_traversal_absolute_and_drive_paths_are_rejected(self):
        for hostile_name in (
            "../finance.db",
            "/etc/finance.db",
            "C:/finance.db",
            "..\\finance.db",
            "sub/finance.db",
        ):
            with self.subTest(name=hostile_name):
                members = self._valid_members()
                payload = members.pop("finance.db")
                members[hostile_name] = payload
                self._build(members)
                with self.assertRaises(IntegrityVerificationError):
                    verify_backup(self.hostile, self.PASSPHRASE)

    def test_directory_member_is_rejected(self):
        members = self._valid_members()
        with zipfile.ZipFile(self.hostile, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
            archive.writestr("finance.db/", b"")
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_symlink_member_is_rejected(self):
        members = self._valid_members()
        info = zipfile.ZipInfo("config.json")

        info.external_attr = (0o120777 << 16)
        info.create_system = 3
        members["config.json"] = (info, b"/etc/passwd")
        self._build(members)
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_encrypted_member_is_rejected(self):
        members = self._valid_members()
        self._build(members)
        _flip_encryption_bit(self.hostile, b"finance.db")
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)

    def test_corrupt_archive_becomes_an_integrity_error(self):
        raw = bytearray(self.package.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        self.hostile.write_bytes(bytes(raw))
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.hostile, self.PASSPHRASE)


    def test_restore_stages_the_incoming_package_only_once(self):
        opens = []
        real_init = zipfile.ZipFile.__init__

        def counting_init(self_, file, *args, **kwargs):
            try:
                opens.append(os.path.abspath(os.fspath(file)))
            except TypeError:
                pass
            return real_init(self_, file, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "__init__", counting_init):
            self._restore(self.package)

        incoming = os.path.abspath(str(self.package))
        self.assertEqual(
            opens.count(incoming), 1,
            f"gelen paket {opens.count(incoming)} kez açıldı: {opens}",
        )

    def test_hostile_package_leaves_the_profile_byte_for_byte_intact(self):
        members = self._valid_members()
        members["finance.db"] = b"\0" * (8 * 1024 * 1024)
        self._build(members)
        before = self._profile_fingerprint()

        with self.assertRaises((IntegrityVerificationError, DataMigrationError)):
            self._restore(self.hostile)

        self.assertEqual(self._profile_fingerprint(), before)

    def test_hostile_package_starts_no_restore_journal(self):
        from services.backup_service import _restore_journal_dir

        members = self._valid_members()
        members["notlar.txt"] = b"merhaba"
        self._build(members)
        with self.assertRaises((IntegrityVerificationError, DataMigrationError)):
            self._restore(self.hostile)
        self.assertFalse(_restore_journal_dir(self.db_path).exists())

    def test_valid_package_still_verifies_and_restores(self):
        verified = verify_backup(self.package, self.PASSPHRASE)
        self.assertEqual(verified["key"], self.key)
        self.assertIsNotNone(verified["config"])

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE accounts SET balance = 9999 WHERE id = ?",
                (self.account_id,),
            )
            conn.commit()
        result = self._restore(self.package)
        self.assertTrue(result["restored"])
        self.assertTrue(self.safety.exists())
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?",
                (self.account_id,),
            ).fetchone()[0]
        self.assertEqual(balance, 874.5)


class _SizeSpy:
    """Yazılan en büyük dosya boyutunu ölçen ince sarmalayıcı."""

    def __init__(self, handle, largest):
        self._handle = handle
        self._largest = largest
        self._written = 0

    def write(self, data):
        self._written += len(data)
        self._largest["bytes"] = max(self._largest["bytes"], self._written)
        return self._handle.write(data)

    def __getattr__(self, name):
        return getattr(self._handle, name)

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, *exc):
        return self._handle.__exit__(*exc)


def _flip_encryption_bit(path, member_name):
    """Merkezi dizindeki ve yerel başlıktaki 'şifreli' bayrağını açar."""
    raw = bytearray(path.read_bytes())

    cursor = 0
    while True:
        cursor = raw.find(b"PK\x03\x04", cursor)
        if cursor < 0:
            break
        name_len = struct.unpack_from("<H", raw, cursor + 26)[0]
        name = bytes(raw[cursor + 30:cursor + 30 + name_len])
        if name == member_name:
            flags = struct.unpack_from("<H", raw, cursor + 6)[0]
            struct.pack_into("<H", raw, cursor + 6, flags | 0x1)
        cursor += 4

    cursor = 0
    while True:
        cursor = raw.find(b"PK\x01\x02", cursor)
        if cursor < 0:
            break
        name_len = struct.unpack_from("<H", raw, cursor + 28)[0]
        name = bytes(raw[cursor + 46:cursor + 46 + name_len])
        if name == member_name:
            flags = struct.unpack_from("<H", raw, cursor + 8)[0]
            struct.pack_into("<H", raw, cursor + 8, flags | 0x1)
        cursor += 4
    path.write_bytes(bytes(raw))


if __name__ == "__main__":
    unittest.main()
