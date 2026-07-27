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

- [ ] **CI test job.** `run_tests.py` didn't propagate a failing exit code —
  a broken build would report `0` regardless of test results, so it could
  never have failed a "required" CI check. Fixed in this same change
  (`sys.exit(0 if result.wasSuccessful() else 1)`), verified with both a
  passing and a deliberately failing run before trusting it. Add a fast
  Linux job (`ubuntu-latest`) running `run_tests.py` on push/PR to `main`,
  and mark it as a required status check once it's proven stable through
  at least one real PR cycle.
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

1. **Remove CVC and full PAN storage entirely.**
   `AccountService.create_account` accepts and encrypts `card_number_full`,
   `expiry_date`, `cvc_code` and writes them to `accounts`
   ([services/account_service.py:88-96](../services/account_service.py)).
   The UI only ever displays last-4 + network logo downstream — there's no
   product reason to hold the CVC at all, and holding it is a liability
   with no offsetting benefit. Remove the field from the dialog, the
   service signature, and the column; ship a migration that nulls out any
   `cvc_code` already on disk. No dependency on anything else — do this
   first, it's the cheapest way to close the worst exposure.

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
- Stock price cache TTL is Istanbul/BIST-hours-based regardless of the
  ticker's actual exchange, so a US stock can be treated as "market closed"
  while its own market is open — and if the cache is empty *and* the
  market's considered closed, the first fetch may never happen at all.
  Track exchange/timezone per ticker; always allow at least one fetch when
  the cache is empty, independent of market-hours state.
- `main.py` is ~1,800 lines and `ArchlenceApp` inherits from a long list of
  mixins. Split screen behavior into separate controller/view-model
  classes; keep `ArchlenceApp` to app lifecycle only.
- Split `requirements.txt` into `requirements-runtime.txt` (what the
  shipped app needs) and `requirements-dev.txt` (flake8, testing tools),
  plus a pinned lockfile.

## Notes on scope

This roadmap was drafted after an external review (GPT) of the public repo
as of 2026-07-27. Every finding was independently re-verified against the
actual code before being included here — a couple of things the review
called Phase 2 (the data directory, PBKDF2's real weakness) got moved up
after checking, because they change what "the app works at all" means, not
just "the app is polished."
