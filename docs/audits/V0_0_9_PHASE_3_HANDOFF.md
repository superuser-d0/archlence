# Phase 3 Handoff

Only confirmed or strong-evidence items from Phase 1/2 are included. Source
evidence and exact commands are in the Phase 1/2 audit matrices.

## P0 Release Blockers

### P0-1 — Backup authenticity absent

* Root cause: `services/backup_service.py:verify_backup` trusts a mutable
  SHA-256 in `metadata.json`; it has no signature/MAC bound to DB + metadata.
* Required fix: versioned authenticated backup manifest, verify before any
  restore; specify compatibility/migration for existing backups.
* Failing test: `BackupAuthenticityReproduction`.
* Verification: DB + metadata coordinated mutation must be rejected.

### P0-2/P0-3 — Recurring charge/refund lacks idempotency

* Root cause: `database.db.process_due_recurring_payment` and
  `services.recurring_service.refund_current_period_charge` have no durable
  unique period/reversal key or atomic state transition.
* Required fix: DB-enforced idempotency key/unique constraint and one
  transaction that writes financial effect and period/refund marker.
* Failing tests: sequential and `test_phase2_concurrency` two-worker cases.
* Dependency: transaction-boundary refactor first; migration must safely add
  keys/indexes and deduplicate/flag legacy conflicts.

### P0-4/P0-5 — Asset sale and debt payment partial commits

* Root cause: UI/mixin paths commit balance/entity/ledger in separate service
  calls/connections (`mixins/asset_mixin.py`, `mixins/recurring_mixin.py`).
* Required fix: single database transaction/cursor across ledger, balance,
  transaction and entity state; UI/caches only after commit.
* Fault tests: asset removal failure and ledger insertion failure must leave
  every before-state unchanged.

### P0-6 — Non-finite money is accepted

* Root cause: float inputs reach SQLite arithmetic without universal Decimal
  finite validation. Transaction, account, savings and recurring paths accept
  infinity; asset purchase rejects it.
* Required fix: one finite monetary parser at every service/API/import
  boundary; reject NaN/±Inf/string variants before write.
* Failing tests: additional reproduction and nonfinite matrix; assert no
  transaction/event/entity/cache state changes.

### P0-7 — Credit-card limit TOCTOU

* Root cause: limit check and transaction write are separate connections/
  transaction scopes in account and transaction services.
* Required fix: conditional/locked limit update and transaction insert in one
  DB transaction, with controlled conflict.
* Failing test: two 60-unit charges against 100 limit produce debt 120.

## P1 Release Blockers

### P1-1 Restore generation atomicity

* Root cause: `restore_backup` rolls DB/key back but writes config in place
  and does not restore prior config when a later verification fails.
* Required fix: stage complete profile, atomic replacement/rollback of DB,key,
  config, durable marker/recovery, and fault matrix.

### P1-2 Migration crash recovery

* Root cause: migration guards only on column existence; a committed ALTER
  prevents an interrupted data backfill from retrying.
* Required fix: transactional/idempotent migration journal/version and
  data-completeness guard, tested against populated old profiles.

### Phase 1 A-1/A-2 Exception gate integrity

* Required fix: AST-based broad-handler enumeration that recognizes tuple,
  attribute and alias forms; baseline exact set must reject both slack and
  stale entries. Add mutation tests.

### P1-CSV Plaintext export permissions

* Root cause: direct `open(path, 'w')` uses user umask; under 022 final CSV
  is 0644 and no atomic staging/symlink policy exists.
* Required fix: explicit private permissions, atomic safe destination policy,
  overwrite/symlink behavior and UI plaintext warning; Windows ACL manual test.

## P2 Follow-ups

* P2-6 backup unexpected-member allow-list; POSIX traversal is blocked but
  unexpected member is accepted and Windows drive syntax was not validated.
* P2-7 delayed SQLite connection cleanup: FD 4→71 during 100 operations,
  returns 4 later/after GC. Convert remaining raw `get_connection()` callers
  to explicit close/managed connection and add resource regression test.
* P2 NaN is rejected only by SQLite, not the service domain.
* P2 version gate misses workflow fallback, extra README stale value, release
  asset rename and tag mismatch; upgrade smoke is fixed to v0.0.1.
* P2 packaging supply-chain reproducibility: unpinned GitHub Actions and
  AppImage `continuous` downloader without checksum.
* P2 FK enforcement, `user_version`, observability/UI real-device coverage.

## Dependency Order

1. Finite money parser and database transaction-boundary primitives.
2. Recurring/card idempotency and asset/debt atomicity migrations/tests.
3. Backup authenticated format, then atomic restore.
4. Migration crash recovery.
5. Exception/version/release gates and CSV/archive hardening.
6. Move audit tests to CI, package validation, RC/soak.

## Required Tests to Move Into Normal Suite

All fixed P0/P1 reproductions, real installment property/mutations, populated
migration matrix, non-finite service matrix, concurrent recurring/refund/card
tests, restore fault matrix, backup tamper/archive tests, CSV mode/atomicity.

## Manual Windows Checklist

Real DPAPI, installer clean install/upgrade/uninstall while running, Unicode
and long paths, non-admin user-data retention, locked DB/antivirus behavior,
stale lock, crash log, DPI 125/150/200%, keyboard focus and App exit.

## Release GO Conditions

Every P0/P1 above is fixed and mutation/fault verified; normal suite and
expanded CI are green; v0.0.1–v0.0.8 migration matrix green; clean Linux
package smoke green; Windows evidence or explicit accepted risk; three-day RC
with no P0/P1, duplicate transaction, invariant violation, DB lock or recovery failure.
