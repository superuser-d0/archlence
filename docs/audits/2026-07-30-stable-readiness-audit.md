# Archlence stable-readiness audit — 2026-07-30

> **ARCHIVED BASELINE — CURRENT STATUS DEĞİLDİR**

Audited commit: `ecf582ae` (`main`)

This report records the live-code baseline before remediation. No finding below
is inherited from an earlier report without checking the current source.

## Release inventory

GitHub API was queried on 2026-07-30. All releases report
`immutable: false`, but the requested destructive history reset is **not
authorized by its own gate** because published assets have downloads.

| Release | Tag / target | Published | State | Asset | Size | Downloads |
|---|---|---|---|---|---:|---:|
| Archlence 1.0.1 | `v1.0.1` / `a05c6c3` | 2026-07-30 03:53Z | published, stable | `Archlence-1.0.1-x86_64.AppImage` | 104,262,136 | 0 |
| Archlence 1.0.1 | `v1.0.1` / `a05c6c3` | 2026-07-30 03:53Z | published, stable | `ArchlenceSetup-1.0.1.exe` | 54,855,512 | 0 |
| Archlence 1.0.0 | `v1.0.0` / `258ee53` | 2026-07-30 02:56Z | published, stable | `Archlence-1.0.0-x86_64.AppImage` | 104,258,040 | **1** |
| Archlence 1.0.0 | `v1.0.0` / `258ee53` | 2026-07-30 02:56Z | published, stable | `ArchlenceSetup-1.0.0.exe` | 54,850,264 | **1** |
| Archlence 0.9.0 | `v0.9.0` / `fc3d737` | 2026-07-30 02:35Z | published, pre-release | `Archlence-0.9.0-x86_64.AppImage` | 104,258,040 | **1** |
| Archlence 0.9.0 | `v0.9.0` / `fc3d737` | 2026-07-30 02:35Z | published, pre-release | `ArchlenceSetup-0.9.0.exe` | 54,850,692 | **1** |

Repository rules: `main` is protected, administrators are included, force
push/deletion are disabled, and `build-windows` plus `test` are required and
strict. No repository ruleset/tag-protection rule is configured. Release
objects are currently mutable.

## Current automated baseline

- `xvfb-run -a .venv/bin/python -m unittest discover -s tests`:
  **516 passed, 0 failed, 0 skipped**.
- `compileall` over project-owned Python: passed.
- `git diff --check`: passed.
- Pyflakes baseline: 11 findings — 6 `F401`, 4 duplicate-key `F601`, and
  1 `F824`; no `F821/F822/F823`.
- CI lint is informational (`continue-on-error: true`) and therefore is not a
  quality gate.

Passing tests do not imply stable readiness: current tests explicitly preserve
several unsafe fail-open contracts.

## Finding classification

| Area | Live classification | Evidence / impact |
|---|---|---|
| Encryption fail-open | **Still present — P0** | `utils/crypto.py::encrypt` returns plaintext after encryption failure. |
| Decryption fail-open | **Still present — P0** | Both AEAD and legacy failures return `"[Şifreli Veri]"`. |
| Corrupt amount coerced to zero | **Still present — P0** | `main.py` and `transaction_service.py` contain decrypt/float failure paths assigning `0.0`; budget/insights helpers also return zero. |
| AEAD primitive | **Completely resolved at primitive level** | AES-256-GCM envelope and tamper/wrong-key tests exist in `utils/aead_crypto.py`; unsafe compatibility wrapper prevents end-to-end fail-closed behavior. |
| Legacy crypto migration | **Still present — P0** | No inventory, backup, transactional re-encryption, verification, rollback, resume, or user-controlled migration flow exists. Current “migration” service is CSV import/export only. |
| Key provider atomic creation | **Completely resolved** | Same-filesystem temp file + `fsync` + atomic hard link prevents key-creation races. |
| OS key store | **Still present — P1** | Only raw `FileKeyProvider` exists. No DPAPI/Secret Service provider, visibility of fallback, recovery export/import, or rotation. |
| Backup/restore | **Still present — P0** | No application backup/restore implementation or integration tests; README only says to keep database backups. A database copy alone is unusable without its AEAD key. |
| Financial data-quality propagation | **Still present — P0** | Services return floats/lists without complete/partial/invalid metadata; unreadable values can become zero or be omitted while UI presents a definitive total. |
| Decimal financial arithmetic | **Partially resolved / different problem** | Input validation is strong, but persistent/domain arithmetic is predominantly `float`; no documented rounding boundary or gradual Decimal model. |
| Monolithic app architecture | **Partially resolved** | Domain services exist and many are headless-testable, but `main.py` is 2,266 lines and mixins total thousands more; calculations, cache, threads, dialogs, and widgets remain coupled. |
| Broad/silent exception handling | **Still present — P1** | Many `except Exception`, `pass`, `print`, empty-list and zero fallbacks remain across `main.py`, mixins, and services. No rotating/redacting structured logger/error IDs. |
| Single-instance protection | **Still present — P1** | No process lock/mutex/socket. Atomic key creation prevents one race but two instances can still migrate/process recurring payments/use the same DB. |
| SQLite concurrency | **Partially resolved** | Connections generally use timeout and are closed more carefully, but no process-level exclusion; migration and recurring execution are not protected from a second process. |
| Background result ordering | **Partially resolved** | Chart/cache request-generation guards exist in selected paths; there is no common task manager/cancellation contract and broad callback exceptions remain. |
| Large-data performance | **Still present — P2** | Search micro-performance tests exist; no repeatable 1k/5k/10k/50k financial-data benchmark or UI-thread blocking measurement. |
| Search-bar render artifacts | **Unverified live / likely still present — P1 UI** | Home header uses a stock `MDTextField(mode="round")`; no regression test, focus/cursor policy, DPI/resize verification, or packaged screenshot evidence exists. Root cause requires live canvas inspection before editing. |
| Real UI tests | **Partially resolved** | Several Xvfb/Kivy behavior tests exist; no stable screenshot artifact detector for the search field and no complete DPI/fullscreen matrix. |
| Critical lint | **Partially resolved** | Undefined-name classes are currently zero, but duplicate dictionary keys and other F findings remain; CI does not block them. |
| Version source of truth | **Still present — P1 release** | `1.0.1` is duplicated in README, Inno Setup and workflow defaults. No application-level version source or tag/version consistency gate. |
| Package confidentiality scan | **Partially resolved** | PyInstaller datas are narrow and prior builds pass smoke tests, but release jobs do not scan archives for DB/key/log/token/test artifacts and do not publish checksums/SBOM. |
| Documentation truthfulness | **Still present — P0/P1** | README describes AEAD but does not disclose fail-open behavior, raw key-file dependency, absence of restore, or key-loss consequences; roadmap correctly admits several gaps while releases are labelled stable. |

## Three highest security risks

1. Encryption failure can persist sensitive plaintext.
2. Decryption/integrity failures can be converted to placeholders/zero and
   continue through financial logic.
3. The database and raw key file have no verified joint backup/recovery
   lifecycle; key loss makes AEAD records unrecoverable.

## Three highest data-loss/integrity risks

1. No transactional, backed-up legacy-to-AEAD migration exists.
2. No tested restore workflow verifies database integrity and key matching
   before replacing current data.
3. Multiple application processes can operate on the same profile, including
   due/recurring processing and future migrations.

## Three most expensive architectural areas

1. `ArchlenceApp` and its mixins combine lifecycle, UI, data loading, errors,
   threading, caching, and calculations.
2. Decryption is performed ad hoc in dozens of callers with incompatible
   fallback behavior instead of through typed repository/domain boundaries.
3. Background work has per-feature generation/cancellation conventions rather
   than one lifecycle-aware task manager.

## Most important test gaps

- End-to-end failure injection proving plaintext can never reach SQLite.
- Corrupt/wrong-key record propagation to an explicit invalid dashboard state.
- Backed-up, transactional, idempotent legacy migration with rollback tests.
- Complete backup/restore/key-match tests.
- Single-instance/stale-lock tests.
- Repeatable 10,000+ transaction benchmarks and UI-thread measurements.
- Search-bar canvas/cursor visual regression across theme, resize, and DPI.
- Clean installed Windows flow and clean Linux AppImage recovery/key-store
  behavior; current CI only proves package launch/build.

## Recommended implementation order

1. Introduce typed crypto/integrity exceptions and make encryption fail closed.
2. Add a data-quality result contract; stop zero/empty fallbacks in critical
   totals and surface an invalid-state message.
3. Build and test verified backup/restore before any re-encryption.
4. Add user-controlled legacy inventory/migration with backup, transaction,
   verify, rollback and idempotence.
5. Add platform key providers, explicit fallback state, recovery material and
   rotation migration.
6. Add single-instance protection before enabling migration.
7. Extract financial summary/error/task services incrementally.
8. Add large-data benchmark and complete search-bar root-cause/UI verification.
9. Make critical lint/version/package scans blocking and reconcile docs.

## User-data impact

Fail-closed reads will deliberately stop definitive totals when any contributing
record cannot be authenticated. This is a visible behavior change but prevents
false financial information. Existing legacy CBC records must remain readable
until the user explicitly runs a backed-up migration. No bulk rewrite should
occur during startup. Backup/restore and key-provider changes must preserve the
current raw key as recovery material until a new package has been verified and
the user explicitly confirms completion.

## Stable-release decision

**BLOCKED.** The current source does not meet the supplied stable gate, and the
requested release-history reset is independently blocked because four existing
assets have non-zero download counts. No release or tag may be deleted/reused
under the user's stated rules.
