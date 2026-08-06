# Archlence

<p align="center">
  <strong>A privacy-first, local-first desktop workspace for personal finance, cash flow, and portfolio tracking.</strong>
</p>

[![Latest release](https://img.shields.io/github/v/release/superuser-d0/archlence?include_prereleases)](https://github.com/superuser-d0/archlence/releases/latest)
[![Tests](https://github.com/superuser-d0/archlence/actions/workflows/tests.yml/badge.svg)](https://github.com/superuser-d0/archlence/actions/workflows/tests.yml)
[![License](https://img.shields.io/github/license/superuser-d0/archlence)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS%20source-5C3EE8)
![Status](https://img.shields.io/badge/status-pre--release-orange)

<p align="center">
  <a href="https://github.com/superuser-d0/archlence/releases/latest">Download</a> ·
  <a href="docs/">Documentation</a> ·
  <a href="CONTRIBUTING.md">Contribute</a> ·
  <a href="https://github.com/superuser-d0/archlence/issues">Report a bug</a>
</p>

> [!WARNING]
> Archlence is in active pre-release development. It is suitable for testing
> and development, but it is not yet recommended as the sole store for
> day-to-day financial records. Keep verified backups and review the
> [current limitations](#project-status) before using real data.

![Archlence dashboard](docs/screenshots/dashboard.png)

> All screenshots use generated sample data. No real financial information is
> included.

## About Archlence

Personal finance data should remain useful without becoming somebody else's
dataset.

Archlence is an independently developed local-first desktop application. It
brings accounts, cash flow, transactions, subscriptions, debts, credit cards,
and investments into one workspace built with Python, Kivy/KivyMD, and SQLite.

The repository is open for transparent development, technical review, and
future community contributions. Archlence remains an active pre-release.

### Latest release

The latest public release focuses on data integrity, packaged-app reliability,
CI enforcement, and dashboard performance.

See the [full changelog](CHANGELOG.md) and
[download the latest release](https://github.com/superuser-d0/archlence/releases/latest).

## Why Archlence?

- **Local-first ownership:** core financial records stay in a local SQLite
  database.
- **Privacy by design:** sensitive fields are encrypted at rest, with no
  analytics or advertising trackers.
- **Unified workspace:** accounts, cards, cash flow, recurring payments,
  debts, savings, and investments share one desktop interface.
- **Actionable insights:** projections, financial-health indicators, and
  unusual-spending analysis help turn records into decisions.
- **Desktop focus:** packaged Windows and Linux options avoid a browser-first
  workflow.
- **Turkish and English:** both interfaces are maintained in the application.
- **Transparent development:** limitations, technical debt, and release work
  are documented openly.

## Core capabilities

| Area | Current capabilities |
| --- | --- |
| Dashboard | Period summaries, balance trends, projections, health score, obligations, and recent activity |
| Transactions | Income and expenses, categories, dates, pending items, recurring entries, and installments |
| Accounts | Cash and checking balances with account-based transaction tracking |
| Credit cards | Limits, debt, statements, payment actions, and local card controls |
| Subscriptions | Detection candidates, recurring schedules, renewals, updates, and cancellation |
| Budgeting and planning | Monthly budgets, category allocations, calendars, scenarios, calculators, and projections |
| Investments | Stocks, cryptoassets, precious metals, currencies, price refreshes, and transaction history |
| Debt and savings | Debt progress, installments, upcoming payments, and savings goals |
| Data portability | CSV import and export for supported financial records |
| Localization and desktop experience | Turkish and English interfaces, light and dark themes, and desktop navigation |

## Screenshots

### Portfolio and asset history

Review allocation, balance trends, positions, and the transaction history
behind portfolio changes.

| Portfolio overview | Asset history |
| --- | --- |
| ![Portfolio overview](docs/screenshots/portfolio-overview.png) | ![Asset history](docs/screenshots/asset-history.png) |

### Accounts and recurring payments

Keep account and card state alongside subscriptions and upcoming renewals.

| Accounts and credit cards | Subscriptions |
| --- | --- |
| ![Accounts and credit cards](docs/screenshots/mycards.png) | ![Subscriptions](docs/screenshots/subscriptions.png) |

### Obligations and planning

Track debt and payment progress, then use budgets, calendars, calculators,
savings goals, and what-if tools for planning.

| Debts and payments | Financial tools |
| --- | --- |
| ![Debts and payments](docs/screenshots/debts-and-payments.png) | ![Financial tools](docs/screenshots/financial-tools.png) |

### Settings and privacy controls

Manage language, appearance, categories, balance history, backups, and local
data controls.

| Settings |
| --- |
| ![Settings](docs/screenshots/settings.png) |

## Quick installation

Archlence is currently distributed as a pre-release.

| Platform | Recommended package | Python required |
| --- | --- | --- |
| Windows | Per-user installer | No |
| Arch-based Linux | `archlence-bin` package | No |
| Other x86-64 Linux | AppImage | No |
| macOS | Source installation | Yes |

Download packages from the
[latest GitHub release](https://github.com/superuser-d0/archlence/releases/latest).

For checksum verification, source installation, upgrades, removal, release
files, and troubleshooting, see the
[installation guide](docs/INSTALLATION.md).

## Privacy and data ownership

- Core financial records are stored locally; Archlence does not operate a
  server that receives them.
- Sensitive transaction fields are encrypted at rest with authenticated
  field encryption.
- No analytics or advertising trackers are included.
- External requests are limited to price data and selected visual metadata
  features; those features do not intentionally upload core financial records.
- A usable backup requires the database and matching password-protected
  recovery material. A database copy alone is insufficient.
- Losing both the active key and usable recovery material can make encrypted
  data unrecoverable.

Keep verified backups and store each recovery password separately. See
[key management](docs/KEY_MANAGEMENT.md),
[backup and recovery](docs/BACKUP_RECOVERY.md), and the current
[security and reliability status](docs/SECURITY_RELIABILITY_STATUS.md).

Archlence is not a bank, brokerage, accounting platform, or financial adviser.

## Project status

Archlence is under active pre-release development and is not yet recommended
as the sole store for day-to-day financial records. Current stabilization work
includes:

- completing the shared `Decimal` policy across remaining financial paths;
- validating packaged OS-keystore and recovery behavior across more real
  Windows and Linux configurations;
- stabilizing credit-card and recurring-payment workflows;
- expanding real-hardware Windows installation, upgrade, persistence, and
  removal checks;
- adding code signing for the Windows installer and Linux AppImage;
- reducing broad exception handling and UI-layer responsibility debt.

For scope and current guarantees, see the [product vision](docs/VISION.md),
[security and reliability status](docs/SECURITY_RELIABILITY_STATUS.md), and
[changelog](CHANGELOG.md).

## Architecture

Archlence separates UI composition, application workflows, domain services,
persistence, and security concerns:

```text
main.py
├── ui/          Kivy layouts, components, charts, themes, and localization
├── mixins/      Application workflows and screen behavior
├── services/    Finance, pricing, insights, projection, and recovery services
├── database/    SQLite schema, migrations, models, and ledger primitives
├── security/    Local authentication and access-control services
├── utils/       Decimal, encryption, key storage, paths, and formatting
└── tests/       Unit, integration, security, packaging, and UI regressions
```

```text
Kivy UI
   ↓
Application workflows
   ↓
Domain services
   ↓
Ledger and SQLite
   ↓
Encryption and OS key storage
```

Critical implementation contracts include atomic ledger and balance
operations, transactional settlement, migration guards, asynchronous price
refresh, authenticated field encryption, and balance history/replay.

See the [architecture guide](docs/ARCHITECTURE.md) for boundaries, data flow,
and testing responsibilities.

## Development and tests

Archlence supports Python 3.11 or newer. CI and packaged builds use the
repository-defined Python 3.12 environment.

```bash
python -m pip install -r requirements.txt
python run_tests.py
```

The suite covers ledger operations, transactions, accounts, subscriptions,
pricing, budgeting, history, projections, security, and selected UI contracts.
CI runs the full suite on Linux and Windows, with lint, type, version, and
visual-regression checks on Linux.

Financial-logic changes require regression tests that demonstrate ledger,
balance, and transaction integrity. For environment and platform dependencies,
see the [installation guide](docs/INSTALLATION.md).

## Contributing

Contributions are welcome.

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Browse the [open issues](https://github.com/superuser-d0/archlence/issues).
3. Create a focused branch.
4. Add regression tests where applicable.
5. Run the full test suite.
6. Open a draft pull request early for larger changes.

Financial-logic changes must demonstrate ledger, balance, and transaction
integrity. UI changes should include screenshots or a short recording.

## Security reporting

Do not share real financial information in issues, screenshots, fixtures, or
pull requests. Do not open a public issue for a suspected vulnerability; use a
[private GitHub security advisory](https://github.com/superuser-d0/archlence/security/advisories/new)
instead.

See [SECURITY.md](SECURITY.md) for the reporting process and pre-release support
scope.

## Roadmap

Near-term work prioritizes reliability before feature expansion:

- data integrity and completion of shared financial-number policies;
- backup, recovery, and key-management validation;
- packaged Windows validation on a broader range of real systems;
- credit-card and recurring-payment reliability;
- package signing and release trust;
- contributor experience and clearer architecture boundaries.

See the detailed [technical roadmap](docs/ROADMAP.md) and
[product vision](docs/VISION.md).

## License

Archlence is available under the [MIT License](LICENSE).
