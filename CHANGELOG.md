# Changelog

## [0.0.3] — 2026-08-02

This release replaces the numeric-only PIN with a password policy, splits
recurring incomes into their own dashboard card, and fixes Borsa Istanbul
stocks reporting ₺0.00. It remains a **pre-release**.

### Highlights

- Local sign-in now requires a password (minimum length, one uppercase
  letter, one special character) instead of a 4-digit PIN, and a new
  Settings entry lets you change it without leaving the app.
- Recurring incomes (salary, etc.) moved out of the subscriptions card into
  their own "Active Incomes" card, so they no longer read as expenses.
- Assets typed as "Hisse Senedi" (stock) now resolve to their Borsa
  Istanbul ticker again and fetch a live price instead of showing ₺0.00.

### Financial correctness and reliability

- **Stock assets stopped pricing.** `normalize_asset_type` only recognized
  the tokens `STOCK`/`HISSE`/`HİSSE`, not the literal label
  `"Hisse Senedi"` the UI actually stores. Unrecognized assets fall through
  to no live price, so every stock entered through the normal flow showed
  ₺0.00 instead of its Yahoo Finance quote. The matcher now also accepts
  `"Hisse Senedi"` (both the Turkish "İ" and ASCII "I" spelling), and the
  equivalent `"Kripto Para"` spelling for crypto, restoring the existing
  `.IS`-suffix resolution in `ticker_mapper`/`asset_service`.

### Performance

- No performance-relevant changes in this release.

### UI and accessibility

- Recurring incomes render in a dedicated "Active Incomes" card with a
  green, filled `cash-multiple` icon, visually distinct from the gray
  repeat icon used for expense subscriptions.
- The Calendar and Monthly Budget dialogs, both of which do heavy
  calculation while building their view, now show a "Please wait,
  loading..." dialog for one frame instead of appearing to freeze.
- Password fields no longer insert a stray character when Tab is pressed
  to move to the next field, and now show persistent helper text stating
  the password rule inline.
- All PIN wording ("PIN", "PIN Değiştir", ...) was renamed to
  "Şifre"/"Password" throughout the UI and the i18n table to match the
  password-based flow.

### Testing and packaging

- The complete 600-test suite passes with this release, including a new
  assertion that the budget planner's deferred build (behind the new
  loading dialog) actually runs under `Clock.tick()`.
- No installer or packaging changes in this release.

### Additional issues found and fixed

- **PIN brute-force search space.** A 4-digit numeric PIN has only 10,000
  possible values; even with Argon2id hashing and the existing
  exponential login lockout, that is a small space for an attacker with
  physical/file access to a device to work through offline. The new
  password policy (minimum length, uppercase, special character) moves
  the character set from digits-only to alphanumeric-plus-symbols, adding
  orders of magnitude of combinations on top of the existing lockout and
  hashing.
- The brand-icon lookup table now recognizes roughly twenty additional
  Turkish banks and fintech wallets (Garanti BBVA, İş Bankası, Yapı
  Kredi, Ziraat, Akbank, VakıfBank, Halkbank, Enpara, QNB Finansbank,
  TEB, DenizBank, Kuveyt Türk, Türkiye Finans, Albaraka, Papara, Ininal,
  Tosla, Paycell, Nays, Pokus, Ozan), so recurring payments to these show
  their real logo instead of the generic fallback.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.
- **Existing 4-digit PINs are not migrated.** The new password policy is
  only enforced at setup/change time; a user who upgrades without
  changing their password keeps signing in with their old 4-digit PIN
  until they use Settings > Change Password.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.3.exe`
- Linux: `Archlence-0.0.3-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.3-sbom.cdx.json`.

## [0.0.2] — 2026-07-30

This release fixes two Windows-specific defects that could lead to lost work or
an unclean shutdown. It remains a **pre-release**.

### Highlights

- The complete test suite now runs in Windows CI as well as Linux. Both fixes
  in this release were found directly through that coverage.

### Financial correctness and reliability

- **Turkish error text could terminate a transaction on Windows.** Legacy
  Windows consoles commonly use cp1252, which cannot encode several characters
  used in Turkish messages. Many application messages are emitted inside exception
  handlers, so a `UnicodeEncodeError` there escaped the original handler and
  could terminate the operation. In the confirmed case, a subscription-radar
  failure caused the complete transaction to be lost. Console streams now use
  UTF-8 with replacement for unsupported output, preventing the reporting path
  from terminating the operation.
- **The Windows single-instance lock could fail during shutdown.** The lock
  file was truncated after its byte was locked. Windows byte-range locking
  could then reject the unlock call and crash shutdown. The lock now uses a
  fixed byte that is never truncated, and release is guarded on every exit
  path.

### Performance

- Fixing Windows `multiprocessing` spawn safety made `run_tests.py` up to three
  times faster in the measured CI job. Previously, tests that created a child
  process could rerun the complete suite in every child. This result is from CI
  and has not been independently benchmarked on user hardware.

### UI and accessibility

- This release has no user-visible UI change. Both fixes concern background
  error reporting and process lifecycle.

### Testing and packaging

- The complete suite now runs on Windows CI.
- `run_tests.py` is safe under the Windows `multiprocessing` spawn method; the
  suite is no longer recursively executed inside child processes.
- Test isolation now uses the cross-platform `ARCHLENCE_HOME` override. The
  previous mechanism did nothing on Windows and could write into a real user
  profile.
- The v0.0.1 → v0.0.2 upgrade smoke test installs the real baseline release,
  writes a sentinel record, upgrades in place, and verifies preservation.

### Additional issues found and fixed

- Several test helpers left SQLite connections open. A context manager around
  `sqlite3.connect(...)` controls a transaction but does not close the
  connection. Linux allows deletion of an open file, masking the defect;
  Windows kept it locked and failed cleanup. The helpers now close their
  connections explicitly.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.2.exe`
- Linux: `Archlence-0.0.2-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.2-sbom.cdx.json`.

## [0.0.1] — 2026-07-30

Initial public release. This is a **pre-release**: packages install and launch,
and the flows below are covered by tests, but it is not yet considered stable
or recommended for everyday financial tracking.

### Highlights

- Fixed a cursor defect that rearranged digits while entering an amount.
- Removed UI stalls from the calendar, monthly budget, category settings, and
  transaction-add flows.
- Asset purchases now select an account that can actually fund the purchase.

### Financial correctness and reliability

- **Amount-entry corruption:** the thousands-separator mask ran inside Kivy's
  `on_text` event, leaving the cursor one character behind. Typing `1234567`
  could produce `1.235.674`, recording a different amount from the one entered.
  Formatting now occurs after editing and was verified in a real SDL2/OpenGL
  window.
- **Extreme-amount guard:** the integer portion is limited to 12 digits. Larger
  values can exceed the reliable integer range used by `float64` and silently
  corrupt balance arithmetic. The limit is applied during input and does not
  rewrite existing records.
- **Funding-account selection:** asset purchases were always deducted from
  `DEFAULT_ACCOUNT_ID` (`1`). That row may not exist, or the user's funds may
  be held elsewhere. Archlence now selects a checking account that can cover
  the amount and reports the named account and shortfall when none can.
- **Backdated transaction entry removed:** a past-dated record changed the
  current balance immediately but could not be placed correctly in the
  historical balance ledger. Future-dated pending transactions remain
  supported.

### Performance

These results measure call counts and work performed, not elapsed time, and are
protected by regression tests.

- **Calendar:** selecting a day no longer rebuilds all 42 cells or opens
  unbounded threads and SQLite connections. Twelve rapid selections now
  coalesce into one database read, and only the affected cells are repainted.
- **Monthly budget:** twelve rapid month changes now coalesce into one list
  rebuild.
- **Category settings:** ten rapid toggles now coalesce into one chart refresh.
- **Transaction entry:** four heavy refreshes are spread across separate
  frames instead of blocking one frame together.

### UI and accessibility

- Asset-add failures now show the actual cause, such as the funding account and
  missing amount, instead of a generic error.
- The transaction date picker no longer offers past dates.

### Testing and packaging

- **Test reporting restored.** Kivy replaces `sys.stderr` during import. The
  runner previously captured the stream afterward, hiding test names,
  tracebacks, and the final summary after roughly the 69th test. It now
  captures the real stream before any Kivy import while retaining a correct
  failure exit code.
- Price and portfolio failures now use the persistent rotating log instead of
  `print()`, which disappears from Windows `console=False` packages.
- Test suite at release: 595 passing tests, including 26 new regression tests.

### Additional issues found and fixed

- The fake text field in `tests/test_formatters.py` updated its cursor in the
  opposite order from Kivy and allowed the production amount bug to pass. It
  now follows real `insert_text` ordering.
- `tests/test_asset_price_worker.py` treated a `print()` call as proof of
  logging. It now verifies the persistent logger used by packaged builds.

### Known limitations

- This is not stable and is not recommended for daily financial tracking.
- The Windows gold/asset-add fix still needs broader user-hardware validation.
  Failures are recorded under
  `%LOCALAPPDATA%\Archlence\Archlence\Logs\archlence.log`.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Broad exception handlers and `print()`-based reporting remain in parts of
  the UI layer.
- Decimal rules exist, but not every monetary path has completed migration.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.1.exe`
- Linux: `Archlence-0.0.1-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.1-sbom.cdx.json`.
