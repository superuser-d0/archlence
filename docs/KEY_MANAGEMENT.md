# Key management

Archlence uses a random 256-bit AES key for each installation.

## Platform protection

- **Windows:** the key is stored in the user-data directory as a DPAPI-protected
  blob bound to the current Windows user.
- **Linux:** the Python `keyring` interface uses Secret Service or KWallet when
  a suitable backend is available.
- If no OS key store is available, Archlence uses a local file restricted to
  mode `0600`. This fallback is not silent: Settings displays the active method
  and a warning.

When an old `encryption.key` file is found, the key is written to the OS store,
read back, and verified before the old file is removed. This avoids leaving a
second raw-key copy on disk after migration.

## Recovery package

The raw key is never exported. A recovery package protects it with AES-256-GCM
using a key derived from a password of at least 12 characters through
PBKDF2-HMAC-SHA256. Store the package and password separately. A lost password
cannot be recovered.

During import, the recovered key is first checked against every AEAD field in
the database. A mismatched key never replaces the active key.

## Key rotation

Rotation first creates a verified backup. A temporary database copy is
decrypted with the old key, encrypted with the new key, and validated. The new
key and staged database are activated together. If file replacement fails, the
old database and key are restored.

A rotation request carries the current key fingerprint and a unique rotation
identifier. Stale or accidentally repeated requests are rejected. Any legacy
CBC fields must be migrated before rotation.

An attacker who fully controls the signed-in OS account and the running
Archlence process can access data despite the OS key store. This model reduces
the risk of copying a key from disk or accessing it from another OS account; it
does not solve compromise of the operating-system account itself.
