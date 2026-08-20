# Security & Release Readiness Roadmap

This roadmap covers the engineering items still open from the security and
release-readiness review the project was drafted around. It is not a history of
what was done and not the full limitation list: release-by-release detail
belongs in [CHANGELOG.md](../CHANGELOG.md), the current posture and every known
limitation belong in
[security and reliability status](SECURITY_RELIABILITY_STATUS.md), and the
broader near-term product priorities are summarised in the
[project README](../README.md).

Every item here was verified against the code on `main` before being listed.

## Open work

### 1. Split `main.py` and the `ArchlenceApp` mixin list

Screen behaviour should move into separate controller/view-model classes and
`ArchlenceApp` should be reduced to application lifecycle. A written plan
exists: [`MAIN_PY_SPLIT_PLAN.md`](MAIN_PY_SPLIT_PLAN.md). **No production code
has been changed yet.**

Measured on 2026-08-17: `main.py` is 2,280 lines across 17 mixins.

The real constraint is not file size. `.kv` binds to `app` as a single object —
33 method calls and 344 references, all resolved *at runtime*. A missing name
is not a build error, it is a control that silently does nothing, which is
exactly the defect found and fixed twice in 0.0.11 and 0.0.12. The plan
therefore keeps `.kv` untouched behind delegating methods rather than
repointing 344 call sites.

The plan's prerequisite is already done and was worth doing on its own:
`tests/test_kv_app_surface.py` asserts that every `app.<name>` used in `.kv`
actually exists on `ArchlenceApp`, which closes the silent-breakage risk
permanently.

### 2. Validate packaged key storage on real systems

`utils/key_provider.py` selects `DpapiKeyProvider` on Windows,
`KeyringKeyProvider` (Secret Service/KWallet) on Linux, and an owner-only file
elsewhere; `MigratingKeyProvider` moves an existing file-based key into the OS
key store on first use. The Linux Secret Service path was verified empirically
on a development machine — a fresh profile produced a working key with no
`encryption.key` file on disk.

Still needed: end-to-end confirmation of the Windows DPAPI path and of recovery
behaviour from a **packaged** build on real hardware, not a development
checkout.

## Where the rest of the status lives

- Release-by-release detail and current known limitations —
  [CHANGELOG.md](../CHANGELOG.md) and
  [security and reliability status](SECURITY_RELIABILITY_STATUS.md).
- Conditions that must all hold before the legacy CBC reader can be removed —
  [legacy encryption migration](ENCRYPTION_MIGRATION.md).
- Boundaries and contracts a change must preserve —
  [architecture](ARCHITECTURE.md).

## Closed items

Kept as a short ledger so closed work is not reopened by accident, and because
source comments across the tree still point at these items by their original
phase numbering. The reasoning behind each is in the changelog entry and the
pull request that landed it.

**Phase 0 — safety net**

- CI test suite as a required status check, with a correct exit code.
- The full pyflakes set (`flake8 --select=F`) is now a **blocking** CI gate;
  the 122-violation backlog it was waiting on was cleared in v0.0.9.

**Phase 1 — release blockers**

1. CVC and full PAN storage removed; only the derived `masked_number` and
   `network_logo` remain, backfilled for existing installs.
2. The `KIVY_WINDOW=mock` / `except BaseException` startup fallback removed.
   `main.py` falls back to stub UI classes only when `ARCHLENCE_HEADLESS` is
   explicitly set, and fails visibly otherwise.
3. The built Windows `.exe` is smoke-tested in CI, alongside installation,
   previous-release upgrade, profile persistence, and removal.
4. User data moved out of the install directory via `platformdirs`, including
   the config path, crash log, and brand-icon cache.
5. Encryption: AES-256-GCM with a versioned envelope, a random per-install key
   held in an OS key store, no fail-open on decrypt, and a backup-first
   transactional migration for existing databases. Real-system validation of
   the packaged Windows path is still open — see above.
6. PIN hashing moved to Argon2id with lazy upgrade on successful login, plus a
   persisted login throttle with doubling lockout.

**Phase 2 — hardening**

- Search implemented across account names, category names and transaction
  descriptions. Descriptions are matched over a bounded 500-row recent window
  chosen by measurement; the limit and its cost are stated in the UI and
  recorded in the changelog.
- The notification bell lists pending transactions and recurring payments due
  within seven days, on a background thread.
- Turkish case folding fixed in the budget, BIST and crypto pickers; all three
  now go through `services.search_service.matches`.
- Broad exception handling narrowed in `services/`, `database/`, `utils/` and
  the four user-facing boundaries the audit tool flagged. The remaining
  handlers are logged boundaries, reviewed-and-accepted, or re-raising; CI
  freezes a decreasing baseline. Treat this as closed unless the audit
  surfaces a new user-facing boundary.
- The stock price cache's fetch gate no longer blocks the first fetch for a
  never-cached symbol while the market is closed. Exchange/timezone tracking
  was checked and deliberately not built: there is no non-BIST stock entry path
  in the app today.
- `requirements.txt` split into pinned runtime and dev files, with
  `matplotlib`/`scipy` and their transitive dependencies proven unused and
  dropped.
