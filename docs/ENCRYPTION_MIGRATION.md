# Legacy encryption migration

Archlence writes new records in the `AEADv1` (AES-256-GCM) format. AES-CBC
records from older installations remain readable, but they have no integrity
authentication and must be migrated through the controlled process.

Migration never starts automatically or without notice. A read-only inventory
first shows the fields and record counts that will be affected. The user is
also shown the backup destination and warned that losing the key makes the
data unreadable.

The security sequence is:

1. Create a password-protected, verified backup after confirming that the
   current database and key match.
2. Lock the database with a `BEGIN IMMEDIATE` transaction.
3. Decrypt each legacy field, encrypt it with AEAD, then decrypt it again to
   verify the result.
4. Commit the migrated data and migration record together only after every
   field succeeds.
5. Roll back the complete transaction on any error while retaining the
   verified backup.

The migration is repeatable. Fields prefixed with `AEADv1:` are skipped; when
no legacy fields remain, neither the database nor backup files are modified.

A second Archlence instance cannot use the same profile during migration. The
single-instance lock is acquired before migration begins.

## Conditions for removing the legacy reader

CBC support is deprecated, isolated to migration/restore compatibility, and
cannot write new data. It will not be removed until all of these are true:

1. Inventory reports zero legacy fields in every supported profile.
2. Old backups can be restored by the current release and passed through the
   controlled migration.
3. Local inventory remains at zero throughout at least one complete stable
   release line.
4. The backup-retention policy and the final legacy-capable release are clearly
   documented.

Until then, `_decrypt_legacy_cbc` remains protected by backward-read tests;
new writes produce only `AEADv1`.
