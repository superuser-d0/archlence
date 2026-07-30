"""Password-protected key recovery and rollback-safe key rotation."""

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from services.backup_service import (
    ENCRYPTED_FIELDS,
    create_backup,
    decrypt_recovery_material,
    encrypt_recovery_material,
    verify_database_key,
)
from services.crypto_migration_service import inspect_legacy_encryption
from utils import aead_crypto
from utils.errors import DataMigrationError, IntegrityVerificationError

_PREFIX = "AEADv1:"


def export_recovery_package(destination, passphrase, provider):
    key = provider.load_key()
    if key is None:
        raise IntegrityVerificationError("Dışa aktarılacak anahtar bulunamadı.")
    payload = {
        "format": "archlence-key-recovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "key_fingerprint": hashlib.sha256(key).hexdigest(),
        "recovery": encrypt_recovery_material(key, passphrase),
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_suffix(destination.suffix + ".tmp")
    staged.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(staged, destination)
    return str(destination)


def read_recovery_package(package, passphrase):
    try:
        payload = json.loads(Path(package).read_text(encoding="utf-8"))
        if payload.get("format") != "archlence-key-recovery-v1":
            raise IntegrityVerificationError(
                "Kurtarma paketi formatı desteklenmiyor."
            )
        key = decrypt_recovery_material(payload["recovery"], passphrase)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError) as exc:
        raise IntegrityVerificationError("Kurtarma paketi bozuk.") from exc
    if hashlib.sha256(key).hexdigest() != payload.get("key_fingerprint"):
        raise IntegrityVerificationError(
            "Kurtarma paketi parmak izi doğrulanamadı."
        )
    return key


def import_recovery_package(package, passphrase, provider, db_path):
    incoming = read_recovery_package(package, passphrase)
    verify_database_key(db_path, incoming)
    current = provider.load_key()
    if current is None:
        provider.store_key(incoming)
    elif current != incoming:
        provider.replace_key(incoming, expected_current=current)
    return {"imported": True, "fingerprint": hashlib.sha256(incoming).hexdigest()}


def rotate_encryption_key(
    *,
    db_path,
    provider,
    backup_path,
    backup_passphrase,
    rotation_id,
    expected_fingerprint,
    _failure_hook=None,
):
    """Re-encrypt a staged DB, then swap DB/key with compensating rollback."""
    current = provider.load_key()
    if current is None:
        raise DataMigrationError("Döndürülecek anahtar bulunamadı.")
    fingerprint = hashlib.sha256(current).hexdigest()
    if fingerprint != expected_fingerprint:
        raise DataMigrationError(
            "Anahtar beklenen sürümde değil; yinelenen rotasyon engellendi."
        )
    if inspect_legacy_encryption(db_path=db_path).legacy_fields:
        raise DataMigrationError(
            "Anahtar rotasyonundan önce legacy migration tamamlanmalıdır."
        )
    create_backup(
        backup_path,
        backup_passphrase,
        db_path=db_path,
        key_provider=provider,
    )
    new_key = os.urandom(32)
    db_path = Path(db_path)
    with tempfile.TemporaryDirectory(
        prefix="archlence-rotate-", dir=str(db_path.parent)
    ) as temp_dir:
        temp = Path(temp_dir)
        staged_db = temp / "finance.db"
        old_db = temp / "old-finance.db"
        with closing(sqlite3.connect(db_path)) as source:
            with closing(sqlite3.connect(staged_db)) as destination:
                source.backup(destination)
        with closing(sqlite3.connect(staged_db)) as conn:
            conn.row_factory = sqlite3.Row
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            conn.execute(
                "CREATE TABLE IF NOT EXISTS key_rotations ("
                "rotation_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL,"
                "old_fingerprint TEXT NOT NULL, new_fingerprint TEXT NOT NULL)"
            )
            if conn.execute(
                "SELECT 1 FROM key_rotations WHERE rotation_id = ?",
                (rotation_id,),
            ).fetchone():
                raise DataMigrationError("Bu rotasyon daha önce uygulandı.")
            count = 0
            for table, fields in ENCRYPTED_FIELDS.items():
                if table not in tables:
                    continue
                columns = {
                    row[1] for row in conn.execute(
                        f"PRAGMA table_info({table})"
                    )
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
                        if not text.startswith(_PREFIX):
                            raise DataMigrationError(
                                "Rotasyon sırasında legacy alan bulundu."
                            )
                        plaintext = aead_crypto.decrypt(
                            text[len(_PREFIX):], current
                        )
                        replacement = _PREFIX + aead_crypto.encrypt(
                            plaintext, new_key
                        )
                        conn.execute(
                            f"UPDATE {table} SET {field}=? WHERE id=?",
                            (replacement, row["id"]),
                        )
                        count += 1
                        if _failure_hook:
                            _failure_hook("reencrypt", count)
            new_fingerprint = hashlib.sha256(new_key).hexdigest()
            conn.execute(
                "INSERT INTO key_rotations VALUES (?, ?, ?, ?)",
                (
                    rotation_id,
                    datetime.now(timezone.utc).isoformat(),
                    fingerprint,
                    new_fingerprint,
                ),
            )
            conn.commit()
        verify_database_key(staged_db, new_key)
        provider.replace_key(new_key, expected_current=current)
        try:
            if _failure_hook:
                _failure_hook("after_key_replace", count)
            os.replace(db_path, old_db)
            os.replace(staged_db, db_path)
            verify_database_key(db_path, new_key)
        except (OSError, sqlite3.Error, IntegrityVerificationError) as exc:
            if old_db.exists():
                if db_path.exists():
                    db_path.unlink()
                os.replace(old_db, db_path)
            provider.replace_key(current, expected_current=new_key)
            raise DataMigrationError(
                "Anahtar rotasyonu geri alındı."
            ) from exc
    return {
        "rotated_fields": count,
        "old_fingerprint": fingerprint,
        "new_fingerprint": new_fingerprint,
        "backup_path": str(backup_path),
    }
