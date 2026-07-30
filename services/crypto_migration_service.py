"""User-controlled, backup-first migration from legacy CBC to AEAD."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from database.db import DB_NAME, SECRET_KEY
from services.backup_service import ENCRYPTED_FIELDS, _key_provider, create_backup
from utils import aead_crypto
from utils.crypto import decrypt
from utils.errors import DataMigrationError, DecryptionError

_AEAD_PREFIX = "AEADv1:"
MIGRATION_ID = "legacy-cbc-to-aead-v1"


@dataclass(frozen=True)
class CryptoMigrationPlan:
    legacy_fields: int
    affected_records: int
    backup_path: str
    migration_id: str = MIGRATION_ID


def _candidate_fields(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    for table, configured_fields in ENCRYPTED_FIELDS.items():
        if table not in tables:
            continue
        columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table})")
        }
        fields = [field for field in configured_fields if field in columns]
        if fields and "id" in columns:
            yield table, fields


def inspect_legacy_encryption(*, db_path=DB_NAME, backup_path=""):
    """Return a read-only inventory; it never mutates or creates a backup."""
    legacy_fields = 0
    record_keys = set()
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for table, fields in _candidate_fields(conn):
            selected = ", ".join(["id", *fields])
            for row in conn.execute(f"SELECT {selected} FROM {table}"):
                for field in fields:
                    value = row[field]
                    if value is None or str(value).strip() == "":
                        continue
                    if not str(value).startswith(_AEAD_PREFIX):
                        legacy_fields += 1
                        record_keys.add((table, row["id"]))
    return CryptoMigrationPlan(
        legacy_fields=legacy_fields,
        affected_records=len(record_keys),
        backup_path=str(backup_path),
    )


def migrate_legacy_encryption(
    passphrase,
    backup_path,
    *,
    db_path=DB_NAME,
    key_path=None,
    key_provider=None,
    _failure_hook=None,
):
    """Backup, migrate atomically, verify, and remain safe to run repeatedly."""
    db_path = Path(db_path)
    backup_path = Path(backup_path)
    plan = inspect_legacy_encryption(
        db_path=db_path, backup_path=backup_path
    )
    if plan.legacy_fields == 0:
        return {
            "migrated_fields": 0,
            "affected_records": 0,
            "backup_path": None,
            "already_current": True,
        }

    create_backup(
        backup_path,
        passphrase,
        db_path=db_path,
        key_path=key_path,
        key_provider=key_provider,
    )
    provider = _key_provider(key_path, key_provider)
    key = provider.load_key()
    if key is None:
        raise DataMigrationError("Migration anahtarı bulunamadı.")
    migrated = 0
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL,"
                "details TEXT NOT NULL)"
            )
            for table, fields in _candidate_fields(conn):
                selected = ", ".join(["id", *fields])
                rows = conn.execute(f"SELECT {selected} FROM {table}").fetchall()
                for row in rows:
                    for field in fields:
                        value = row[field]
                        if value is None or str(value).strip() == "":
                            continue
                        text = str(value)
                        if text.startswith(_AEAD_PREFIX):
                            continue
                        plaintext = decrypt(text, SECRET_KEY)
                        replacement = (
                            _AEAD_PREFIX + aead_crypto.encrypt(plaintext, key)
                        )
                        if (
                            aead_crypto.decrypt(
                                replacement[len(_AEAD_PREFIX):], key
                            )
                            != plaintext
                        ):
                            raise DataMigrationError(
                                "Yeni şifreli kayıt doğrulanamadı."
                            )
                        conn.execute(
                            f"UPDATE {table} SET {field} = ? WHERE id = ?",
                            (replacement, row["id"]),
                        )
                        migrated += 1
                        if _failure_hook:
                            _failure_hook(migrated)
            remaining = 0
            for table, fields in _candidate_fields(conn):
                clauses = " OR ".join(
                    f"({field} IS NOT NULL AND trim({field}) != '' "
                    f"AND {field} NOT LIKE '{_AEAD_PREFIX}%')"
                    for field in fields
                )
                remaining += conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {clauses}"
                ).fetchone()[0]
            if remaining:
                raise DataMigrationError(
                    f"{remaining} legacy kayıt taşınmadan kaldı."
                )
            conn.execute(
                "INSERT OR REPLACE INTO schema_migrations "
                "(migration_id, applied_at, details) VALUES (?, ?, ?)",
                (
                    MIGRATION_ID,
                    datetime.now(timezone.utc).isoformat(),
                    f"migrated_fields={migrated}",
                ),
            )
            conn.commit()
    except (sqlite3.Error, OSError, DecryptionError, ValueError) as exc:
        raise DataMigrationError(
            "Legacy şifreleme migration'ı geri alındı; backup korunuyor."
        ) from exc
    return {
        "migrated_fields": migrated,
        "affected_records": plan.affected_records,
        "backup_path": str(backup_path),
        "already_current": False,
    }
