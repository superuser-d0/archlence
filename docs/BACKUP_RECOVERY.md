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
