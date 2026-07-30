"""Verified, password-protected backup and rollback-safe restore."""

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256

from database.db import DB_NAME
from utils import aead_crypto
from utils.app_paths import data_dir
from utils.errors import (
    DataMigrationError,
    IntegrityVerificationError,
    KeyUnavailableError,
)

BACKUP_FORMAT_VERSION = 1
_RECOVERY_ITERATIONS = 600_000
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32
_AEAD_PREFIX = "AEADv1:"

ENCRYPTED_FIELDS = {
    "transactions": ("amount", "description"),
    "active_debts": ("debt_name", "total_amount", "monthly_payment"),
    "active_assets": ("purchase_price", "quantity"),
    "recurring_payments": ("name", "amount"),
    "savings_goals": ("goal_name",),
    "installment_plans": ("description", "total_amount", "monthly_amount"),
}


def default_key_path():
    return str(Path(data_dir()) / "encryption.key")


def _key_provider(key_path=None, provider=None):
    if provider is not None:
        return provider
    if key_path is not None:
        from utils.key_provider import FileKeyProvider

        return FileKeyProvider(str(key_path))
    from utils.key_provider import create_platform_key_provider

    return create_platform_key_provider(data_dir())


def _require_passphrase(passphrase):
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Kurtarma parolası en az 12 karakter olmalıdır.")


def encrypt_recovery_material(key, passphrase):
    _require_passphrase(passphrase)
    if len(key) != _KEY_LEN:
        raise KeyUnavailableError("Yedeklenecek şifreleme anahtarı geçersiz.")
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    wrapping_key = PBKDF2(
        passphrase.encode("utf-8"),
        salt,
        dkLen=_KEY_LEN,
        count=_RECOVERY_ITERATIONS,
        hmac_hash_module=SHA256,
    )
    cipher = AES.new(wrapping_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(key)
    return {
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": _RECOVERY_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_recovery_material(payload, passphrase):
    _require_passphrase(passphrase)
    try:
        salt = base64.b64decode(payload["salt"], validate=True)
        nonce = base64.b64decode(payload["nonce"], validate=True)
        tag = base64.b64decode(payload["tag"], validate=True)
        ciphertext = base64.b64decode(payload["ciphertext"], validate=True)
        iterations = int(payload["iterations"])
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrityVerificationError(
            "Backup kurtarma materyali bozuk."
        ) from exc
    wrapping_key = PBKDF2(
        passphrase.encode("utf-8"),
        salt,
        dkLen=_KEY_LEN,
        count=iterations,
        hmac_hash_module=SHA256,
    )
    try:
        cipher = AES.new(wrapping_key, AES.MODE_GCM, nonce=nonce)
        key = cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError as exc:
        raise IntegrityVerificationError(
            "Backup parolası yanlış veya kurtarma materyali bozuk."
        ) from exc
    if len(key) != _KEY_LEN:
        raise IntegrityVerificationError("Backup anahtar uzunluğu geçersiz.")
    return key


def _sqlite_backup(source_path, destination_path):
    source_uri = f"file:{Path(source_path).resolve()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        with closing(sqlite3.connect(destination_path)) as destination:
            source.backup(destination)


def _integrity_check(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise IntegrityVerificationError(
            "Backup veritabanı SQLite bütünlük kontrolünü geçemedi."
        )


def _existing_tables(conn):
    return {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def verify_database_key(db_path, key):
    """Authenticate every AEAD field in the database with an explicit key."""
    checked = 0
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        tables = _existing_tables(conn)
        for table, fields in ENCRYPTED_FIELDS.items():
            if table not in tables:
                continue
            columns = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table})")
            }
            usable = [field for field in fields if field in columns]
            if not usable:
                continue
            selected = ", ".join(["id", *usable])
            for row in conn.execute(f"SELECT {selected} FROM {table}"):
                for field in usable:
                    value = row[field]
                    if value is None or str(value).strip() == "":
                        continue
                    text = str(value)
                    if not text.startswith(_AEAD_PREFIX):
                        continue
                    try:
                        aead_crypto.decrypt(
                            text[len(_AEAD_PREFIX):], key
                        )
                    except (aead_crypto.DecryptionError, ValueError) as exc:
                        raise IntegrityVerificationError(
                            f"Backup anahtarı {table} id={row['id']} "
                            f"field={field} kaydıyla eşleşmiyor."
                        ) from exc
                    checked += 1
    return checked


def create_backup(
    destination,
    passphrase,
    *,
    db_path=DB_NAME,
    key_path=None,
    key_provider=None,
    config_path=None,
):
    """Create a self-contained backup and verify it before publication."""
    db_path = Path(db_path)
    destination = Path(destination)
    if not db_path.is_file():
        raise FileNotFoundError("Yedeklenecek veritabanı bulunamadı.")
    provider = _key_provider(key_path, key_provider)
    key = provider.load_key()
    if key is None:
        raise KeyUnavailableError("Yedeklenecek şifreleme anahtarı bulunamadı.")
    recovery = encrypt_recovery_material(key, passphrase)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="archlence-backup-", dir=str(destination.parent)
    ) as temp_dir:
        temp = Path(temp_dir)
        db_copy = temp / "finance.db"
        _sqlite_backup(db_path, db_copy)
        _integrity_check(db_copy)
        aead_checked = verify_database_key(db_copy, key)
        metadata = {
            "format_version": BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": hashlib.sha256(db_copy.read_bytes()).hexdigest(),
            "key_fingerprint": hashlib.sha256(key).hexdigest(),
            "aead_records_verified": aead_checked,
        }
        (temp / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        (temp / "key.recovery.json").write_text(
            json.dumps(recovery, indent=2), encoding="utf-8"
        )
        members = ["finance.db", "metadata.json", "key.recovery.json"]
        if config_path and Path(config_path).is_file():
            shutil.copy2(config_path, temp / "config.json")
            members.append("config.json")

        staged = temp / "backup.zip"
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                archive.write(temp / member, member)
        os.replace(staged, destination)

    verify_backup(destination, passphrase)
    return {
        "path": str(destination),
        "aead_records_verified": aead_checked,
        "database_sha256": metadata["database_sha256"],
    }


def verify_backup(package_path, passphrase):
    """Extract into a temporary directory and prove DB/key compatibility."""
    package_path = Path(package_path)
    with tempfile.TemporaryDirectory(prefix="archlence-verify-") as temp_dir:
        temp = Path(temp_dir)
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                names = set(archive.namelist())
                required = {
                    "finance.db", "metadata.json", "key.recovery.json",
                }
                if not required <= names:
                    raise IntegrityVerificationError(
                        "Backup paketi gerekli dosyaları içermiyor."
                    )
                if any(
                    Path(name).is_absolute() or ".." in Path(name).parts
                    for name in names
                ):
                    raise IntegrityVerificationError(
                        "Backup paketi güvenli olmayan dosya yolu içeriyor."
                    )
                for name in required | ({"config.json"} & names):
                    archive.extract(name, temp)
        except (zipfile.BadZipFile, OSError) as exc:
            raise IntegrityVerificationError(
                "Backup paketi açılamadı."
            ) from exc

        try:
            metadata = json.loads(
                (temp / "metadata.json").read_text(encoding="utf-8")
            )
            recovery = json.loads(
                (temp / "key.recovery.json").read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IntegrityVerificationError(
                "Backup metadata veya kurtarma materyali bozuk."
            ) from exc
        if metadata.get("format_version") != BACKUP_FORMAT_VERSION:
            raise IntegrityVerificationError("Backup format sürümü desteklenmiyor.")
        db_copy = temp / "finance.db"
        digest = hashlib.sha256(db_copy.read_bytes()).hexdigest()
        if digest != metadata.get("database_sha256"):
            raise IntegrityVerificationError("Backup veritabanı hash'i eşleşmiyor.")
        key = decrypt_recovery_material(recovery, passphrase)
        if hashlib.sha256(key).hexdigest() != metadata.get("key_fingerprint"):
            raise IntegrityVerificationError("Backup anahtar parmak izi eşleşmiyor.")
        _integrity_check(db_copy)
        checked = verify_database_key(db_copy, key)
        if checked != int(metadata.get("aead_records_verified", -1)):
            raise IntegrityVerificationError(
                "Backup AEAD doğrulama sayısı eşleşmiyor."
            )
        return {
            "key": key,
            "metadata": metadata,
            "config": (
                (temp / "config.json").read_bytes()
                if (temp / "config.json").exists()
                else None
            ),
        }


def restore_backup(
    package_path,
    passphrase,
    *,
    db_path=DB_NAME,
    key_path=None,
    key_provider=None,
    config_path=None,
    safety_backup_path=None,
    _failure_hook=None,
):
    """Verify, safety-backup, then replace DB/key with rollback on failure."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    provider = _key_provider(key_path, key_provider)
    config = Path(config_path) if config_path else None
    safety_backup_path = Path(
        safety_backup_path
        or db_path.with_name(
            f"pre-restore-{datetime.now():%Y%m%d-%H%M%S}.archlence-backup"
        )
    )
    current_key = provider.load_key()
    if db_path.exists() and current_key is not None:
        create_backup(
            safety_backup_path,
            passphrase,
            db_path=db_path,
            key_provider=provider,
            config_path=str(config) if config else None,
        )

    with tempfile.TemporaryDirectory(
        prefix="archlence-restore-", dir=str(db_path.parent)
    ) as temp_dir:
        temp = Path(temp_dir)
        with zipfile.ZipFile(package_path, "r") as archive:
            archive.extract("finance.db", temp)
            archive.extract("metadata.json", temp)
            archive.extract("key.recovery.json", temp)
            if "config.json" in archive.namelist():
                archive.extract("config.json", temp)
        verification = verify_backup(package_path, passphrase)
        staged_db = temp / "finance.db"
        staged_key = temp / "encryption.key"
        staged_key.write_bytes(verification["key"])
        os.chmod(staged_key, 0o600)

        old_db = temp / "old-finance.db"
        try:
            if db_path.exists():
                os.replace(db_path, old_db)
            if _failure_hook:
                _failure_hook("after_old_files_staged")
            os.replace(staged_db, db_path)
            if _failure_hook:
                _failure_hook("after_database_replaced")
            incoming_key = staged_key.read_bytes()
            if current_key is None:
                provider.store_key(incoming_key)
            else:
                provider.replace_key(
                    incoming_key, expected_current=current_key
                )
            if config and verification["config"] is not None:
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_bytes(verification["config"])
            _integrity_check(db_path)
            verify_database_key(db_path, provider.load_key())
        except Exception as exc:
            if db_path.exists():
                db_path.unlink()
            if old_db.exists():
                os.replace(old_db, db_path)
            restored_key = provider.load_key()
            if (
                current_key is not None
                and restored_key is not None
                and restored_key != current_key
            ):
                provider.replace_key(
                    current_key, expected_current=restored_key
                )
            elif current_key is None and restored_key is not None:
                provider.delete_key(expected_current=restored_key)
            raise DataMigrationError(
                "Restore başarısız oldu; önceki veriler geri yüklendi."
            ) from exc

    from utils.crypto import _get_aead_key
    _get_aead_key.cache_clear()
    return {
        "restored": True,
        "safety_backup_path": str(safety_backup_path),
    }
