# Backup and recovery

An Archlence backup contains the database, format metadata, and
password-protected recovery material. The raw `encryption.key` file is never
placed in the package.

## Security contract

- The recovery password must contain at least 12 characters and is not stored
  by the application.
- The key is protected with AES-256-GCM using a key derived by
  PBKDF2-HMAC-SHA256 with 600,000 iterations.
- Backup completes only after SQLite `integrity_check`, file-hash validation,
  and validation of every AEAD field with the selected key succeed.
- Restore creates an additional verified safety backup of the current data
  before changing it.
- If restore fails, the previous database and key are restored.

## What the user must retain

Store the backup package and its recovery password separately in secure
locations. If the password is lost, neither Archlence nor its developers can
decrypt the key stored in the package. Copying only `finance.db` is not enough;
the matching encryption key is also required.

## Restore process

Restore begins only after validation succeeds. If the destination already has
data, Archlence creates a safety backup named
`pre-restore-YYYYMMDD-HHMMSS.archlence-backup`. A wrong password, a corrupt
database hash, or a key that does not match the encrypted records leaves the
destination files unchanged.

A second Archlence process cannot use the same profile during backup or
restore. The single-instance guard blocks it before either operation starts.

## Savings goals: scope and retired files

Savings goals live in `finance.db` only. They are therefore inside every
backup package automatically — with every field, including the permanent
`goal_uid`, the target and saved amounts, the target date, status,
`created_at`, `color`, `auto_deposit`, and the quarantine table. The package
carries no separate JSON member for them, and it never did; this is not a gap.

Older packages (`format_version` 2) restore unchanged. Nothing new is
required inside the archive.

### Files kept outside the package

Migrating the pre-SQLite `savings_goals.json` produces artifacts that are
**deliberately excluded** from backups, because their contents are already in
the database or in the quarantine table:

| File | Written when | Read again? |
|---|---|---|
| `savings_goals.json.migrated-<time>` | migration completed and verified | never |
| `savings_goals.json.stale-<time>` | a restore replaced the database while a legacy file was still present | never |
| `savings_goals.json.unreadable-<time>` | the legacy file could not be parsed; no record was migrated | never |
| `finance.db.pre-savings-migration-<time>` | before the migration writes any row | only if you restore it by hand |

These are **sensitive**: goal names and amounts are personal financial data.
They stay in the user data directory (`data_dir()`), are never copied to a new
location, and are never deleted automatically — silently destroying user data
would contradict the migration's own contract. Delete them yourself once you
are satisfied the migration went well.

`finance.db.pre-savings-migration-<time>` is a plain SQLite copy of the
database as it was before the migration. It contains the same encrypted
records as the live database and no key material; the encryption key stays in
the platform key store either way. It is the supported way back to a build
older than schema generation 2, since such a build refuses to open a
generation-2 profile.
