# Archlence — V1.0 Vision and Scope Decision (2026-07-23)

## Name and Brand Decision (2026-07-23)
The product name has been finalized as **Archlence**. The name was chosen to be distinguishable, suitable for international use, and to create a unique brand identity in the fintech domain.

**Brand identity (revised 2026-07-30):** A bold white "A" monogram on the brand
blue (`#5444E5`) — deliberately the *same* value as `ARCHLENCE_PRIMARY_HEX` in
`ui/theme.py`, so the app icon matches the Premium Mavi Tema primary rather than
drifting into a second, unmanaged brand colour. The letterform takes a cue from
sharp geometric distro marks (pointed apex, concave outer edges so the legs flare
out, open triangular notch at the baseline) while staying distinct: the curved
crossbar band is Archlence's own signature, inherited from the previous mark.
See `assets/icon_source.svg` — still the single source for `icon.png`/`icon.ico`.

*Why it changed:* the original identity was a white monogram on black (`#141414`)
built from fragile petal forms plus semi-transparent "burst" rays. Verified
empirically at real icon sizes: those thin rays disappear entirely by 48px
(taskbar/tray), leaving the mark unreadable. The new solid letterform stays
legible down to 16px.

**Applied changes (in this session):**
- [x] `README.md` — Title, feature list, roadmap, and contact address updated to Archlence; former name change added as a note.
- [x] `archlence.spec` — `name="Archlence"`, `icon="assets/icon.ico"`.
- [x] `.github/workflows/build-windows.yml` — Artifact name and `dist/` path updated to Archlence.
- [x] `assets/icon_source.svg` — Final icon vector source saved.

- [x] Based on `icon_source.svg`, the desktop `icon.png` and multi-sized `icon.ico` were generated.
- [x] Source code, UI texts, tests, configurations, and packaging identifiers migrated to the name Archlence.

**Rename + QA audit results (2026-07-23, separate AI session):**
- [x] 39 logical files/assets affected (34 edits, 2 file renames, 3 icon assets). `FinoraApp` → `ArchlenceApp`, `finora.spec` → `archlence.spec`. A migration approach was used for the config, copying the old file to `archlence_config.json` (no user data lost). Cryptographic constant byte values were left untouched (behavior preserved). In the final scan, excluding out-of-scope folders, literal "Finora" matches: **0**.
- [x] Visual/functional QA — 1 bug found and fixed: The health score sparkline was in the correct parent chain but wasn't positioned inside `MDFloatLayout` (stayed at `pos=(0,0)`), thus its canvas was drawing at the bottom-left of the window over the bottom navigation. Fixed by adding `pos_hint: {"x": 0, "y": 0}` in `ui/dashboard.kv:664`. All screens (Home, Assets, Cards, Tools, Settings) + What-If (31 chart points), Balance History, and `MDDatePicker` were rescanned in a real SDL2/OpenGL window; no other overflows/incorrect parents found.
- [x] Verification: `compileall` passed, `git diff --check` clean, **121/121** tests green. There is a harmless `ResourceWarning: unclosed database` in the test suite that doesn't cause functional failure — noted for quality tracking.

## Decision
"Broad V1.0" — We will not proceed to packaging/release until the 5 killer features on the README roadmap are complete. The core (accounts, transactions, balance math, AES-256 encryption, UI/theme system) is already finished and tested; the remaining work consists of these 5 features + technical debts + packaging.

## Current Status (reference: README.md, ANTIGRAVITY_TASKS*.md)
- ~17,500 lines of code, 3 months of development.
- Core system (DB, services, balance/net worth calculation, test infrastructure) is stable.
- UI: Rounds 1-4 completed (Accounts/Cards tab, dialog layout, dark theme, RecycleView migration).

## Sequencing and Rationale

### 1. Technical Debts (first — every subsequent feature will be built on this)
- [x] Dark mode preference persistence — Written to `display.style` in `archlence_config.json`, read and restored on startup.
- [x] `tests.test_ids` fix — Added `active_category_type = StringProperty("income")` to `IdsApp`, stub contract completed. Visual/headless verification also done on a real OpenGL window using TCP-Xvfb — KV/OpenGL smoke test passed.
- [x] `ui/charts.py` chart colors (axis, grid, label, empty-data ring) adapted to the theme + re-drawing trend/pie/bar charts preserving data upon theme change. Income/expense and category colors were intentionally kept untouched since they are semantic.

**Verification:** Python syntax checks passed.

**SavingsService test failures — resolved:**
- [x] Test balance set to 10,000 TRY, original balance restored at the end of each test. Result: SavingsService 6/6, full suite 120/120 green, `git diff --check` clean.

**Item 1 — COMPLETED.**

### 2. Statistical Features (share the same infrastructure, must be done together)
- [x] Automatic subscription radar — Statistical detection of recurring transactions, surfacing "silent leak" candidates, candidate tracking, and persistent dismissal flow.
- [x] Statistical anomaly detection — Z-score based spending deviation alerts and home page cards.
- [x] Encrypted `amount`/`description` fields are deciphered and calculated in Python, not aggregated in SQL.
- [x] Service layer tested with tolerance, irregular intervals, thresholds, and persistence scenarios.

**Item 2 — COMPLETED (V1 Core).**

Improvement decisions:
- [x] Automatic tracking of weekly, bi-weekly, and quarterly candidates. The maturity engine supports `weekly`, `biweekly`, `monthly`, `quarterly`, and `yearly` periods; handles end-of-month and leap year boundaries. Unknown periods are rejected rather than silently assumed monthly.
- [x] Persistent "I SAW IT" flow for anomalies and `anomaly_dismissals` migration. Dismissal is applied idempotently with the transaction ID and the same anomaly is filtered out on subsequent dashboard refreshes.

### 3. Financial Health Score
- [x] Weighted score calculation from savings rate, debt ratio, and volatility components.
- [x] Displaying the current score on the home page card.
- [x] Storing score history in the `financial_health_history` table and reading it with `get_health_history(limit=30)`.
- [x] Same-day dashboard refreshes update the daily log instead of producing a new row; old same-day duplicates reduced to a single record during migration.

**Item 3 — COMPLETED.**

**Card fix (2026-07-23, separate session):** The user pointed out the curved sparkline under the card had no function; removed. In the same session, a misleading data integrity issue was fixed where the neutral `50.0` default returned by `_score_savings_rate`/`_score_debt_ratio`/`_score_volatility` when there was no actual data (`total_income <= 0 and total_expense <= 0`) was shown on the screen as if it were a real "50/Average" rating.

- [x] Sparkline and empty-history label removed from `ui/dashboard.kv`, card height 212dp → 150dp. The `HealthScoreSparkline` class (`ui/charts.py:310`) and `get_health_history(limit=30)` preserved for future use.
- [x] `insufficient_data` threshold: `total_income <= 0 and total_expense <= 0` (only if there is no actual income/expense in the lookback window). A stricter transaction/day count threshold was deliberately not chosen — unilateral income/expense is also real data, doesn't unnecessarily block users with little data, and prevents confusing a user who legitimately scores 50 with a "no data" state.
- [x] In insufficient data state, `compute_financial_health_score` now returns `{"score": None, "breakdown": {}, "computed_at": ..., "insufficient_data": True}` and does not write to the history table. UI: score "--", label "Not Enough Data", description "Not enough data to calculate a score yet. Add a few transactions and it will appear here.", progress bar hidden.
- [x] Changed files: `services/insights_service.py:473`, `mixins/insights_mixin.py:139`, `ui/dashboard.kv:598`, `ui/i18n.py`, `main.py`, `tests/test_insights_service.py`, `tests/test_insights_mixin.py`.
- [x] Verification: 126/126 tests green, `compileall` passed, `git diff --check` clean. Real SDL2/OpenGL verification: "--"/"Not Enough Data" on a transaction-less profile, score 90/"Very Good" on real data; no `health_trend_chart` ID on either screen.

### 4. Balance Time Machine (point-in-time history & diff)
- [x] Past snapshot/replay model using `daily_balance_snapshot` + `balance_events` ledger; migration guard and missing ledger healing/backfill.
- [x] Fast 30-day diff view and custom date range comparison with two date pickers.
- [x] Point-in-time view showing end-of-day total balance, total savings, and calculation source (`snapshot`/`replay`) by selecting a single date.
- [x] Explicit "no records" state for dates before the start of the ledger, avoiding misleading zeros.

**Item 4 — COMPLETED.**

### 5. What-if Scenario Sandbox (most abstract, last)
- [x] Movement of the RK4 (4th-order Runge-Kutta) wealth projection engine to a Kivy-independent `services/projection_service.py` layer; daily series and backward-compatible final value APIs.
- [x] Baseline + what-if simulation with income/expense percentage change, 30/90/365-day horizon, and signed one-off income/expense parameters.
- [x] What-If Sandbox dialog in the Tools tab, multi-series comparison chart, and final difference/negative wealth warning against the baseline scenario.
- [x] Analytical solution comparison, delta application, negative scenario, 365-day stability, and headless mixin data-flow tests.

**Item 5 — COMPLETED.** Visual verification: What-If Sandbox, Balance History, and MDDatePicker flows tested on a real OpenGL window via TCP-Xvfb (screenshots: `archlence_scenario_smoke0003.png`, `archlence_history_smoke0004.png`, `archlence_datepicker_smoke0002.png`). Also in this session, an `ast.Str` incompatibility crashing `MDDatePicker` on Python 3.14 was resolved, date picker texts linked to the TR/EN system, and the What-If dialog was made compact to fit an 800×600 screen.

**Environment note:** To permanently fix standard `xvfb-run` usage (bypassed with TCP-Xvfb alternative in this session), `/tmp/.X11-unix` ownership/permissions need to be fixed — run once in your own terminal if you wish: `sudo chown root:root /tmp/.X11-unix && sudo chmod 1777 /tmp/.X11-unix`.

### 6. Packaging / Distribution (after product freeze)

**Scope decision: V1.0 targets Windows + Linux only. Mac is out of scope** (decision date: today) — `.dmg`/notarization tasks removed from this list until decided separately.

**Windows — to be completed via existing `archlence.spec` + `.github/workflows/build-windows.yml` (2026-07-23 audit report):**
- [x] Application icon — Multi-sized `assets/icon.ico` (16/32/48/64/128/256px) and `assets/icon.png` (1024×1024 RGBA) generated, linked in spec (`archlence.spec:67`).
- [~] Post-build smoke test — step WRITTEN 2026-07-29 (`build-windows.yml`, launches `Archlence.exe`, checks it's still alive after 10s and that `crash.log` didn't grow) but **NOT YET VERIFIED** — PyInstaller can't cross-compile, this repo's dev session had no Windows machine and no Linux-side way to run a real `.exe`, so the step's correctness (including whether `KIVY_GL_BACKEND=angle_sdl2` is actually needed/sufficient at *runtime*, not just at PyInstaller's analysis step) has only been reasoned from existing comments, never observed. Only a real run on `windows-latest` (push/PR triggers it) proves it; don't upgrade this to `[x]` until a CI run has actually gone green with this step present.
- [x] Python version consistency — **decided and locked 2026-07-29**: Python 3.12 for all packaging CI (Windows + Linux), deliberately behind local dev's 3.14.6, to avoid untested binary/DLL risk with Kivy+PyInstaller. Documented directly in `build-windows.yml`/`build-linux.yml` next to the `setup-python` step.
- [ ] Version/naming — still missing. No Git tag, artifact comes out with a static `Archlence-Windows` name.
- [~] Code signing — not implemented but consciously documented as non-mandatory and deferred for V1.0.
- [~] Installer wizard (Inno Setup/NSIS) — undefined but documented as a separate out-of-V1.0 decision.

**Linux — built 2026-07-29 (separate session):**
- [x] `archlence.spec` — platform-branched on `IS_WINDOWS = sys.platform.startswith("win")`: `kivy_deps` (sdl2/glew/angle) import, the ANGLE `KIVY_GL_BACKEND`, `EXE(icon=...)`, and the `Tree()` DLL bundling are all Windows-only now; Linux build carries none of them.
- [x] `.github/workflows/build-linux.yml` — mirrors `build-windows.yml`'s trigger/concurrency pattern on `ubuntu-latest`. Key finding: `collect_all("kivymd")` forces a real Kivy Window/GL context during the PyInstaller analysis step (same root cause as the Windows ANGLE requirement) — SDL's "dummy" video driver (the test suite's headless trick) does NOT satisfy this, it provides no GL surface at all. Fixed with `xvfb-run` (real virtual X11 display, Mesa llvmpipe software GL) instead.
- [x] `assets/archlence.desktop` — standard freedesktop entry, passes `desktop-file-validate`.
- [x] `installer/appimage/AppRun` — layout-agnostic wrapper script that execs the onedir's inner binary directly, so it doesn't care whether PyInstaller nests output under `_internal/` or not (version-dependent).
- [x] End-to-end verified on a real Linux machine (not just written blind): `xvfb-run -a pyinstaller archlence.spec` → `dist/Archlence/Archlence` (ELF 64-bit, ~290 MB onedir) → AppDir assembled → `appimagetool --appimage-extract-and-run` → `Archlence-x86_64.AppImage` (~114 MB), valid ELF PIE executable. Full test suite re-run after: 463/463 green, no regressions.
- [ ] Python version consistency (local 3.14.6 vs CI 3.12) — still open, deliberately not decided here; `build-linux.yml` only matches `build-windows.yml`'s existing CI pin (3.12) for CI-to-CI consistency, not a resolution of the local/CI question.
- [ ] Not yet done: actually running the produced AppImage to confirm it launches/looks right. Recommend the user double-click/run the AppImage themselves once, the normal way, before trusting it fully.

**Rename audit:** A scan excluding out-of-scope folders found zero remaining "Finora" references. The project folder name (`Documents/finora`) and `graphify-out/` cache were consciously left unchanged per instructions (the cache should be deleted and regenerated later).

## Security — Local PIN System (2026-07-23, separate session)

While investigating a GUI omission noted by the user ("no sign up, create account button is non-functional"), a much more serious security flaw was discovered: the login screen used a STATIC, hardcoded `ADMIN_HASH` (same across all installs) and an unsalted SHA-256; additionally, there was a literal `"admin_secret"` backdoor password completely bypassing the hash check in `main.py::check_login`. These were completely removed.

- [x] Real local PIN system established: `pin_setup` screen on first boot, 4-12 digit PIN + repeat, 128-bit random salt per install via `secrets.token_hex(16)`, timing-attack-resistant comparison with `hmac.compare_digest`. Plain PIN is never written anywhere.
- [x] Static `ADMIN_HASH` and literal `"admin_secret"` backdoor completely removed (`security/security_service.py:14`, `main.py:1155`).
- [x] Non-functional "create account" button and the whole email-based "forgot password" flow (`ui/dashboard.kv`) removed — conceptually meaningless anyway in a local-first architecture. Username field also removed (unnecessary in a single-user app).
- [x] PIN recovery path: Added "Reset PIN and Data" to the Settings menu accessible before login — clears PIN/salt, all user tables, saved card number/EXP/CVC fields, and transaction/asset/debt/goal/history/insight records (preserves language/theme preference), then redirects back to `pin_setup`.
- [x] Hidden `screens/admin_screen.py` panel completely removed — rationale: its functions (CSV export, reset) were already more completely available in Settings, plus the admin panel was exporting encrypted fields RAW (unlike the properly decrypted export in Settings), and it completely lacked an authorization model to protect it.
- [x] Verification: 125/125 tests green (including 4 new security tests — different hash with different salt, wrong PIN rejection, 128-bit salt generation), real SDL2 window visually verified for first setup/re-login/wrong PIN/reset flows, old backdoor/screen scan: 0 matches.

## Budget Planner — Comprehensive Update (2026-07-24, separate session)

The "Monthly Budget Plan" was transformed from a simple planned income/expense ledger into a real budget TRACKING tool: month/year separation, category-based actuals tracking, fixed/variable expense separation, rollover balance, threshold-based alerts, automatic suggestions, templates, and a trend chart were added.

- [x] **Critical real bug fixed**: `monthly_budget_plan` table lacked a `target_year` column completely; although `calculate_monthly_budget` took a year parameter, the query only filtered by `target_month` — January 2026 and January 2027 plans were mixing up as the same records. Added `target_year` into `database/init_db.py:72`, backfilled old records with the current year, all queries now use `WHERE target_month = ? AND target_year = ?`. Verified in tests that writing different plans for the same month in 2026/2027 yields completely separate results.
- [x] Schema also expanded with `category_name`, `rollover_enabled`, `is_template`, `alert_threshold_pct` columns (`database/init_db.py:72`) — migration is re-runnable and backward compatible.
- [x] Category-based actual tracking: plan items are linked to the real `categories` table with a searchable picker ("Enter free text" path also preserved), planned/actual/percentage/remaining are calculated in `services/budget_service.py:40`, encrypted amounts deciphered in Python, not SQL. Progress bars shown with green/orange/red thresholds (`mixins/budget_mixin.py:30`).
- [x] Fixed/variable expense split: active subscriptions shown in a read-only fixed expenses section, manually entered items in a separate "Planned Items" section.
- [x] Rollover balance/overspend: derived at calculation time using an unchained rollover logic relying only on the previous month, without retroactively altering past records.
- [x] Auto-suggestion engine: "SUGGEST" button populates the amount field on a background thread based on the average of the last three completed months.
- [x] Template ("auto-repeat every month"): mechanism established at the query level; editing it in a specific month creates an override for that month only, without breaking the template itself.
- [x] Trend chart: dialog showing the planned/actual series for the last six months, opened via the "History / Trend" button added to the budget card (`ui/dashboard.kv:738`).
- [x] Migration verification: real database (`finance.db`, 380 KB, 12 budget records) backed up before alteration (`db_backups/2026-07-24_budget_tracking/`), migration run on a temporary copy verifying 5 new columns added and 12 old records backfilled with `target_year=2026`; source database untouched.
- [x] Verification: Budget service 7/7, full suite **142/142** green, `compileall`/`git diff --check` clean. Category search, suggestion engine (200.00 TRY), progress percentages (50%/85%/100% → green/orange/red), read-only Netflix subscription, progress-bar-less "Emergency Fund" free text item, and six-point trend chart visually verified in a real SDL2/OpenGL window. No issues other than a previously known, harmless single `ResourceWarning: unclosed database`.

## Minimal Dashboard Architecture + Subscription Interceptor (2026-07-24, separate session)

The large "Monthly Budget Plan" card on the home page was moved to a minimal card architecture consistent with other tools in the user's Tools tab (Calculator, Interest Return, Compound Interest, etc.), opening when clicked like "Savings Goal". In the same session, an interceptor was established that automatically writes subscription-like expenses passing through the credit card to the "Active Subscriptions" radar.

- [x] Budget planner extracted from `ui/dashboard.kv` and defined as `<BudgetPlannerPanel@MDCard>` in `ui/tools.kv`; only the minimal `<BudgetSummaryCard@MDCard>` (`ui/dashboard.kv:904`, id: `budget_summary_card`) left on the home page — panel opens with "OPEN PLANNER". The panel's own `ids` dictionary is kept separate from `root.ids` (`mixins/budget_mixin.py`, see `_planner_ids()` contract).
- [x] Data bridge: changes in the planner (spent/limit) instantly reflect on the summary card; the summary card was also prevented from erroring out in a theme-less unit-test environment.
- [x] Subscription interceptor (`services/recurring_service.py`) — triggers only for expenses passing through a credit card with the subscription category (`SUBSCRIPTION_CATEGORIES`) or containing a recognized brand name; `register_subscription_from_transaction` writes idempotently to the `recurring_payments` table (does not re-add if same name exists). The manual "recurring payment" form was prevented from creating duplicates with the auto interceptor (interceptor works only with credit card signals).
- [x] Brand recognition list deliberately left empty: `services/recurring_service.py:40` — `KNOWN_BRANDS = []` — real brand dataset not yet populated (marked as "Pending Work" below).
- [x] TAB key focus chain established with `write_tab=False` + `focus_next` on PIN, account creation, and transaction forms; chain is re-established when dynamic recurring fields open and close (`mixins/transaction_mixin.py:260-275`).
- [x] Heavy budget form refreshes distributed to different frames using `Clock.schedule_once`, reducing UI freeze risks.
- [x] Verification: full suite including `tests/test_budget_mixin.py`, `tests/test_subscription_interceptor.py` **278/278** green (`xvfb-run -a .venv/bin/python -m unittest discover -s tests`).

**Pending Work (COMPLETED):**
- [x] `services/recurring_service.py:40` — Populating the `KNOWN_BRANDS` list with a real brand dataset (digital platform, software license, cloud storage, education, sports, donation, membership brands).
- [x] Completing the TR/EN i18n equivalents (`ui/i18n.py`) of placeholder texts for `BudgetSummaryCard`/`BudgetPlannerPanel` ("Monthly Budget", "Preparing budget plan...", "OPEN PLANNER" etc.).
- [x] Pure visual polish of `<BudgetSummaryCard@MDCard>` and `<BudgetPlannerPanel@MDCard>` in `ui/tools.kv` (color/contrast, padding/spacing, font size, progress bar thickness) — WITHOUT altering backend methods and widget IDs (`budget_planner_panel`, `budget_summary_card`, `budget_summary_text`, `budget_summary_bar`, `month_selector_container`, `projection_label`, `projection_icon`, `budget_detailed_list`).

## Performance, UI, and Budget Improvements (Recent Updates)
- [x] **Performance (Startup/Transactions):** VACUUM operation and cryptographic warmup moved off the main thread, resolving UI freezes during startup and transaction additions.
- [x] **Subscriptions:** Dead Clearbit logo API removed, more readable renewal texts added.
- [x] **Assets:** Opening balance is no longer shown as fake income; it now appears as its own distinct slice/series in charts (e.g., trend chart).
- [x] **Prices:** Fixed an issue where the first-ever data fetch was skipped if the market was closed.
- [x] **UI & Dialogs:** Live-tested fixes for currency layout, MDCard clicks, and calendar crash.
- [x] **Budget & Wallet:** Opening balance synchronization, plan confirmation, and save toasts added.

## Unpostponable / Unchanging Constraints
- Local-first architecture will be maintained: data will not leave the device, no cloud/3rd party servers.
- Changes touching the logic layer like `services/*`, `database/*` are considered major refactors, to be handled with separate care (see "Unchanging files" principle in ANTIGRAVITY_TASKS files).

## Quality and Performance Tracking
- [x] UI/mixin tests for `mixins/insights_mixin.py` — health score render (happy path, green/red band selection, error state) and dismiss-recurring-candidate action now covered (2026-07-29), on top of the existing add-to-subscription/anomaly-dismissal action tests. Found and fixed a real coverage gap in the process: the error-state test explicitly checks it's distinguishable from "insufficient data" (both used to look identical — same "--" score — before the 2026-07-23 insufficient-data fix). Still open: full candidate/anomaly CARD content assertions (brand icon presence, amount formatting inside the built widget tree) — only their empty-state renders are tested; would need richer kivymd stubs (FitImage/MDIcon are stubbed but untested with real data) or a `services.brand_icon_service` mocking pass.
- [ ] Measure insights refresh time when transaction volume reaches a few thousand. Not urgent yet as accounts run on a background thread; if necessary, cache results until a new transaction/change occurs.
- [x] `ResourceWarning: unclosed database` — resolved 2026-07-29. `main.py`'s
  dashboard-metrics / advice / change-rate paths were pairing
  `get_connection()` with a manual `conn.close()`, which is skipped if a query
  raises mid-block; they now use the existing `managed_connection()` context
  manager (`database/db.py`). Verified by re-running the whole suite under
  `python -W always::ResourceWarning`: **zero** occurrences remain (previously
  it repeated on most runs).

## Current Status Snapshot (2026-07-30 audit, re-verified)

Overall V1.0 vision completion estimate: **~95%**. Every claim below was checked
against the code at the time of writing, not carried over from an earlier pass.

- **Product scope (Items 1-5, security, budget planner overhaul, minimal
  dashboard/subscription interceptor, Pending Work brand list/i18n/polish):
  done.**
- **Packaging (Item 6): now largely done, both platforms.** Windows: post-build
  smoke test added and observed green on a real `windows-latest` run; Python
  3.12 locked as the deliberate packaging target. Linux: `build-linux.yml`,
  `assets/archlence.desktop`, `installer/appimage/AppRun`, and a
  platform-branched `archlence.spec` — the resulting AppImage was built, run,
  and confirmed launching on a real Linux desktop.
- **The two bugs the previous snapshot listed as open are both fixed** (that
  snapshot was written before the fixes landed and should not be trusted as
  current):
  1. The Tools-tab budget card is a 140dp grid tile like the other tool cards
     (`ui/dashboard.kv`, `id: budget_tool_card`), not a full-width panel.
  2. The yfinance price worker no longer swallows failures — it captures
     `stdout`/`stderr` via `PIPE` and prints the reason on a non-zero exit
     (`services/asset_service.py`). The original silent `DEVNULL` was in fact
     hiding a real `ModuleNotFoundError`.
- **Quality tracking: 2 of 3 done** (insights_mixin render/error-state tests;
  `ResourceWarning` eliminated). One open, non-blocking: measuring insights
  refresh time at a few thousand transactions.

## Next Steps

Remaining before a public V1.0, in order:

1. **Cut the first tagged release.** The release plumbing exists
   (`.github/workflows/release.yml`: pushing a `v*` tag publishes a GitHub
   Release with `ArchlenceSetup.exe` and the Linux `.AppImage` attached, with
   the installer version derived from the tag). What's left is the human
   decision to push `v1.0.0` — CI artifacts alone are login-only and expire,
   so a Release is what actually gives end users a permanent download link.
2. Measure insights refresh time at scale (quality tracking, non-blocking).
3. Code signing and an installer wizard remain consciously deferred
   out-of-V1.0 decisions (see the Windows list above).
