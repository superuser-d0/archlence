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
  <a href="https://github.com/superuser-d0/archlence/releases/tag/v0.0.4"><img alt="Current release" src="https://img.shields.io/badge/release-v0.0.4-blue"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-pre--release-orange">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
</p>

![Archlence dashboard](docs/screenshots/dashboard.png)

> All screenshots use generated sample data. No real financial information is included.

## About Archlence

Personal finance data should remain useful without becoming somebody else's dataset.

Archlence is an independently maintained, local-first desktop application for personal finance, cash-flow analysis, recurring payments, debt tracking, credit cards, and portfolio monitoring.

The repository is public to support transparent development, technical review, and future community contributions. Archlence is still under active development and should not yet be considered production-ready financial infrastructure.

The current public release is **[v0.0.4](https://github.com/superuser-d0/archlence/releases/tag/v0.0.4)**. It is a pre-release focused on intentional negative-balance support, brand-icon quality and performance, a virtualized subscriptions list, and routing previously-silent background failures into the log.

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

Archlence v0.0.4 is a **pre-release**. It is not stable and is not
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

## Installation

The current public build is the **v0.0.4 pre-release**. Use only the
[official release](https://github.com/superuser-d0/archlence/releases/tag/v0.0.4).

| Platform | Recommended method | Python required? | Desktop integration |
| --- | --- | --- | --- |
| Windows | Installer | No | Start menu; optional desktop shortcut |
| Arch, Manjaro, CachyOS | `makepkg -si` | No | Application menu, icon, terminal command |
| Other x86_64 Linux | AppImage | No | Portable application |
| macOS | Source only | Yes | No packaged release |

Choose one method below. Do not clone the repository when using the Windows
installer or portable AppImage.

### Windows

1. Download [`ArchlenceSetup-0.0.4.exe`](https://github.com/superuser-d0/archlence/releases/download/v0.0.4/ArchlenceSetup-0.0.4.exe).
2. Verify the checksum if desired:

   ```powershell
   $actual = (Get-FileHash .\ArchlenceSetup-0.0.4.exe -Algorithm SHA256).Hash
   $expected = "42ff88d1366682497ca850b8ead885e60e05a1c0b0ba0b665c40d5f62f54983e"
   if ($actual -ne $expected) { throw "Checksum verification failed" }
   ```

3. Run the installer and open Archlence from the Start menu.

The installer is per-user, requires no administrator privileges, and installs
under `%LOCALAPPDATA%\Programs\Archlence`. It is unsigned, so SmartScreen may
warn on first launch. Verify the checksum before selecting **More info → Run
anyway**.

### Arch Linux, Manjaro, and CachyOS

Build and install the `archlence-bin` package as a normal user:

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
makepkg -si
```

Do not run `makepkg` with `sudo`; it requests the administrator password only
for the final Pacman installation. The package installs the application menu
entry, system icon, `/usr/bin/archlence`, and the application under
`/opt/archlence`.

```bash
# Launch
archlence

# Inspect the installed package
pacman -Qi archlence-bin

# Remove the application (user data is retained)
sudo pacman -R archlence-bin
```

Until the package is published to the AUR, update from the existing clean
checkout whenever a new release is announced:

```bash
cd ~/archlence
git status
git pull --ff-only
makepkg -si
```

`archlence-bin` is not currently searchable on the AUR. Commit or stash local
changes before pulling.

### Other Linux distributions — AppImage

The AppImage supports x86_64 Debian, Ubuntu, Linux Mint, Fedora, Arch-based
distributions, and other compatible Linux systems. It does not support ARM.

1. Download [`Archlence-0.0.4-x86_64.AppImage`](https://github.com/superuser-d0/archlence/releases/download/v0.0.4/Archlence-0.0.4-x86_64.AppImage)
   and [`SHA256SUMS.txt`](https://github.com/superuser-d0/archlence/releases/download/v0.0.4/SHA256SUMS.txt).
2. Open a terminal in the download directory and run:

   ```bash
   grep ' Archlence-0.0.4-x86_64.AppImage$' SHA256SUMS.txt | sha256sum -c -
   chmod +x Archlence-0.0.4-x86_64.AppImage
   ./Archlence-0.0.4-x86_64.AppImage
   ```

If FUSE mounting fails, use:

```bash
./Archlence-0.0.4-x86_64.AppImage --appimage-extract-and-run
```

Expected SHA-256:
`31de4e4ce0b4730de9aa5afbd361b4a8e46085c727d5052c818a444bcb344935`.

### Run from source

Source setup is intended for development, macOS, or unreleased `main` code.
Use Python 3.11 or newer; CI and packaged builds use Python 3.12.

Install Linux system dependencies first:

```bash
# Debian, Ubuntu, Linux Mint
sudo apt update
sudo apt install git python3 python3-venv python3-pip \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libsdl2-mixer-2.0-0 libgl1

# Fedora
sudo dnf install git python3 python3-pip SDL2 SDL2_image SDL2_ttf SDL2_mixer mesa-libGL

# Arch, Manjaro, CachyOS
sudo pacman -S --needed git python python-pip sdl2-compat sdl2_image sdl2_ttf sdl2_mixer libglvnd
```

Clone and run without activating the virtual environment:

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-runtime.txt
.venv/bin/python main.py
```

On macOS, install `python@3.12` and Git with Homebrew, then replace `python3`
with `python3.12`. On Windows PowerShell, use:

```powershell
git clone https://github.com/superuser-d0/archlence.git
cd archlence
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-runtime.txt
.venv\Scripts\python.exe main.py
```

For development tools and tests:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_tests.py
```

Use `.venv\Scripts\python.exe` instead on Windows. Exact lint and type-check
commands live in [the CI workflow](.github/workflows/tests.yml).

### Troubleshooting

- **`destination path 'archlence' already exists`:** do not clone again. Run
  `cd ~/archlence`, inspect `git status`, then use `git pull --ff-only` when the
  tree is clean.
- **Fish reports `case builtin not inside of switch block`:** either avoid
  activation and use `.venv/bin/python` directly, or run
  `source .venv/bin/activate.fish`.
- **PowerShell blocks `Activate.ps1`:** activation is optional; use
  `.venv\Scripts\python.exe` directly.
- **AppImage reports a FUSE error:** use the `--appimage-extract-and-run`
  command shown above.

On first launch, Archlence guides you through creating a local PIN and first
account. Upgrading or uninstalling a package does not intentionally remove the
user database; keep a verified backup anyway.

### Release files

The release also contains `SHA256SUMS.txt`, the CycloneDX SBOM
`Archlence-0.0.4-sbom.cdx.json`, and `THIRD_PARTY_NOTICES.md`. Packages are
unsigned; checksums detect an incomplete or altered download but do not replace
code signing.

Untagged `main` builds are available as expiring GitHub Actions artifacts for
[Windows](https://github.com/superuser-d0/archlence/actions/workflows/build-windows.yml)
and [Linux](https://github.com/superuser-d0/archlence/actions/workflows/build-linux.yml).
They are development artifacts, not public releases.

## Changelog

### 0.0.4 — negative-balance support, brand-icon quality, virtualized lists

- Checking accounts, savings goals, and credit-card debt payments can now
  go negative on purpose; net worth math is unaffected.
- Brand-icon logos are sharper: a multi-provider fallback replaces the
  single-provider lookup, and every image is decoded and re-encoded as a
  real PNG instead of trusting the response's declared content type.
- The Active Subscriptions / Active Incomes cards are now virtualized
  (`RecycleView`); rendering cost no longer grows with subscription count.
- Background failures that used to `print()` to a console nobody sees in
  the packaged Windows build are now written to the rotating log file with
  a full traceback.
- See [CHANGELOG.md](CHANGELOG.md) for the full list, including known
  limitations.

### 0.0.3 — password policy, active-incomes card, Borsa Istanbul price fix

- Local sign-in now requires a password (minimum length, one uppercase
  letter, one special character) instead of a 4-digit PIN, with a
  Settings > Change Password flow.
- Recurring incomes now render in their own "Active Incomes" card instead
  of the subscriptions (expenses) card.
- Assets typed as "Hisse Senedi" resolve to their Borsa Istanbul ticker
  again and fetch a live price instead of showing ₺0.00.
- See [CHANGELOG.md](CHANGELOG.md) for the full list, including known
  limitations.

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
