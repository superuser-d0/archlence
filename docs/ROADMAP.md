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

2. **Remove the `KIVY_WINDOW=mock` / `except BaseException` startup
   fallback.** `main.py:45-48` silently switches to a mock window when
   `DISPLAY` is unset, and `main.py:84` / `main.py:118` catch
   `BaseException` around the Kivy/KivyMD import and startup path, falling
   back to a stub `run()` that only prints to console. On a packaged
   Windows build this means the app can exit without ever showing a
   window, with no visible error. Gate the mock window behind an explicit
   `ARCHLENCE_HEADLESS=1` env var instead of `DISPLAY` absence, and narrow
   the `except BaseException` blocks to the specific import/init errors
   that are actually recoverable.

3. **Smoke-test the built `.exe` in CI.** Once (2) removes the silent
   fallback, add a step after the PyInstaller build that launches the
   packaged executable and verifies it actually opens a window and exits
   cleanly, rather than only checking that `dist/Archlence/` contains
   files. Depends on (2) — testing a fallback that's designed to hide
   failures proves nothing.

4. **Move user data out of the install directory, via `platformdirs`.**
   `database/db.py:6-7` derives `DB_NAME` from `BASE_DIR` (the app's own
   install location) — same pattern for logs, JSON config, and image
   caches across `services/*.py` and `main.py`. On a packaged Windows
   install this directory is commonly read-only (`Program Files`), so the
   app likely can't persist any data at all post-install, or silently
   writes into `VirtualStore` where the user will never find it.
   `platformdirs` is already in `requirements.txt` and unused — no new
   dependency needed, just use it: bundle dir (KV files, default assets),
   user-data dir (SQLite + config), user-cache dir (logos, price cache),
   user-log dir (crash logs). Depends on (3) — confirm the exe actually
   runs before deciding where it's allowed to write.

5. **Encryption: move to AEAD, generate a real key, use an OS keystore,
   version the ciphertext, migrate existing data.**
   `utils/crypto.py` has a hardcoded password and salt
   (`STATIC_SALT`, `DEFAULT_PASSWORD`) shared by every install, uses
   AES-256-**CBC** with no MAC (ciphertext can be tampered with
   undetected), and — worse — `decrypt()`'s except-all returns
   `"[Şifreli Veri]"` on any failure rather than raising. That string
   propagates into amount fields downstream and can collapse into `0.0` in
   arithmetic, meaning corrupted or tampered data can silently turn into
   wrong balance totals instead of a visible error. The 1,000,000-iteration
   PBKDF2 buys nothing here — the input to it is public (checked into the
   repo), so the derived key is too.
   - Switch to AES-GCM or ChaCha20-Poly1305 (authenticated encryption).
   - Generate a random key per install; store it via the OS keystore
     (Windows DPAPI / Credential Manager, macOS Keychain, or a keyring
     library on Linux) instead of in source.
   - Prefix ciphertext with a version byte + algorithm id + nonce so a
     future format change doesn't require a flag day.
   - On decrypt failure, surface the error — don't fail open into
     plaintext or a placeholder that silently becomes a number.
   - Write an explicit migration for existing databases (re-encrypt every
     row under the new scheme). Take a DB backup immediately before
     running it.
   - Depends on (4): this touches the same `finance.db` the data-directory
     move touches. Do both in the same migration window — moving the file
     and re-encrypting it separately doubles the chance of a user's data
     getting stuck mid-migration.

6. **PIN hashing: Argon2id + attempt throttling.**
   `security/security_service.py:25` hashes the PIN with a single round of
   salted SHA-256. The salt stops rainbow tables but does nothing to slow
   down brute force, and a 4-6 digit PIN's keyspace is small enough that
   this matters. Move to Argon2id (or PBKDF2-HMAC with a much higher
   iteration count / scrypt as a fallback if Argon2 isn't available on a
   target platform), add increasing backoff after failed attempts, and a
   temporary lockout past a threshold. Independent of (5) — can land
   separately, but shares the "verify with a real attack-cost estimate,
   not just an algorithm name swap" bar.

## Phase 2 — Hardening (after Phase 1 ships)

Not release-blocking, but worth doing before calling this stable.

- Split overly broad exception handling by failure type (decrypt error /
  validation error / network error / DB error) so a real data problem
  can't collapse into a value that looks like a normal `0`.
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
