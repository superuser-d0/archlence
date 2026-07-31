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
  <a href="https://github.com/superuser-d0/archlence/releases/tag/v0.0.2"><img alt="Current release" src="https://img.shields.io/badge/release-v0.0.2-blue"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-pre--release-orange">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
</p>

![Archlence dashboard](docs/screenshots/dashboard.png)

> All screenshots use generated sample data. No real financial information is included.

## About Archlence

Personal finance data should remain useful without becoming somebody else's dataset.

Archlence is an independently maintained, local-first desktop application for personal finance, cash-flow analysis, recurring payments, debt tracking, credit cards, and portfolio monitoring.

The repository is public to support transparent development, technical review, and future community contributions. Archlence is still under active development and should not yet be considered production-ready financial infrastructure.

The current public release is **[v0.0.2](https://github.com/superuser-d0/archlence/releases/tag/v0.0.2)**. It is a pre-release focused on Windows reliability, safe local-data handling, and cross-platform test coverage.

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

Archlence v0.0.2 is a **pre-release**. It is not stable and is not
recommended for day-to-day finance tracking yet.

The package installs and runs, and the flows listed in the changelog are
covered by tests, but the 0.0.x line exists precisely to signal that the app is
still being shaken out against real usage. See CHANGELOG.md for what is covered
and what is still known-broken before trusting it with real data.

The current focus is:

- broader packaged-app validation of OS-keystore and recovery behavior;
- completing the migration of remaining financial calculation paths to the shared `Decimal` policy;
- stabilizing credit-card and recurring-payment workflows;
- expanding automated and regression test coverage;
- reducing broad exception and UI-layer responsibility debt;
- making the project easier for outside contributors to understand and extend.

Some workflows, interface elements, sample-data states, and security components are still being refined.

See [Vision and scope](docs/VISION.md) for what "stable" is meant to signal
and the platform/versioning decisions behind the current 0.0.x line, and the
single current [Security and reliability status](docs/SECURITY_RELIABILITY_STATUS.md)
for the exact guarantees and limitations. Dated audit documents are archived
baselines, not current status.

## Known limitations

The following areas are actively being improved:

- packaged OS-keystore and recovery coverage across more real Windows and Linux configurations; Windows DPAPI and Linux Secret Service/KWallet are supported, with a permission-restricted local-file fallback when no OS keystore is available;
- migration of the remaining financial calculation paths to the shared `Decimal` policy;
- code signing — both packages are unsigned, so Windows SmartScreen warns on
  first run; the Linux AppImage is unsigned too;
- the packaged builds are verified in CI (install, launch, upgrade-from-the-
  previous-release, and uninstall, on real `windows-latest`/`ubuntu-latest`
  runners) and on the maintainer's own Linux machine, but real-hardware
  confirmation on a range of actual Windows installations is still limited;
- consistency of sample-data presentation;
- selected credit-card and recurring-payment flows;
- some loading, localization, and UI edge cases;
- broader contributor and architecture documentation.

Known limitations are tracked openly so that progress can be reviewed over time.

## Getting started

### Recommended: install the packaged release

The current public build is the **v0.0.2 pre-release**. Download packages only
from the [official v0.0.2 release](https://github.com/superuser-d0/archlence/releases/tag/v0.0.2).
The packaged applications include Python and their runtime dependencies; you do
not need to install Python, Kivy, or SDL separately.

#### Windows installer

1. Download [`ArchlenceSetup-0.0.2.exe`](https://github.com/superuser-d0/archlence/releases/download/v0.0.2/ArchlenceSetup-0.0.2.exe).
2. Optionally verify its SHA-256 checksum as shown below.
3. Double-click the installer. It installs for the current user under
   `%LOCALAPPDATA%\Programs\Archlence` and does not require administrator
   privileges.
4. Launch Archlence from the Start menu. A desktop shortcut is optional in the
   installer.

The installer is unsigned, so Windows SmartScreen may show an "unrecognized
app" warning. Verify the checksum before choosing **More info → Run anyway**.

```powershell
$actual = (Get-FileHash .\ArchlenceSetup-0.0.2.exe -Algorithm SHA256).Hash
$expected = "42ff88d1366682497ca850b8ead885e60e05a1c0b0ba0b665c40d5f62f54983e"
if ($actual -ne $expected) { throw "Checksum verification failed" }
"Checksum verified"
```

Upgrading or uninstalling the application does not intentionally remove the
user database. Keep a verified backup before upgrading or uninstalling anyway.

#### Linux AppImage

1. Download [`Archlence-0.0.2-x86_64.AppImage`](https://github.com/superuser-d0/archlence/releases/download/v0.0.2/Archlence-0.0.2-x86_64.AppImage)
   and [`SHA256SUMS.txt`](https://github.com/superuser-d0/archlence/releases/download/v0.0.2/SHA256SUMS.txt)
   into the same directory.
2. Verify the AppImage and make it executable:

```bash
grep ' Archlence-0.0.2-x86_64.AppImage$' SHA256SUMS.txt | sha256sum -c -
chmod +x Archlence-0.0.2-x86_64.AppImage
./Archlence-0.0.2-x86_64.AppImage
```

The AppImage is built for 64-bit x86 Linux and bundles its application runtime,
so no separate Python or SDL installation is required. It is not code-signed;
the expected SHA-256 is
`31de4e4ce0b4730de9aa5afbd361b4a8e46085c727d5052c818a444bcb344935`.

There is currently no packaged macOS release.

### Run from source

Source installations are intended for development and testing. Requirements:

- Python 3.11 or newer (CI uses Python 3.12)
- Git
- a Kivy-compatible desktop/OpenGL environment

Clone the repository and create an isolated environment:

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
python -m venv .venv
```

Activate it on Linux or macOS and install the pinned runtime dependencies:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-runtime.txt
python main.py
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-runtime.txt
python main.py
```

When running from source on Linux, Kivy uses system SDL/OpenGL libraries. Install
the matching packages before installing Python dependencies:

```bash
# Arch, CachyOS, Manjaro
sudo pacman -S --needed sdl2-compat sdl2_image sdl2_ttf sdl2_mixer libglvnd

# Debian, Ubuntu, Linux Mint
sudo apt install libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libsdl2-mixer-2.0-0 libgl1

# Fedora
sudo dnf install SDL2 SDL2_image SDL2_ttf SDL2_mixer mesa-libGL
```

For tests, lint, and type checking, install the development environment instead.
The complete test command is shown below; the exact lint/type-check gates live
in [the CI workflow](.github/workflows/tests.yml).

```bash
python -m pip install -r requirements.txt
python run_tests.py
```

On first launch, Archlence guides you through creating a local PIN and setting up your first account.

### Release verification and development artifacts

The v0.0.2 release also includes `SHA256SUMS.txt`, the CycloneDX SBOM
`Archlence-0.0.2-sbom.cdx.json`, and `THIRD_PARTY_NOTICES.md`. Checksums are
useful for detecting an incomplete or altered download, but they are not a
substitute for package signing when obtained from the same unsigned release.

Untagged builds of `main` are also produced on every push, but only as GitHub
Actions artifacts ([Windows](https://github.com/superuser-d0/archlence/actions/workflows/build-windows.yml),
[Linux](https://github.com/superuser-d0/archlence/actions/workflows/build-linux.yml)).
Those require a signed-in GitHub account to download and expire after 90 days,
so they're intended for development and testing rather than general use.

## Changelog

### 0.0.2 — Windows console encoding and instance-lock crash fixes

- Turkish error text no longer crashes the process on a legacy Windows
  console (a transaction could be silently lost when the subscription
  radar failed mid-write).
- The single-instance lock no longer risks crashing on shutdown on Windows.
- The test suite now runs on Windows in CI, not just Linux — both fixes
  above were only reachable because of that.

### 0.0.1 — pre-release: input correctness and UI responsiveness

- Amount field no longer scrambles typed digits (it recorded wrong values).
- Calendar, monthly budget, category settings and transaction-add no longer
  stall the UI; rapid taps coalesce instead of doing linear work per tap.
- Asset purchases pick an account that can actually fund them.
- Test reporting restored: the runner's output was being swallowed by Kivy.

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
  per install — not a value shared across installs. Windows protects the key
  with DPAPI; Linux uses Secret Service/KWallet when available. Settings
  explicitly warns when a 0600 local-file fallback is active;
- legacy CBC records are moved only through the user-controlled, backup-first
  transactional migration flow;
- application backups contain the database and password-protected recovery
  material together. A database copy without its matching key is not enough;
- settings, local databases, and runtime data are excluded from Git by default;
- the application does not include analytics or advertising trackers;
- CSV export provides a human-readable way to move supported records elsewhere;
- portfolio price refreshes and some visual metadata features may contact external public data sources;
- core financial records remain local and are not intentionally uploaded by those features.

Keep regular verified backups and store each recovery password separately.
Losing both the active key and recovery material makes encrypted data
unrecoverable. See [key management](docs/KEY_MANAGEMENT.md) and
[backup/recovery](docs/BACKUP_RECOVERY.md).

Archlence is a personal finance management tool. It is not a bank, brokerage service, accounting platform, or source of financial advice.

## Roadmap

- Broader hardware-backed key-store coverage and recovery UX
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
