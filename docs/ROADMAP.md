# Security & Release Readiness Roadmap

Archlence's ledger logic (atomic balance updates, `balance_events` audit
trail, pending-transaction settlement) is on solid ground. Its security
posture is not yet ready to carry the sensitive data it stores. This
document tracks closing that gap before the app can be called
production-ready.

Every item below was verified against the code on `main` before being
listed — not copied from a review without checking. Verification method is
noted per item so the next person doesn't have to re-derive it.

## Phase 0 — Safety net (do this first)

Everything in Phase 1 touches encryption, stored data, or the startup path.
Making those changes without a CI check that can actually fail is flying
blind.

- [x] **CI test job.** Done — [PR #8](https://github.com/superuser-d0/archlence/pull/8).
  `run_tests.py` didn't propagate a failing exit code —
  a broken build would report `0` regardless of test results, so it could
  never have failed a "required" CI check. Fixed in this same change
  (`sys.exit(0 if result.wasSuccessful() else 1)`), verified with both a
  passing and a deliberately failing run before trusting it. Added a fast
  Linux job (`ubuntu-latest`, `.github/workflows/tests.yml`) running
  `run_tests.py` on push/PR to `main`; promoted to a required status check
  (alongside `build-windows`, `enforce_admins: true`) after it proved
  stable through the PR that introduced it — which, on its own first CI
  run, caught a real pre-existing bug: `tests/test_savings_service.py` was
  silently depending on the real `finance.db` already having an account.
  Fixed in the same PR (see commit `37017f6`).
- [ ] **Lint, informational only (not blocking).** `flake8 --select=F`
  (pyflakes: unused imports, undefined names, redefinitions) currently
  reports 117 pre-existing violations; unrestricted flake8 reports 2067
  (almost all line-length). Gating on either right now would fail every
  future PR for reasons unrelated to the change being reviewed. Run it,
  report it, don't block on it — clean up the backlog separately, then
  promote to required.
  - One F-code finding is worth a dedicated look, not a mass cleanup:
    `mixins/subscription_mixin.py:187-188` — an exception variable that
    pyflakes reports as both unused (F841) and undefined (F821) in the
    same handler, which points at a real scoping bug in the except
    block, not just style noise.

## Phase 1 — Release blockers

Ordered by dependency, not just severity — items later in the list build on
guarantees established earlier.

1. ~~**Remove CVC and full PAN storage entirely.**~~ **Done** —
   [PR #9](https://github.com/superuser-d0/archlence/pull/9).
   `expiry_date`/`cvc_code` params removed everywhere (dialog, service,
   nothing ever read them back out anyway); `card_number_full` stays as a
   transient input to `create_account` — used once to derive `masked_number`
   + `network_logo`, never encrypted or written to disk. Migration
   backfills those two derived columns from any pre-existing encrypted
   `card_number_full` (decrypt once, derive, THEN null the sensitive
   columns — order verified against a hand-built pre-upgrade row before
   trusting it), so existing installs don't lose their last-4 display.
   Verified against real encrypted data, not just unit-test mocks, before
   writing the permanent tests.

2. ~~**Remove the `KIVY_WINDOW=mock` / `except BaseException` startup
   fallback.**~~ **Done** —
   [PR #16](https://github.com/superuser-d0/archlence/pull/16).
   The original description undersold the bug: `"mock"` has never been a
   real Kivy 2.3.1 window provider (only `egl_rpi`/`sdl2`/`x11` exist —
   verified by reading `kivy/core/__init__.py::core_select_lib` and
   `kivy/core/window/__init__.py::window_impl` directly, not assumed).
   Setting `KIVY_WINDOW=mock` restricts Kivy's own provider search to a
   name that matches nothing, so `core_select_lib` tries zero real
   providers and returns `None` — no exception, just a silent `Window =
   None`. Combined with the old `if not DISPLAY: KIVY_WINDOW=mock` guard
   (`DISPLAY` is X11/Linux-only and is never set on Windows, so this fired
   on *every* Windows install unconditionally) and the entry point's `if
   _KivyWindow is None: raise SystemExit(0)`, this meant the packaged
   Windows `.exe` (`console=False`) most likely exited with a **success**
   code without ever showing a window, on every install — a real,
   previously-unknown release blocker, confirmed empirically via
   subprocess tests that set the real env vars and inspect `crash.log`,
   not by inspection alone. Fix: the `DISPLAY`/`mock` logic is gone
   entirely — `KIVY_WINDOW` is never touched, so Kivy's real provider
   search runs. A new explicit `ARCHLENCE_HEADLESS` flag (opt-in, not
   inferred from `DISPLAY`) gates the stub-class fallback for
   test/CI/tooling use. The `except BaseException` blocks around the
   Kivy/KivyMD import are narrowed to `(ImportError, RuntimeError)` /
   `(ImportError, AttributeError)`, and both now `raise` instead of
   silently degrading unless `ARCHLENCE_HEADLESS=1` is explicitly set. See
   `tests/test_startup_import.py` for the three scenarios this locks in
   (real provider succeeds; genuinely broken provider fails loudly without
   the flag; degrades gracefully with it).

3. ~~**Smoke-test the built `.exe` in CI.**~~ **Done** — this entry was
   stale: three launch smoke tests already existed and go further than the
   text above described. `build-windows.yml` launches the raw
   `dist/Archlence/Archlence.exe`, and separately installs the Inno Setup
   package silently, launches the installed copy, then uninstalls and
   verifies removal. `build-linux.yml` runs the AppImage under `xvfb-run`
   and requires `timeout` to be the thing that kills it (exit 124), i.e.
   the process was still alive.
   - **Real gap found and closed while verifying this.** Only the raw-`.exe`
     step checked `crash.log`; the installer and AppImage steps checked
     *only* that the process stayed alive. An app that starts, catches an
     exception, logs it and keeps running with a broken screen therefore
     passed two of the three packaging paths. Both now compare `crash.log`
     the same way the raw-`.exe` step already did.
   - Measured, not assumed: `crash.log` is opened (empty) at `main.py`
     import time, so it *always exists* — checking for the file's presence
     would fail every run. The check is "non-empty"/"grew". Verified both
     directions on a real run: healthy launch leaves it at 0 bytes; an
     injected unhandled exception writes 91 bytes and is detected.
   - The Linux step was validated by extracting its body from the YAML and
     running it verbatim against a wrapper standing in for the AppImage:
     healthy run exits 0, and a process that stays alive but writes to
     `crash.log` now exits 1 — a case the previous version passed.
   - **Not verified here:** the Windows PowerShell changes. They mirror the
     already-proven raw-`.exe` step line for line, but no Windows runner was
     available in this environment; the first CI run on Windows is their
     real acceptance test.
   - Still open, deliberately: none of the three asserts that a window
     actually *appeared* (they infer it from "process alive + nothing
     logged"). On Windows `$proc.MainWindowHandle` would assert it directly;
     on Linux it needs `xdotool`/`x11-utils`, which the runner does not
     install today. Left alone rather than added blind — an unverifiable
     assertion that misfires would break every build for a non-issue.

4. ~~**Move user data out of the install directory, via `platformdirs`.**~~
   **Core done** — `database/db.py:6-7` derived `DB_NAME` from `BASE_DIR`
   (the app's own install location), same pattern for config JSON, the
   savings-goals store, crash logs, and the brand-icon cache across
   `main.py`/`services/brand_icon_service.py`/`services/migration_service.py`.
   On a packaged Windows install this directory is commonly read-only
   (`Program Files`), so the app likely couldn't persist any data at all
   post-install. `platformdirs` was already in `requirements.txt`, unused
   — now wired in via `utils/app_paths.py`, a thin resolver
   (`data_dir()`/`cache_dir()`/`log_dir()`) plus `migrate_legacy_path()`,
   a generic single-file "move if source exists and destination doesn't,
   never overwrite an existing destination" helper.
   - Correction to the original text: this did **not** end up depending on
     item (3) after all. The original reasoning ("confirm the exe actually
     runs before deciding where it's allowed to write") was the same
     over-cautious Windows-dependency pattern already corrected earlier in
     this roadmap for the Kivy fallback and PIN throttling items — the
     resolver and migration logic don't need a real Windows install to
     verify; only the final "does the installed .exe actually persist data
     where platformdirs says it will" acceptance check does, and that's a
     smaller, separate concern than gating all the development work on it.
   - `database/db.py::DB_NAME` now resolves via `data_dir()`; `get_connection()`
     creates the target directory on first real connection (`data_dir()`
     itself does zero I/O — resolving a path by importing this module,
     which every test file does, must never touch the real filesystem).
     `migrate_legacy_database_location()` is a separate, explicit function
     — called once from `main.py::build()` before `initialize_database()`,
     not triggered by import — moves an existing `BASE_DIR/finance.db`
     into the new location for upgrading installs.
   - `main.py`: crash log now opens under `log_dir()` instead of next to
     `main.py`. Config JSON and the savings-goals store resolve through
     new module-level helpers (`_resolve_config_path()`/
     `_resolve_savings_store_path()`, deliberately `self`-free so they're
     directly testable without a real window) that chain the *existing*
     legacy pre-rename migration (an even older app-name change already in
     the code) with the new `BASE_DIR` → `data_dir()` move.
   - `services/brand_icon_service.py::BRAND_ICON_CACHE_DIR` now under
     `cache_dir()` — no migration needed, it's a re-fetchable cache, not
     user data.
   - `services/migration_service.py::get_export_path()`'s Desktop-not-found
     fallback now targets `data_dir()` instead of `BASE_DIR`, same
     read-only-install-dir risk, same fix.
   - Verified: 14 new tests across `tests/test_app_paths.py` (pure
     resolver + migration mechanics, via monkeypatched `XDG_*` env vars —
     confirms the wrapper actually delegates to `platformdirs` and that
     `migrate_legacy_path` never overwrites a destination that already has
     current data) and `tests/test_app_paths_wiring.py` (the `main.py`
     helpers call the mechanics with the right source/destination pairs,
     including the pre-rename → archlence → `data_dir()` three-location
     chain). Confirmed import-time side-effect-free: running the full test
     suite creates no real `~/.local/share/Archlence` or
     `~/.local/cache/Archlence` directory on the dev machine (checked
     directly, not assumed) — `crash.log` is the one exception, and only
     because it already had that exact same eager-write-on-import behavior
     before this change, just pointed at the repo root instead of
     `~/.local/state/Archlence/log/`.
   - **Follow-up fix (found in a self-audit, not by CI)** —
     [PR #19](https://github.com/superuser-d0/archlence/pull/19). The first
     cut of this item had a bug that made it fail in exactly the situation
     it exists to fix. `migrate_legacy_path()` used `shutil.move`, which on
     the same filesystem degrades to `os.rename` and therefore needs write
     permission on the **source directory** — but the source here is the
     app's install directory, which on a packaged Windows install is
     commonly read-only. Reproduced empirically against a `chmod a-w`
     directory: `PermissionError`, and since all three migration calls are
     unguarded in `build()`, the app would have died before showing a
     window — the same silent-startup-failure class as item (2), for
     exactly the upgrading users this item was meant to help. Now copies
     and then deletes the source on a best-effort basis (an undeletable
     source leaves a harmless orphan that the `os.path.exists(new_path)`
     guard stops from ever being re-read). Separately,
     `_resolve_config_path()` was writing the pre-rename config into
     `_APP_DIR` as an intermediate step before migrating it out — also a
     write into the possibly-read-only install dir; both legacy names now
     migrate straight to the target. Locked in by three new tests that
     `chmod` the source directory read-only, which is what the original
     tests failed to do.
   - **Not done / explicitly deferred:** the real acceptance check — does
     a genuinely installed Windows `.exe` actually persist data under
     `%LOCALAPPDATA%\Archlence` and survive being read-only under
     `Program Files` — needs a real Windows install, not something this
     agent can verify. That's a small, focused check for whenever item (3)
     happens, not a blocker for the work above.

5. **Encryption: move to AEAD, generate a real key, use an OS keystore,
   version the ciphertext, migrate existing data.**
   `utils/crypto.py` has a hardcoded password and salt
   (`STATIC_SALT`, `DEFAULT_PASSWORD`) shared by every install, uses
   AES-256-**CBC** with no MAC (ciphertext can be tampered with
   undetected), and — worse — `decrypt()`'s except-all returns
   an “encrypted data” placeholder on any failure rather than raising. That string
   propagates into amount fields downstream and can collapse into `0.0` in
   arithmetic, meaning corrupted or tampered data can silently turn into
   wrong balance totals instead of a visible error. The 1,000,000-iteration
   PBKDF2 buys nothing here — the input to it is public (checked into the
   repo), so the derived key is too.
   - [x] Switch to AES-GCM or ChaCha20-Poly1305 (authenticated encryption).
     **Core done** — `utils/aead_crypto.py`: AES-256-GCM, versioned
     envelope (`version | algo_id | nonce | tag | ciphertext`), random
     12-byte nonce per call (verified two encryptions of the same
     plaintext never produce the same output). No fail-open: every
     failure mode (wrong key, wrong key length, tampered ciphertext/tag/
     nonce/version/algo-id byte, truncated envelope, invalid base64,
     non-UTF-8 plaintext after decrypt) raises `DecryptionError` — this is
     the actual point of the whole item, tested explicitly per failure
     mode in `tests/test_aead_crypto.py`, not just a happy-path round
     trip.
   - [x] Generate a random key per install; store it — **done, including
     the OS keystore adapters.** `utils/key_provider.py::KeyProvider` is an
     abstract `get_or_create_key() -> bytes` contract, deliberately
     independent of *where* the key lives. `FileKeyProvider` (32 random
     bytes on first use, mode `0600`) is the fallback, not the only
     implementation:
     - `create_platform_key_provider()` selects per platform —
       `DpapiKeyProvider` on Windows, `KeyringKeyProvider` (Secret
       Service/KWallet) on Linux, owner-only file everywhere else.
     - `MigratingKeyProvider` wraps the pair so an existing file-based key
       is moved into the OS keystore on first use; `KeyProtectionStatus`
       reports which mechanism is actually protecting the key.
     - **Verified empirically on this Linux dev machine:** a fresh profile
       produced a working key with *no* `encryption.key` file on disk —
       the key went straight into the Secret Service keystore. The earlier
       "OS keystore adapter still open" note was stale.
     - Still needs a real Windows box to confirm the DPAPI path end to end
       (same class of check as item 3).
   - [x] Prefix ciphertext with a version byte + algorithm id + nonce —
     done, see envelope format above.
   - [x] On decrypt failure, surface the error — done in the new module
     (see above), and **now live in the app's actual decrypt path for new
     data** — see the integration note below. Still fail-open for data
     that isn't in the new format, deliberately (see below).
   - [x] Write an explicit migration for existing databases (re-encrypt
     every row under the new scheme). Take a DB backup immediately before
     running it. — **Done.** The "not started" note below was stale; the
     work exists and is wired end to end:
     - `services/crypto_migration_service.py` —
       `inspect_legacy_encryption()` is a read-only inventory (never
       mutates, never creates a backup); `migrate_legacy_encryption()`
       takes a verified backup first, then migrates inside a single
       `BEGIN IMMEDIATE` transaction, re-decrypting each new value to
       verify it before committing, and refuses to commit if any legacy
       field remains. Records itself in `schema_migrations`, so re-running
       is a no-op.
     - Reachable by the user: Data & Privacy → migration entry
       (`mixins/migration_mixin.py::_on_migration_selected`), which shows
       the inventory *before* asking for a passphrase and writes the
       backup to `data_dir()/backups/pre-migration-<timestamp>.backup`.
     - **Acceptance-checked on a realistic database, not just unit
       fixtures:** a full mock profile (1014 records / 2030 encrypted
       fields across every encrypted table) was rewritten into legacy CBC
       and migrated back — 0.8 s, zero fields left in the old format, zero
       plaintexts altered, second run idempotent.
     - **Coverage gap found and closed while verifying this.** The
       existing `tests/test_crypto_migration_service.py` proves the
       *mechanism* (backup-first, rollback, idempotence) but only over one
       table and two fields — deliberately breaking the migration so it
       silently skipped `savings_goals` left that suite fully green. New
       `tests/test_crypto_migration_coverage.py` asserts that every table
       in `ENCRYPTED_FIELDS` is actually migrated and that plaintext
       (Turkish characters, decimals, long text, a value literally
       containing `AEADv1`) survives byte-for-byte; it fails on that same
       injected gap. It also pins `ENCRYPTED_FIELDS` itself, so adding an
       encrypted column without extending the migration breaks the build.
     - **`ENCRYPTED_FIELDS` completeness was measured, not assumed:** every
       table/column in a generated profile was scanned for AEAD envelopes
       and cross-checked against the list. All 13 listed fields are
       genuinely encrypted, and no column outside the list holds encrypted
       data. (`installment_plans` is created lazily by
       `transaction_service`, so it is absent from a fresh schema —
       `_candidate_fields()` already handles a missing table correctly.)
   - Depends on (4): this touches the same `finance.db` the data-directory
     move touches. Do both in the same migration window — moving the file
     and re-encrypting it separately doubles the chance of a user's data
     getting stuck mid-migration. (4) shipped first, so this is now
     unblocked.
   - [x] **Wired into the app's real `encrypt()`/`decrypt()` — done** —
     [PR #22](https://github.com/superuser-d0/archlence/pull/22).
     `utils/crypto.py` is now a transparent dispatcher rather than the
     dead AEAD module sitting unused next to the live CBC one. All ~13
     real call sites (`services/*.py`, `database/*.py`, `main.py`) are
     **unchanged** — same `encrypt(data, password)` /
     `decrypt(enc_data, password)` signatures, same fail-open external
     contract. Only the internals moved:
     - `encrypt()` now always produces AEAD ciphertext (AES-256-GCM,
       random per-install key via `FileKeyProvider`, key file at
       `data_dir()/encryption.key`), prefixed with a literal `AEADv1:`
       marker. The old CBC *encryption* code is gone — nothing will ever
       write in that format again, so there was no reason to keep it.
     - `decrypt()` checks for the `AEADv1:` prefix and dispatches
       accordingly. Base64 never contains `:`, so old ciphertext can
       never be misdetected as new. Without the prefix, decryption falls
       through to the **unmodified** legacy CBC path — old data is never
       touched, rewritten, or migrated; it just stays readable forever.
       Verified against a real ciphertext blob generated by this
       module's pre-integration code (not reconstructed from the new
       code, which would make the test circular) — see
       `tests/test_crypto.py::LegacyFormatBackwardCompatibilityTest`.
     - The key file itself inherits every hardening already done to
       `FileKeyProvider` in [PR #21](https://github.com/superuser-d0/archlence/pull/21)
       (atomic creation, no double-click race) — this integration is what
       actually puts that code on a real path for the first time.
     - Test isolation: `run_tests.py` now also sandboxes
       `XDG_DATA_HOME`/`XDG_CACHE_HOME`/`XDG_STATE_HOME` to a throwaway
       temp dir for the whole suite — dozens of tests call
       `encrypt()`/`decrypt()` incidentally, and without this every test
       run would have created a real key file in the developer's actual
       `~/.local/share/Archlence/`. Same principle as the `ARCHLENCE_HEADLESS`
       placement, applied to a more sensitive artifact.
     - Caught its own regression before merging: `main.py`'s crypto-warmup
       thread used to warm the cache via `decrypt(encrypt("archlence-warmup"))`
       — a round trip that, post-integration, never touches the legacy
       PBKDF2 path at all (since `encrypt()` now always produces AEAD
       output), silently defeating the warmup's entire purpose for every
       *existing* (not-yet-rewritten) row a real user has. A test written
       for this exact regression (`test_startup_performance.py::CryptoWarmupTest`)
       failed immediately when the integration landed; fixed by warming
       `_get_key`/`_get_aead_key` directly instead of relying on an
       indirect round trip.
   - **Superseded note (kept for history):** this section used to say bulk
     re-encryption was deliberately not done and that old rows would stay
     in legacy CBC until something naturally rewrote them. That is no
     longer accurate — the explicit, user-triggered migration described
     above exists, is backup-first, and is covered by tests. Old data is
     still *readable* indefinitely (`decrypt()` handles both formats), so
     the migration remains opt-in rather than automatic, which was always
     the intent.
   - [x] **Callers updated to the fail-closed contract.** This entry used to
     say `decrypt()` was still fail-open and that fixing it meant touching
     ~55 call chains unsafely. Both halves were wrong. `decrypt()` itself
     has raised typed errors since PR #22 — the *callers* were the stale
     part, and there are 21 of them, not 55.
     - Measured: corrupt envelope, tampered ciphertext, non-base64 legacy
       data and an unreachable key all raise `DecryptionError` subclasses
       via `ArchlenceError`. **None is a `ValueError` or `TypeError`**, so
       the old `except (ValueError, TypeError)` blocks never fired on real
       corruption; the exception escaped to wherever it landed. Four files
       carried a copied comment asserting the opposite.
     - Every site now follows the pattern `financial_summary_service` and
       `budget_service` already used: re-raise `KeyUnavailableError`,
       handle `(DecryptionError, ValueError, TypeError)`. The distinction
       is the point — per-record corruption is tolerated so one bad row
       cannot drop a list, but an unreachable key fails *every* row, and
       swallowing that per row would present a total failure as ordinary
       data (all `0,00 TL`, all `Bilinmeyen Hedef`, or a CSV export that
       comes out silently blank and reads as data loss).
     - 8 sites (the display-text ones) previously left no trace at all;
       they now log under `[VERİ BÜTÜNLÜĞÜ]` like the amount fields did.
     - **Pre-existing bug the new tests found:**
       `get_asset_transaction_history()` logged `r['id']` while its query
       never selected `id`, so on a genuinely corrupt row the error handler
       itself died with `IndexError`. That path had never been exercised.
     - `tests/test_decrypt_error_contract.py` pins both halves and was
       checked to have teeth in four independent ways.
   - **Still open, deliberately (Aşama 3):** whether some *amount* fields
     should propagate `FinancialDataIntegrityError` rather than falling
     back to `0.0`. That changes what appears on screen — a list may stop
     rendering entirely — so it wants GUI verification and is a product
     call, not a mechanical one. The work above preserves every existing
     fallback value unchanged.

6. ~~**PIN hashing: Argon2id**~~ **Argon2id done** — [PR #14](https://github.com/superuser-d0/archlence/pull/14).
   **Attempt throttling/lockout still open.** `security/security_service.py`
   hashed the PIN with a single round of salted SHA-256 — the salt stops
   rainbow tables but does nothing to slow down brute force, and a 4-6
   digit PIN's keyspace is small enough that matters. This was the one
   Phase 1 item not coupled to Windows/GUI verification (pure backend
   logic, fully unit-testable), so it was picked to work on while the
   Windows-dependent items (2-5) wait.
   `hash_password()` now produces Argon2id hashes (library defaults: 64
   MiB memory, 3 iterations, 4-way parallelism — OWASP's recommended
   range, not hand-tuned). Existing installs' hashes stay valid: `verify_password()`
   detects format from the hash's own shape (Argon2id strings self-identify
   with a `$argon2id$` prefix; the legacy format is always exactly 64 hex
   characters) and verifies either way. On a **successful** login against a
   legacy hash, `main.py::check_login` silently re-hashes with Argon2id and
   overwrites the stored record — deliberately gated behind a successful
   verification first, so an offline attacker who doesn't know the PIN
   can't trigger the upgrade themselves and can't distinguish "wrong PIN"
   from "hash format" from the outside.
   This was the smallest main.py touch made all session (4 lines, additive,
   inside one existing method's success branch, no KV/widget changes) —
   tested anyway by calling `ArchlenceApp.check_login` directly against a
   lightweight stand-in `self` (no real Kivy window needed for a plain
   Python method call); see `tests/test_pin_lazy_migration.py`.

   **Attempt throttling: done** — [PR #15](https://github.com/superuser-d0/archlence/pull/15),
   landed separately as planned. Corrected course mid-session on this one:
   originally deferred as "needs Windows/GUI to verify," which was wrong —
   only the *acceptance* test (does a real window show the lockout message)
   needs Windows; the actual throttle logic is pure and fully unit-testable
   without a window, same as the hashing swap. `security.security_service.LoginThrottle`
   tracks `{failed_attempts, last_failed_at}` as plain data the caller
   owns (no hidden state in the class itself) — first `FAILED_ATTEMPT_THRESHOLD`
   (3) wrong attempts have no delay (a mistyped PIN shouldn't be punished),
   then lockout duration doubles per attempt up to a `LOCKOUT_MAX_SECONDS`
   (300) cap. Every duration/expiry calculation takes an injectable `now`
   (defaults to `time.time()`), so `tests/test_login_throttle.py`'s 11
   tests run in 0.000s — no test sleeps to prove a 5-minute lockout expires.
   **Decision made explicitly, not defaulted into:** lockout state is
   persisted in `config_store` (same durable local storage `pin_hash`
   already uses), survives app restart. An in-memory-only counter would
   have been simpler to write but trivially defeated by restarting the
   app — for a threat model that includes someone with physical/file
   access to the device, that would have made the whole feature
   decorative. Wired into `main.py::check_login`: a locked state now
   blocks PIN verification entirely (correct PIN included — no signal an
   attacker could use to distinguish "wrong PIN" from "locked out" get
   evaluated differently), a fresh failure updates and persists the
   counter, and success resets it. Covered by
   `tests/test_pin_lazy_migration.py::PinThrottleTest`.

## Phase 2 — Hardening (after Phase 1 ships)

Not release-blocking, but worth doing before calling this stable.

- ~~**Implement search**~~ — **Done for names, deliberately scoped** — the home
  header carried a search bar from `0a905a1` through v0.0.10 that was never
  wired to anything, and a user reported it. It now searches account and
  category names (`services/search_service.py`, `mixins/search_mixin.py`).

  **Still open: searching transaction descriptions.** Those fields are
  encrypted, so matching them cannot be pushed into SQL — it means decrypting
  a working set. A full decrypt of 50.000 transactions measures 1,1s
  (`docs/performance/benchmark-results-windows.json`), so a naive
  implementation would freeze the UI on every keystroke. Doing it properly
  needs a decision on one of: a searchable index built at write time (which
  reintroduces plaintext-adjacent data on disk and needs its own threat
  review), decrypting in a background worker with cancellation, or restricting
  description search to a bounded recent window. None of these is obviously
  right, which is why the first round stopped at names.

- ~~**Fix Turkish folding in the older search boxes**~~ — **Done.** There were
  three call sites, not two: the budget category picker used `.casefold()`,
  and the BIST and crypto pickers used `.lower()`, which is weaker still. All
  three now go through `services.search_service.matches`.

  The BIST list made the cost concrete, since most of its names are Turkish.
  Measured against the real `BIST100_STOCKS` data, the old code returned **no
  results at all** for `is bankasi` or `tupras`; both now return the right
  row. A user could not find İş Bankası by typing its name.

- ~~Split overly broad exception handling by failure type~~ — **Partially
  done, scope deliberately narrowed** — [PR #13](https://github.com/superuser-d0/archlence/pull/13).
  ~200 `except Exception` blocks exist across the codebase; ~157 of them are
  in `main.py`/`mixins/`/`ui/` — the same UI layer the `main.py` split was
  deferred for, and for the same reason: I can't run the GUI here to verify
  a narrower catch doesn't let a real Kivy-lifecycle edge case crash a
  screen instead of degrading gracefully. Scoped to the 58 in
  `services/`/`database/`/`utils/` instead — fully unit-testable, no UI
  risk.
  Two behavior-vs-narrowing options were on the table for the decrypt-
  adjacent sites specifically: (A) narrow the caught exception type only,
  keep the existing fail-open recovery (still 0.0 / a placeholder string on
  a real decrypt failure), or (B) also change the recovery to raise instead
  of silently defaulting. B was rejected after checking two real call
  chains: one (`ui/charts.py`'s caller) degrades safely to an empty chart,
  but another (`main.py`'s dashboard-metrics refresh) would have gone from
  "shows a slightly-wrong number" to "the home screen silently never
  refreshes again," and there was no way to check the other ~55 call chains
  or see the resulting UI without a real window. Went with A: `utils/crypto.py::decrypt()`
  never actually raises (it already catches everything internally) — so the
  only exceptions that ever reached a caller's `except Exception` were
  `ValueError`/`TypeError` from feeding a non-numeric placeholder into
  `float()`. Narrowed to exactly that, added logging that didn't exist
  before (a decrypt failure used to leave zero trace anywhere), and proved
  the narrowing does something real: an unrelated bug injected into the
  call chain now raises instead of silently becoming an “unknown debt” label or
  `0.0` (see `tests/test_crypto.py::NarrowedExceptHandlingTest` and
  `tests/test_exception_narrowing.py`). `utils/crypto.py::encrypt()`'s
  fail-open-to-plaintext path (a separate, arguably worse issue — encryption
  failure currently writes real financial data to disk unencrypted with no
  trace) got the same narrow-and-log treatment, not a behavior change —
  actually fixing that fail-open belongs to the Phase 1 crypto migration
  item, which is redesigning this whole mechanism anyway.
  The `main.py`/`mixins/`/`ui/` ~157 remain untouched — same open question
  as the `main.py` split: revisit once there's a way to verify GUI behavior
  in this environment, or the user tests changes directly.
- ~~Stock price cache TTL is Istanbul/BIST-hours-based regardless of the
  ticker's actual exchange~~ — checked before implementing, corrected:
  stock entry only ever goes through the BIST100 picker
  (`mixins/asset_mixin.py::show_add_asset_dialog`, `data/bist100.py`),
  there's no free-text/non-BIST ticker path in the app today, so the
  BIST-only market-hours check is actually correct for every reachable
  case. Building exchange/timezone tracking now would be solving a
  problem the app doesn't have yet — revisit only if non-BIST stock
  entry is ever added.
  The other half of this finding was real, independent of exchange:
  **Done** — [PR #11](https://github.com/superuser-d0/archlence/pull/11).
  `services/price_service.py::get_price()` had its own fetch gate that
  duplicated (and diverged from) `fetch_prices_async()`'s — the latter
  already special-cased "no cache at all → fetch once even if the market
  is closed" (with almost this exact comment already in the code), but
  `get_price()` blocked the call before ever reaching that logic, so a
  never-cached BIST/FX/gold symbol added while the market was closed
  would never get its first price. `get_price()` has zero production
  callers today (verified — only its own test called it), so this was
  latent, not something a live user hit, but it was a live trap for
  whoever calls it next. Fixed to defer to the same logic
  `fetch_prices_async()` already had; verified the old gate actually
  fails (reproduced the bug standalone before trusting the fix).
- `main.py` is ~1,800 lines and `ArchlenceApp` inherits from a long list of
  mixins. Split screen behavior into separate controller/view-model
  classes; keep `ArchlenceApp` to app lifecycle only.
- ~~Split `requirements.txt` into `requirements-runtime.txt` and
  `requirements-dev.txt`, plus a pinned lockfile.~~ **Done** —
  [PR #12](https://github.com/superuser-d0/archlence/pull/12). Every
  package's real reverse-dependency graph was checked with `pip show
  <pkg> | grep Required-by` before moving or deleting anything — a plain
  "is it imported" grep is not safe here: `services/price_service.py`
  uses pandas' DataFrame API (`.columns`, `.iloc`, `.dropna()`) on
  whatever `yfinance.download()` hands back without ever writing
  `import pandas`, and Kivy loads Pillow as an internal image backend
  the same way. That check also caught real cases the naive approach
  would have gotten backwards: `docutils` and the bare `Kivy-Garden`
  package looked disposable but are `Required-by: Kivy` itself.
  `matplotlib`/`scipy`/`kivy_garden.matplotlib` (already known dead
  weight from the Windows-build-hang investigation) plus their
  matplotlib-only transitive deps (`contourpy`, `cycler`, `kiwisolver`,
  `pyparsing`) were dropped entirely rather than moved anywhere — proven
  unused, not just unclassified. Verified by installing
  `requirements-runtime.txt` into a throwaway venv from scratch and
  running the full suite against it: 348/348, no reliance on anything
  that got dropped. No separate lockfile was added: every line in
  `requirements-runtime.txt`/`requirements-dev.txt` was already pinned
  to an exact version (including transitive deps), which already gives
  the same reproducibility a lockfile would.

## Notes on scope

This roadmap was drafted after an external review (GPT) of the public repo
as of 2026-07-27. Every finding was independently re-verified against the
actual code before being included here — a couple of things the review
called Phase 2 (the data directory, PBKDF2's real weakness) got moved up
after checking, because they change what "the app works at all" means, not
just "the app is polished."
