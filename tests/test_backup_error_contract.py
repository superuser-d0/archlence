"""Bozuk paket HER ZAMAN `IntegrityVerificationError` üretmeli.

ÖLÇÜLEN KAÇAKLAR — ikisi de sözleşmenin dışına çıkıyordu:

    metadata.json = []
      -> AttributeError: 'list' object has no attribute 'get'
    metadata.json = null / "metin" / 42
      -> AttributeError: 'NoneType'/'str'/'int' object has no attribute 'get'

    aead_records_verified = "abc"   (imzası geçerli metadata ile)
      -> ValueError: invalid literal for int() with base 10: 'abc'
    aead_records_verified = None
      -> TypeError: int() argument must be a string ... or a real number

    ZIP compression method = 99
      -> NotImplementedError: That compression method is not supported

`AttributeError`/`ValueError`/`TypeError`/`NotImplementedError` çağırana
"programlama hatası" gibi görünür; `IntegrityVerificationError` ise "bu paket
bozuk" der. Restore akışı yalnız ikincisini bekliyor, yani kaçaklar kullanıcıya
çökme olarak yansıyordu.

TESTLERİN ÇOĞU METADATA'YI YENİDEN İMZALIYOR. Aksi hâlde authentication tag
uyuşmazlığı erken devreye girip alan tipini hiç sınamadan reddederdi — yani
sözleşmeyi değil, HMAC'i ölçmüş olurduk. Paketi kendi parolasıyla üreten bir
saldırgan da tam olarak bu durumda olurdu.
"""
import hashlib
import json
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from services.backup_service import (
    _backup_auth_tag,
    create_backup,
    restore_backup,
    verify_backup,
)
from utils.errors import DataMigrationError, IntegrityVerificationError


class BackupErrorContractTest(unittest.TestCase):
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
            "Yedek", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            self.account_id, 125.50, "expense", "Market", "Gizli açıklama"
        )
        create_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
        )
        with zipfile.ZipFile(self.package) as archive:
            self.members = {n: archive.read(n) for n in archive.namelist()}
        self.metadata = json.loads(self.members["metadata.json"])

    # ── yardımcılar ──────────────────────────────────────────────────────
    def _resign(self, metadata):
        """Metadata'yı DOĞRU imzalar; erken HMAC reddini devre dışı bırakır.

        İmza salt olmadan hesaplanamaz; o durumda metadata imzasız döner ve
        doğrulama zaten reddetmelidir."""
        material = dict(metadata)
        material.pop("authentication_tag", None)
        try:
            material["authentication_tag"] = _backup_auth_tag(
                material, self.PASSPHRASE
            )
        except IntegrityVerificationError:
            pass
        return material

    def _build(self, overrides):
        members = dict(self.members)
        members.update(overrides)
        with zipfile.ZipFile(
            self.hostile, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        return self.hostile

    def _metadata_package(self, **overrides):
        material = self._resign(dict(self.metadata, **overrides))
        return self._build({"metadata.json": json.dumps(material).encode()})

    def _profile_fingerprint(self):
        return (
            hashlib.sha256(self.db_path.read_bytes()).hexdigest(),
            hashlib.sha256(self.key_path.read_bytes()).hexdigest(),
            hashlib.sha256(self.config_path.read_bytes()).hexdigest(),
        )

    def _assert_rejected(self, package):
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(package, self.PASSPHRASE)

    # ── JSON kök tipleri ─────────────────────────────────────────────────
    def test_metadata_root_must_be_an_object(self):
        for label, payload in (
            ("[]", b"[]"), ("null", b"null"), ('"metin"', b'"metin"'),
            ("42", b"42"), ("true", b"true"),
        ):
            with self.subTest(root=label):
                self._assert_rejected(
                    self._build({"metadata.json": payload})
                )

    def test_recovery_root_must_be_an_object(self):
        for label, payload in (
            ("[]", b"[]"), ("null", b"null"), ('"metin"', b'"metin"'),
            ("42", b"42"),
        ):
            with self.subTest(root=label):
                self._assert_rejected(
                    self._build({"key.recovery.json": payload})
                )

    # ── metadata alan tipleri (doğru imzalı) ─────────────────────────────
    def test_aead_record_count_must_be_a_real_non_negative_int(self):
        for label, value in (
            ("True", True), ("False", False), ('"12"', "12"), ("2.0", 2.0),
            ("-5", -5), ('"abc"', "abc"), ("None", None), ("[]", []),
            ('"1e400"', "1" + "0" * 400),
        ):
            with self.subTest(value=label):
                self._assert_rejected(
                    self._metadata_package(aead_records_verified=value)
                )

    def test_digest_fields_must_be_64_char_lowercase_hex(self):
        for field in ("database_sha256", "key_fingerprint"):
            for label, value in (
                ("nonhex", "ZZZZ"), ("kısa", "abc123"), ("None", None),
                ("42", 42), ("[]", []),
                ("büyük harf", "A" * 64),
                ("65 hane", "a" * 65),
            ):
                with self.subTest(field=field, value=label):
                    self._assert_rejected(
                        self._metadata_package(**{field: value})
                    )

    def test_format_version_must_be_the_integer_two(self):
        for label, value in (
            ('"2"', "2"), ("True", True), ("2.0", 2.0), ("None", None),
            ("3", 3), ("1", 1),
        ):
            with self.subTest(value=label):
                self._assert_rejected(
                    self._metadata_package(format_version=value)
                )

    def test_authentication_salt_must_be_a_string(self):
        for label, value in (("None", None), ("[]", []), ("42", 42)):
            with self.subTest(value=label):
                material = dict(self.metadata, authentication_salt=value)
                # İmzalanamayacağı için ham hâliyle paketlenir; sözleşme yine
                # `IntegrityVerificationError` demeli.
                self._assert_rejected(
                    self._build({"metadata.json": json.dumps(material).encode()})
                )

    def test_a_missing_metadata_field_is_rejected(self):
        for field in (
            "format_version", "authentication_salt", "database_sha256",
            "key_fingerprint", "aead_records_verified",
        ):
            with self.subTest(field=field):
                material = dict(self.metadata)
                material.pop(field)
                self._assert_rejected(
                    self._build({"metadata.json": json.dumps(
                        self._resign(material)).encode()})
                )

    # ── ZIP sıkıştırma yöntemi ───────────────────────────────────────────
    def test_an_unsupported_compression_method_is_an_integrity_error(self):
        raw = bytearray(self.package.read_bytes())
        # Yerel başlık PK\x03\x04 ofset 8, merkezi dizin PK\x01\x02 ofset 10.
        for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
            cursor = 0
            while True:
                cursor = raw.find(signature, cursor)
                if cursor < 0:
                    break
                struct.pack_into("<H", raw, cursor + offset, 99)
                cursor += 4
        self.hostile.write_bytes(bytes(raw))
        self._assert_rejected(self.hostile)

    # ── profil ve journal dokunulmadan kalmalı ───────────────────────────
    def test_no_rejected_package_touches_the_profile_or_the_journal(self):
        from services.backup_service import _restore_journal_dir

        packages = [
            self._build({"metadata.json": b"[]"}),
            self._metadata_package(aead_records_verified="abc"),
            self._metadata_package(database_sha256="ZZZZ"),
        ]
        before = self._profile_fingerprint()
        for package in packages:
            with self.subTest(package=package.name):
                with self.assertRaises(
                    (IntegrityVerificationError, DataMigrationError)
                ):
                    restore_backup(
                        package, self.PASSPHRASE,
                        db_path=self.db_path, key_path=self.key_path,
                        config_path=str(self.config_path),
                        safety_backup_path=self.safety,
                    )
                self.assertEqual(self._profile_fingerprint(), before)
                self.assertFalse(_restore_journal_dir(self.db_path).exists())

    # ── geçerli paket bozulmamalı ────────────────────────────────────────
    def test_a_valid_package_still_verifies_and_restores(self):
        verified = verify_backup(self.package, self.PASSPHRASE)
        self.assertEqual(verified["key"], self.key)
        self.assertEqual(verified["metadata"]["format_version"], 2)

        result = restore_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
            safety_backup_path=self.safety,
        )
        self.assertTrue(result["restored"])

    def test_the_existing_kdf_round_count_is_untouched(self):
        from services.backup_service import _RECOVERY_ITERATIONS

        recovery = json.loads(self.members["key.recovery.json"])
        self.assertEqual(recovery["iterations"], 600_000)
        self.assertEqual(_RECOVERY_ITERATIONS, 600_000)


if __name__ == "__main__":
    unittest.main()
