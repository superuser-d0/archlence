# Changelog

## [0.0.7] — 2026-08-06

The dashboard's period cards were answering a different question than the one
they appeared to ask: the percentage compared this period's cash flow with the
previous period's, which is a growth rate, not a balance change — and it forced
±100% whenever the previous period happened to be empty. Switching the
interface to English also left Turkish text inside every chart. Both are fixed
here. It remains a **pre-release**.

### Highlights

- **Dashboard period cards now measure what they claim to.** The nominal
  change, the percentage, the heading and the active filter all come from one
  shared period definition, and the percentage is a genuine balance change
  measured against the balance at the end of the day before the period starts.
- **An unknown or zero baseline no longer produces a fabricated number.** A
  move away from an actual zero balance has no finite percentage, so the card
  shows `—` instead of ±100%. Zero to zero is the one well-defined no-change
  case and reads as 0%.
- **Switching to English now translates the charts too.** Legends, month
  abbreviations, day labels, asset-type names and the asset history all rebuild
  on a language change instead of leaving Turkish text in an English view.
- The README is rebuilt around the application itself, with a full screenshot
  set generated from a synthetic profile rather than hand-edited images.

### Financial correctness and reliability

- `services/dashboard_period_service.py` is the single definition of the four
  dashboard periods (Today, 1 Week, 1 Month, 1 Year) and of the change
  calculation. The periods use inclusive bounds, and the baseline is the end of
  the day immediately before the period begins.
- The percentage is `(current − starting) / |starting| × 100`, computed in
  `Decimal` rather than binary floating point.
- `percentage_change` returns no value — rendered as `—` — when the baseline is
  unknown or when the balance moved away from an actual zero. Both cases
  previously produced a confident number that meant nothing.
- Dashboard totals are taken from account balances directly, so savings
  transfers and other ledger-only movements no longer make the dashboard
  disagree with the Accounts screen.
- Stale background results are discarded after a filter change, so a slow
  query for the previous period can no longer overwrite the selected one.

### Performance

- No intentional performance changes in this release. The dashboard metrics
  cache introduced in 0.0.6 is unaffected; its tests were extended to cover the
  new period key so a filter change cannot serve a cached result from a
  different period.

### UI and accessibility

- Chart legends ("Income", "Expense", "Opening Balance"), month abbreviations
  and day labels are generated from the application language instead of
  hardcoded Turkish or the process locale.
- Asset types display as Currency, Gold, Crypto and Stock in English.
- A language change clears the chart texture cache and re-renders active assets
  and asset history; previously those kept their original-language text until
  the view was rebuilt some other way.
- Turkish remains unchanged.

### Testing and packaging

- New coverage: `test_dashboard_period_change.py`, `test_chart_localization.py`
  and `test_readme_sample_profile.py`, alongside extensions to
  `test_dashboard_metrics_cache.py`. Cases include each period boundary,
  positive and negative change, a zero baseline, a missing snapshot with ledger
  replay, no data at all, a stale cache result after a filter change, and
  dashboard/accounts agreement after a savings transfer.
- 680 tests pass locally; 2 are skipped for platform reasons (one needs a real
  Kivy window, one is Windows-only `chmod` behaviour).
- `scripts/dev/seed_readme_profile.py` and
  `scripts/dev/capture_readme_screens.py` make the screenshots reproducible
  from a seed rather than from a private profile. The seeding tool refuses to
  touch a real Archlence data directory, refuses home, the repository root and
  anything beneath it, and will only reset a profile it marked itself.
- `scripts/check_version_consistency.py` no longer requires a per-version
  heading in the README, which now carries a dynamic latest-release badge
  instead of a pinned version.
- The `PKGBUILD` checksums for 0.0.6 were verified and filled in after that
  release published. They are placeholders again here for the same reason.

### Additional issues found and fixed

- These two defects were found while regenerating the README screenshots — the
  screenshots were the test. Reviewing what the application actually rendered,
  rather than what the tests asserted, is what surfaced both.
- The README carried pinned checksums and version-specific download links that
  went stale on every release; general downloads now point at
  `/releases/latest`.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The shared `Decimal` policy is not yet applied across every financial path.
  The new period service uses `Decimal` throughout; older paths are unchanged.
- Two functions still close their database connection without protection:
  `initialize_database()` and `generate_mock_data.main()`, both unchanged since
  0.0.6 and both deliberate.
- Broad exception-handler debt and the pyflakes backlog are both still open.
- DPAPI and OS-keystore behaviour still deserves verification on real Windows
  hardware rather than CI runners.
- Some GitHub Actions versions emit a Node.js 20 deprecation warning and are
  forced to Node.js 24 by the runner. CI is unaffected, but the action versions
  should be updated.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.7.exe`
- Linux: `Archlence-0.0.7-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.7-sbom.cdx.json`.

## [0.0.6] — 2026-08-06

This release is about failures the application was hiding from itself. A
fail-closed decryption contract added in 0.0.3 had never reached its callers,
so on real corruption the handlers written to catch it never ran; the CI gate
meant to hold the line on broad exception handlers had 44 unused slots and was
accepting new ones silently; and a dashboard summary was decrypting ten
thousand records on every render. It remains a **pre-release**.

### Highlights

- Corrupt or unreadable financial data no longer produces a confident wrong
  number. Values that feed a **total** now refuse rather than silently counting
  as zero, while values that only feed a **list** still degrade per-row — a
  wrong row is visible and correctable, the same zero inside a sum is not.
- The dashboard summary is cached on the data revision. At 10,000
  transactions a repeat render drops from **328 ms to 0 ms**.
- After **Settings → Delete Data**, the forecast and asset-history sections
  clear along with everything else. They previously kept showing results
  derived from records that no longer existed.
- **TAB** moves between fields in the add-account dialog instead of inserting a
  tab character, and the optional card-number field now reads as optional.

### Financial correctness and reliability

- `utils.crypto.decrypt()` was made fail-closed in 0.0.3, raising typed errors
  for corrupt envelopes, tampered ciphertext and an unreachable key. Its 21
  call sites were never updated and still caught `except (ValueError,
  TypeError)`, written for the old contract. Measured: all four corruption
  modes raise `DecryptionError` subclasses, and **none** is a `ValueError` or
  `TypeError` — so on real corruption those handlers never ran at all and the
  exception escaped to wherever it happened to land. Four files even carried a
  comment asserting the opposite; those comments are gone.
- `KeyUnavailableError` is now deliberately distinguished from per-value
  corruption everywhere. An unreachable key means *no* row can be read, so
  swallowing it per-row would render a total failure as "every amount is
  0,00 TL". It propagates; per-value corruption still degrades locally.
- `get_transactions_by_period` raises instead of zeroing. Its only production
  consumer already wraps the call, logs, and degrades to an empty chart — a
  visible-but-graceful failure rather than a wrong one.
- Seven functions across `main.py`, `calendar_service.py` and
  `transaction_service.py` opened a database connection and closed it as a
  plain statement, leaking the handle on any exception in between. This was not
  theoretical: it is how `export_all_to_csv` began leaking once the key error
  started propagating, and on Windows a leaked handle keeps the database file
  locked. All now use the repository's `managed_connection()`.

### Performance

- `_compute_dashboard_metrics` was profiled at 10,000 transactions: 328 ms,
  with **99% of it in AES-GCM decryption** — 10,800 `decrypt` calls, the cost
  sitting in cipher construction rather than in any Archlence code. Amounts are
  encrypted TEXT, so SQL cannot sum them and every row must be decrypted in
  Python. There is nothing meaningful to shave off the decryption itself; the
  win is not repeating it when nothing changed. The cache key is (revision,
  period filter, today), and each of the three parts earns its place — removing
  any one of them breaks a test.

### UI and accessibility

- TAB inserted a literal tab character into account fields instead of advancing
  focus. Measured: Kivy's `write_tab` defaults to `True`, and turning it off
  alone does not advance focus — `focus_next` must be set too. Both are now
  handled, with a wrap-around focus ring that the account dialog rebuilds
  whenever the account type changes, because the visible fields change with it.
- The card-number field was already optional in both the UI and the service,
  but did not read as optional. It now says so.
- The add-account empty state clears correctly.
- After a data reset, "Algoritmik Öngörü" and "Varlık Geçmişi" no longer show
  stale results. Both are computed only at startup or from their own triggers,
  and neither trigger fires during a reset, so both kept their last computed
  state indefinitely.

### Testing and packaging

- **The exception-handler CI gate had 44 free slots and was only half
  working.** Real broad handlers on `main` numbered 143; the baseline file
  recorded 187, because it was never regenerated after the 0.0.5 narrowing work
  took the count from 184 down. Measured by injection: a new broad handler in a
  *new* function was caught either way, but one added to an *existing* function
  with baseline slack was **silently accepted**. That is the more likely
  direction, and it is how the condition was found — a handler added during
  this release passed the gate while the count rose. The baseline is
  regenerated to the true count and both directions are verified.
- Windows installer smoke tests could hang indefinitely. Five
  `Start-Process -Wait` calls were bounded first; a subsequent hang proved the
  audit incomplete, and three further unbounded operations were found — an
  `Invoke-WebRequest` with no `-TimeoutSec` (the PowerShell default is `0`,
  meaning indefinite), an argument-less `WaitForExit()` that also waits on
  child processes holding inherited handles, and an unbounded recursive
  directory walk. Both smoke steps now carry a step-level timeout, which
  matters less for the minutes saved than because a step that times out
  **keeps its log**; a force-cancelled job does not, and that is why the first
  hang could not be diagnosed.
- The `PKGBUILD` checksums for 0.0.5 were verified and filled in after that
  release published. They are placeholders again here for the same reason.

### Additional issues found and fixed

- `export_all_to_csv` leaked its database connection whenever export raised.
  Found by a Windows CI failure (`WinError 32`, file in use) on a new
  key-unavailable test — a real production leak the test exposed, not a
  test-setup mistake. Local Linux runs stayed green because the same leak is
  silent there.
- A documentation entry still described `decrypt()` as fail-open, three
  releases after it stopped being so.
- A reset test could leave a background thread running past its own end.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- Two functions still close their database connection without protection:
  `initialize_database()` (~590 lines, runs once at startup) and
  `generate_mock_data.main()` (a development script that is never packaged).
  Wrapping either means re-indenting the entire body for negligible gain.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.
- Checking accounts that go negative still show only the raw negative balance,
  with no dedicated overdrawn indicator.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.6.exe`
- Linux: `Archlence-0.0.6-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.6-sbom.cdx.json`.

## [0.0.5] — 2026-08-04

This release lets you record an asset you already owned without disturbing your
wallet balance, gives the price service a fallback so a single upstream outage
no longer freezes every quote, and reports which provider actually answered.
It remains a **pre-release**.

### Highlights

- Adding an asset now asks whether the amount should come out of your wallet
  balance. Choose **Yes** for something you just bought; choose **No** for an
  asset you already owned and are only recording. Previously every entry was
  treated as a purchase, so recording an existing holding retroactively
  distorted today's balance and expense reports.
- Prices no longer depend on a single provider. When Yahoo Finance returns
  nothing for a symbol, cryptocurrency falls back to CoinGecko and foreign
  currency to Frankfurter (ECB).
- The price source shown for an asset now names the provider that actually
  answered, instead of always claiming Yahoo Finance.

### Financial correctness and reliability

- `AssetPurchaseService.create_purchase` takes `deduct_from_balance`. When it
  is false, only the portfolio row is written — no liquid-account transaction,
  no balance mutation, no balance-event entry. When it is true the operation
  stays exactly as before: one atomic transaction covering all four writes.
- Foreign-exchange rates are the linchpin of the price pipeline: crypto and
  gold are both converted to lira by multiplying with USD/TRY. Recovering that
  one rate from Frankfurter therefore keeps crypto and gold priceable even
  when Yahoo Finance is the side that failed.
- Fallback providers deliberately return values in Yahoo Finance's units
  rather than converting to lira themselves, so every downstream conversion
  path is unchanged regardless of which provider supplied the number.

### Performance

- No intentional performance changes in this release. The fallback only runs
  for symbols the primary provider did not return, so a fully successful fetch
  costs exactly what it did before — verified by a test asserting the fallback
  is not called in that case.

### UI and accessibility

- Two English strings were unreachable because the same Turkish key was
  defined twice in the translation table, so the second definition silently
  replaced the first. Affected the recurring-payment day prompt and the
  "days from now" suffix.
- The month-end forecast sentence carried a misleading `f` prefix implying the
  amount was interpolated before translation — the exact mistake that made the
  English locale fall back to Turkish in 0.0.4. The prefix was inert, and is
  now removed with a comment so it is not reintroduced.

### Testing and packaging

- The Arch package's `sha256sums` were four zero placeholders, so `makepkg`
  failed for every AUR user. Real 0.0.4 checksums were verified end to end;
  they are placeholders again here only because the 0.0.5 assets do not exist
  until this release publishes, and will be filled in immediately afterwards.
- The installer and AppImage launch smoke tests now check `crash.log` the way
  the raw-executable test already did. An application that starts, catches an
  exception, logs it and keeps running with a broken screen previously passed
  two of the three packaging paths.
- Continuous integration reports the pyflakes backlog on every run without
  blocking, and no longer mistakes a locally built package's bundled copy of
  KivyMD for project source.
- Broad exception handlers dropped from 184 to 143. Handlers that must stay
  broad — the boundaries where an escaping exception would leave the interface
  waiting forever — are now marked as reviewed rather than counted as
  unexamined debt.

### Additional issues found and fixed

- The legacy-to-AEAD encryption migration was covered by tests that all passed
  even when an entire table stopped being migrated. Coverage now asserts every
  encrypted table is included and pins the field list, so adding an encrypted
  column without extending the migration fails the build.
- A failure while computing the "today's change" figure could kill the asset
  loading thread before any list was drawn, leaving the loading skeleton on
  screen permanently and blocking every later refresh.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price fallback covers cryptocurrency and foreign currency only. BIST
  equities and gold still depend on Yahoo Finance alone — no free alternative
  source for them is integrated.
- The legacy CBC reader remains deprecated for old profiles and backups.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.
- Checking accounts that go negative still show only the raw negative balance,
  with no dedicated overdrawn indicator.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.5.exe`
- Linux: `Archlence-0.0.5-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.5-sbom.cdx.json`.

## [0.0.4] — 2026-08-03

This release lets checking accounts go negative on purpose, overhauls brand-icon
quality and performance, virtualizes the subscriptions list, and routes every
previously-silent background failure into the on-disk log. It remains a
**pre-release**.

### Highlights

- Checking accounts, savings goals, and credit-card debt payments can now go
  negative on purpose — the "insufficient balance" guard that blocked this is
  gone. Net worth math is unaffected: the signed-balance convention that
  already let credit-card debt show as a negative balance covers this too.
- Brand-icon logos are noticeably sharper. A multi-provider fallback (Google
  Favicon → icon.horse → Unavatar) replaces the single-provider lookup, and
  every downloaded image is now decoded and re-encoded as a real PNG instead
  of trusting the response's declared content type.
- The "Active Subscriptions" / "Active Incomes" cards are now backed by a
  `RecycleView`. Rendering cost no longer grows with subscription count.
- Background failures that used to `print()` to a console nobody sees in the
  packaged Windows build (`console=False`) are now written to the rotating
  log file with a full traceback.

### Financial correctness and reliability

- **Insufficient-balance guard removed.** `AccountService.check_spending_
  allowed`, `SavingsService.deposit_to_goal`, and `AssetPurchaseService.
  _pick_funding_account` no longer reject a transaction that would take an
  account negative; the atomic `WHERE balance >= ?` guards were removed.
  Asset purchases that no account can fully afford now fund from the
  richest available account and drive it negative, instead of raising.

### Performance

- **Brand-icon matching, 14x.** `classify_brand` re-normalized all 176
  known aliases on every call (~220µs for a non-matching description,
  measured). Alias normalization now happens once at import time
  (~16µs/call after).
- **Health score / forecast, 1.9x.** `compute_financial_health_score` and
  `generate_monthly_forecast` decrypted every transaction's `description`
  even though neither reads it — only `amount` and `date` are used.
  `_load_transactions` now takes `decrypt_description=False` on those two
  paths (measured on 10k transactions: 419ms → 226ms combined). The
  subscription radar and anomaly detector, which do need the description,
  are unaffected.
- **Subscription cards, O(1) instead of O(n).** Rendering used to build
  ~11 KivyMD widgets per active subscription in a single frame (~440
  widgets at 40 subscriptions). Cards now come from a `RecycleView`;
  measured widget count plateaus at 4 regardless of whether the list holds
  10, 50, or 200 entries.

### UI and accessibility

- Two Data & Privacy menu icons (`key-arrow-left`, `key-sync`) referenced
  names that don't exist in the bundled KivyMD 1.2.0 icon set and rendered
  blank; replaced with `key-plus` and `lock-reset`.
- The Calendar dialog no longer lets a day with many transactions push the
  month grid off-screen — the daily transaction list is now a bounded,
  independently-scrolling area sized to the window.
- English-locale monthly forecast text no longer mixes Turkish and English.
  The dynamic balance amount was interpolated into the string *before*
  translation, so the literal (amount-specific) string never matched the
  English dictionary and fell back to the untranslated Turkish template.
  Translation now happens on the static template; the amount is filled in
  afterward.
- "Contact Us" now opens the project's GitHub page instead of a `mailto:`
  link — issues are triaged there, not in an inbox.
- Small brand-icon logos (as low as 16px, the ceiling several providers
  publish for Turkish telecom brands) are upscaled instead of being
  discarded; a prior attempt dropped them below a fixed pixel threshold and
  made those brands' icons disappear entirely.

### Testing and packaging

- New `tests/test_icon_names.py` scans every literal icon name in `.py`/
  `.kv` source against KivyMD's bundled MDI set — the class of bug that
  shipped the two blank Data & Privacy icons above can no longer land
  silently.
- The complete suite (615 tests) passes; `flake8 --select=F821,F822,F823,
  E722` and the exception-baseline gate are both clean.

### Additional issues found and fixed

- `utils/toast.py` (the shared `MDSnackbar`-based toast, introduced this
  cycle) imported KivyMD's snackbar module unconditionally, which crashed
  two test modules on import under the headless test harness. It now
  follows the same headless-fallback contract as `main.py`'s KivyMD import
  guard.
- 108 of 109 `except`-block `print()` calls were converted to `logger.
  exception(...)`, which captures the full traceback instead of just
  `str(exception)`. The one exception (`main.py`'s headless-only mock
  `MDApp.run()`) is informational output, not a swallowed failure, and was
  left as-is. Exception *types* were intentionally left broad in this
  pass — narrowing them requires per-call-site behavioral verification and
  is tracked as follow-up work, not blocking this release.

### Known limitations

- This is still a pre-release and is not considered stable.
- Packages are unsigned; Windows SmartScreen may warn on first launch.
- The price service has a single provider (yfinance).
- The legacy CBC reader remains deprecated for old profiles and backups.
- Most `except` blocks still catch broad exception types (`Exception`);
  they are now logged with a full traceback, but not yet narrowed to
  specific exception classes.
- Checking accounts that go negative show only the raw (negative) balance
  number — there is no dedicated "overdrawn" indicator the way credit
  cards show a `debt` field. Deferred as a UX follow-up.
- Existing 4-digit PINs are still not migrated to the password policy
  introduced in 0.0.3; unaffected by this release.

### Installation and checksum verification

- Windows: `ArchlenceSetup-0.0.4.exe`
- Linux: `Archlence-0.0.4-x86_64.AppImage`
- Download `SHA256SUMS.txt` from the same release and verify the matching
  asset. The SBOM is published as `Archlence-0.0.4-sbom.cdx.json`.

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
