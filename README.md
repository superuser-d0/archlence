# Archlence

<p align="center">
  <strong>A local-first personal finance, cash-flow, and portfolio dashboard.</strong>
</p>

<p align="center">
  Track accounts, transactions, subscriptions, debts, credit cards, and investments from a privacy-focused desktop application.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Kivy" src="https://img.shields.io/badge/UI-Kivy%20%2F%20KivyMD-5C3EE8">
  <img alt="SQLite" src="https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-unittest-brightgreen">
  <img alt="Privacy" src="https://img.shields.io/badge/privacy-local--first-00A896">
  <img alt="Status" src="https://img.shields.io/badge/status-active%20development-orange">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
</p>

![Archlence dashboard](docs/screenshots/dashboard.png)

> All screenshots use generated sample data. No real financial information is included.

## About Archlence

Personal finance data should remain useful without becoming somebody else's dataset.

Archlence is an independently maintained, local-first desktop application for personal finance, cash-flow analysis, recurring payments, debt tracking, credit cards, and portfolio monitoring.

The repository is public to support transparent development, technical review, and future community contributions. Archlence is still under active development and should not yet be considered production-ready financial infrastructure.

## Why Archlence?

- **One financial overview:** balances, income, expenses, debts, subscriptions, cards, and investments in one interface.
- **Local-first storage:** core financial records are stored in a local SQLite database.
- **Actionable insights:** financial health scoring, cash-flow projections, and unusual-spending detection.
- **Automated routines:** recurring-payment tracking, subscription detection, and scheduled deductions.
- **Portfolio awareness:** stocks, cryptocurrencies, precious metals, and foreign currencies with background price refreshes.
- **Desktop-focused experience:** Turkish and English interface options with dark and light modes.
- **Open development:** technical debt, security work, and incomplete areas are documented rather than hidden.

## Application overview

### Dashboard and financial health

The dashboard combines current balance, period comparisons, a trend-based month-end balance forecast with actionable recommendations, a financial health score, active subscriptions, upcoming obligations, and recent activity.


### Portfolio overview

Review income, expenses, allocation, balance trends, and active positions from a unified portfolio workspace.

![Portfolio overview](docs/screenshots/portfolio-overview.png)

Price refreshes run outside the main UI path and use asset-aware caching to keep navigation responsive while avoiding unnecessary requests.

### Asset history

Track historical buy and sell activity, review transaction-level outcomes, and preserve the timeline behind portfolio decisions.

![Asset history](docs/screenshots/asset-history.png)

### Accounts and credit cards

Archlence supports cash and checking accounts as well as credit cards.

Card views expose available limits, current debt, statement access, payment actions, and local card controls.

![Accounts and credit cards](docs/screenshots/mycards.png)

### Subscriptions and recurring-payment detection

Review active subscriptions, upcoming renewal dates, monthly costs, and recurring-payment candidates detected from transaction history.

![Subscriptions and recurring-payment detection](docs/screenshots/subscriptions.png)

### Insights, debts, and upcoming payments

Archlence highlights unusual spending, tracks active debts and installment progress, and keeps upcoming automatic payments visible from the same workflow.

![Insights, debts, and upcoming payments](docs/screenshots/debts-and-payments.png)

### Financial planning tools

The tools workspace includes monthly budgets, a calendar, general and compound-interest calculators, loan planning, savings goals, what-if scenarios, and local data operations.

The calendar is a month grid that marks the days carrying activity; selecting a day lists that day's transactions with their times and signed amounts.

![Financial tools](docs/screenshots/financial-tools.png)

### Personalization and privacy controls

Choose Turkish or English, switch between light and dark appearances, manage categories, review balance history, and access local privacy controls.

![Settings](docs/screenshots/settings.png)

## Core capabilities

| Area | Capabilities |
| --- | --- |
| Dashboard | Period summaries, balance trends, projections, health score, subscriptions, debts, and recent activity |
| Transactions | Income and expense entry, categories, dates, pending items, recurring entries, and installments |
| Subscriptions | Detection radar, recurring schedules, automatic deductions, updates, and cancellation |
| Budgeting | Monthly plans, category allocations, recurring-payment reservations, and trend review |
| Accounts | Cash and checking accounts, balances, and account-based transaction tracking |
| Credit cards | Limits, current debt, statements, payment actions, and local card controls |
| Investments | Multi-asset portfolio, price refreshes, profit/loss calculations, and asset history |
| Debt and savings | Debt progress, installment tracking, upcoming payments, and savings goals |
| Data portability | CSV import and export for supported financial records |
| Experience | Turkish and English localization, dark and light modes, and desktop-oriented navigation |

## Architecture

Archlence separates interface, application workflows, business rules, and persistence concerns:

```text
main.py
├── ui/          Kivy layouts, reusable components, charts, themes, and i18n
├── mixins/      Application workflows and screen behavior
├── services/    Transactions, accounts, cards, pricing, insights, and projections
├── database/    SQLite schema, migrations, and ledger primitives
├── security/    Local access-control and security services
├── utils/       Formatting, currency, cryptography, and ticker helpers
└── tests/       Unit, integration, and GUI-oriented regression tests
```

Notable implementation details include:

- atomic balance updates and ledger events;
- `SAVEPOINT`-backed settlement for due transactions;
- SQLite migration guards for existing installations;
- asynchronous asset-price workers with dynamic cache lifetimes;
- AEAD (AES-256-GCM) field-level encryption with a random per-install key for newly written sensitive values, with backward-compatible reads for records still in the previous format;
- daily balance snapshots and event replay for historical balances.

## Project status

Archlence is an early-stage open-source desktop application under active development.

The current focus is:

- OS-keystore-backed key storage and migrating records still using the previous encryption scheme;
- stabilizing credit-card and recurring-payment workflows;
- expanding automated and regression test coverage;
- documenting architectural decisions;
- making the project easier for outside contributors to understand and extend.

Some workflows, interface elements, sample-data states, and security components are still being refined.

Archlence should not yet be treated as production financial infrastructure.

## Known limitations

The following areas are actively being improved:

- OS-keystore-backed key storage (currently a random key generated per install, stored in a local file) and migrating records still using the previous encryption scheme;
- code signing — both packages are unsigned, so Windows SmartScreen warns on
  first run; the Linux AppImage is unsigned too;
- the packaged builds have been verified in CI, on the maintainer's own Linux
  machine, and on a second Windows machine — but that is still a small sample
  rather than a broad range of real installations;
- consistency of sample-data presentation;
- selected credit-card and recurring-payment flows;
- some loading, localization, and UI edge cases;
- broader contributor and architecture documentation.

Known limitations are tracked openly so that progress can be reviewed over time.

## Getting started

### Requirements

- Python 3.11 or newer (verified on 3.14; CI packages with 3.12)
- A desktop environment supported by Kivy
- Git

On Linux, Kivy's wheels link against the system SDL2 libraries rather than
bundling their own, so those have to be present before `pip install`. Install
them with your distribution's package manager first:

```bash
# Arch, CachyOS, Manjaro and other Arch-based distributions
sudo pacman -S --needed sdl2-compat sdl2_image sdl2_ttf sdl2_mixer libglvnd
```

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libsdl2-mixer-2.0-0 libgl1
```

```bash
# Fedora
sudo dnf install SDL2 SDL2_image SDL2_ttf SDL2_mixer mesa-libGL
```

On Arch-based systems the SDL2 package is named `sdl2-compat` (it replaced the
older `sdl2` package and provides the same `libSDL2-2.0.so.0`).

### Installation

Clone the repository:

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies and start the application:

```bash
python -m pip install --upgrade pip
pip install -r requirements-runtime.txt
python main.py
```

`requirements-runtime.txt` is everything the app itself needs — nothing more.
If you also want to run lint locally (`flake8`), install
`requirements-dev.txt` too, or use the `requirements.txt` umbrella, which
installs both:

```bash
pip install -r requirements.txt
```

On first launch, Archlence guides you through creating a local PIN and setting up your first account.

### Pre-built downloads

If you'd rather not build from source, tagged releases ship ready-to-run
packages for both platforms on the
[Releases page](https://github.com/superuser-d0/archlence/releases).

**Windows** — download `ArchlenceSetup-<version>.exe` and double-click it. It
installs per-user (no admin rights required) and doesn't touch any existing
Archlence data.

**Linux** — download `Archlence-<version>-x86_64.AppImage` and make it
executable. No installation step, and no system SDL2 packages needed: the
AppImage bundles everything.

```bash
chmod +x Archlence-<version>-x86_64.AppImage
./Archlence-<version>-x86_64.AppImage
```

The `chmod` is required because GitHub does not preserve the executable bit on
release assets.

Both packages are unsigned. On Windows, SmartScreen will show an "unrecognized
app" warning on first run — this is expected for an app without a paid
code-signing certificate, not a sign of tampering; choose "More info" → "Run
anyway" to proceed.

Untagged builds of `main` are also produced on every push, but only as GitHub
Actions artifacts ([Windows](https://github.com/superuser-d0/archlence/actions/workflows/build-windows.yml),
[Linux](https://github.com/superuser-d0/archlence/actions/workflows/build-linux.yml)).
Those require a signed-in GitHub account to download and expire after 90 days,
so they're intended for development and testing rather than general use.

## Changelog

Full history is on the [Releases page](https://github.com/superuser-d0/archlence/releases).

### 1.0.1 — card controls and live-language refresh

- Frozen cards/accounts now persist their state and reject new income, expense,
  installment, pending, recurring, and direct asset transactions. Debt payments
  remain available so a frozen credit card can still be paid down.
- The internet-shopping switch is now a persistent preference. Transactions do
  not currently identify their channel, so the UI explicitly avoids presenting
  this preference as an enforceable online-payment security control.
- Changing the language refreshes the open screen and bottom-navigation labels
  immediately.
- The time-bucket regression test is deterministic, and obsolete/dangerous
  development helpers have been removed or moved under `scripts/dev/`.

### 1.0.0 — first stable release

**Identical code to 0.9.0** — this release carries no functional changes, only
this changelog entry. It exists because the one thing 0.9.0 was holding back
for has now happened: the packaged Windows installer was launched and checked
on a second, independent Windows machine, not just in CI and on the
maintainer's own hardware. That was the last open question about whether the
packaging actually works outside the environment that produced it.

Code signing remains deliberately out of scope, so first-run SmartScreen
warnings are still expected.

### 0.9.0 — first public pre-release

The first version distributed as a downloadable package rather than source only.

**Distribution**

- Linux packaging built from scratch: a single-file `.AppImage` that bundles its
  own SDL2 and needs no system packages, produced by a
  [CI workflow](.github/workflows/build-linux.yml) alongside a
  platform-branched PyInstaller spec, a freedesktop `.desktop` entry, and an
  `AppRun` launcher.
- Tagged releases now publish both packages automatically, with the installer
  version derived from the git tag.
- The Windows build verifies after packaging that `Archlence.exe` actually
  starts and stays running, and that it writes nothing to its crash log —
  previously a launch-time crash could ship undetected, which had already
  happened once.
- Packaging is pinned to Python 3.12 as a deliberate, documented decision.

**Features**

- Month-end balance forecast: at least three months of history are averaged and
  projected to the end of the current month, then turned into a plain-language
  recommendation. With less than roughly three months of data it says so
  instead of showing an unreliable number.
- A real calendar view — a month grid marking days with activity, and a
  per-day transaction list — replacing a date picker that only reported a count.
- Recurring income alongside recurring expenses, plus dashboard caching.

**Fixes**

- Every card in the Tools grid was silently unclickable. `MDCard`'s ripple
  effect does not carry Kivy's button behaviour, so the declared handlers never
  fired; this affected the budget planner, all five calculators, the what-if
  sandbox, and the reset-data action.
- Once those were wired up, each tap fired twice — the card grabs the touch, so
  Kivy delivers the release event through both normal propagation and the grab
  list — which opened every dialog in duplicate.
- Right-clicking or alt-tabbing painted red circles on the window: Kivy's mouse
  provider was emulating multi-touch and drawing its debug rings.
- The forecast card's text overflowed its fixed height and drew over its own
  heading once the longer forecast text landed.
- Toggling balance visibility ran a database query and decrypted rows on the UI
  thread on every click; the budget category search rebuilt its whole list on
  every keystroke.
- The calculator evaluated input with `eval()`; it now walks a restricted
  syntax tree instead.
- Income and expense rows in the budget planner are aligned to opposite sides,
  as intended.

**Brand**

- New app icon: a bold "A" on the brand blue, replacing a mark whose thin rays
  disappeared entirely below about 48 pixels.

## Tests

The repository includes automated coverage for the ledger, transactions, accounts, subscriptions, pricing, budgeting, history, projections, security, and UI contracts.

Run the complete test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

or the equivalent convenience wrapper (same discovery, verbose output, and
a correct non-zero exit code on failure — this is what CI runs):

```bash
python run_tests.py
```

GUI checks may require a virtual display on headless Linux:

```bash
xvfb-run -a python -m unittest tests.test_gui tests.test_ids
```

## Privacy and data

Archlence is designed around local data ownership:

- core financial records are stored locally in `finance.db`, in a
  per-OS user-data directory resolved via [`platformdirs`](https://github.com/tox-dev/platformdirs)
  (`utils/app_paths.py`) — not inside the application's own install
  folder, which is commonly read-only once packaged (e.g. under `Program
  Files` on Windows). On Linux this is `~/.local/share/Archlence/`
  (config JSON lives alongside it); cached, re-fetchable data (brand
  icons) goes to `~/.cache/Archlence/`; `crash.log` goes to
  `~/.local/state/Archlence/log/`. Windows and macOS use the
  corresponding OS-standard locations for each. Upgrading from an older
  version that stored these next to the application migrates them
  automatically on first launch;
- sensitive transaction fields (amounts, descriptions) are encrypted at rest
  with AES-256-GCM authenticated encryption, using a random key generated
  per install and stored locally — not a value shared across installs.
  Records written before this scheme was introduced remain readable
  through a backward-compatible path until they're naturally rewritten;
- settings, local databases, and runtime data are excluded from Git by default;
- the application does not include analytics or advertising trackers;
- CSV export provides a human-readable way to move supported records elsewhere;
- portfolio price refreshes and some visual metadata features may contact external public data sources;
- core financial records remain local and are not intentionally uploaded by those features.

Keep regular backups of your local database.

Archlence is a personal finance management tool. It is not a bank, brokerage service, accounting platform, or source of financial advice.

## Roadmap

- OS-keystore-backed key storage and migration of existing records to the newer encryption scheme
- Improved credit-card reliability and statement workflows
- More consistent recurring-payment detection and presentation
- Natural-language queries over local financial history
- Local receipt parsing and categorization
- Additional portfolio data sources and reporting options
- Code signing for the Windows installer and the Linux AppImage
- Contributor documentation and architecture decision records

## Contributing

Issues and pull requests are welcome.

The project is still evolving, so opening an issue before a large change is recommended.

For changes to financial logic, include tests that demonstrate balance, ledger, and transaction integrity before and after the operation.

For UI changes, screenshots or short screen recordings are helpful whenever possible.

Useful contribution areas currently include:

- security and key management;
- test coverage;
- packaging and release automation;
- localization;
- accessibility;
- documentation;
- UI edge cases and regression fixes.

## Security

Please do not publish sensitive personal or financial information in issues, screenshots, test fixtures, or pull requests.

For security-related findings, use a private GitHub security advisory when possible instead of creating a public issue.

## License

Archlence is licensed under the [MIT License](LICENSE).
