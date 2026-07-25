# Archlence

<p align="center">
  <strong>A local-first personal finance, cash-flow, and portfolio dashboard.</strong>
</p>

<p align="center">
  Track accounts, transactions, recurring payments, debts, and investments from a single privacy-focused desktop application.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Kivy" src="https://img.shields.io/badge/UI-Kivy%20%2F%20KivyMD-5C3EE8">
  <img alt="SQLite" src="https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/tests-unittest-brightgreen">
  <img alt="Local first" src="https://img.shields.io/badge/privacy-local--first-00A896">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-yellow">
</p>

![Archlence dashboard](docs/screenshots/dashboard.png)

> The screenshots use generated sample data. No real financial information is included.

## Why Archlence?

Personal finance data should remain useful without becoming somebody else's dataset.

Archlence stores its core financial records locally, combines everyday cash-flow tracking with investment monitoring, and turns transaction history into practical signals such as financial health, unusual spending, and upcoming obligations.

- **One financial overview:** balances, income, expenses, debts, subscriptions, and investments in one interface.
- **Local-first storage:** core financial records are stored in a local SQLite database.
- **Actionable insights:** financial health scoring, cash-flow projections, and anomaly detection.
- **Automated routines:** recurring-payment tracking, subscription detection, and scheduled deductions.
- **Portfolio awareness:** stocks, cryptocurrencies, precious metals, and foreign currencies with background price refreshes.
- **Desktop-focused experience:** dark and light modes with Turkish and English interface options.

## Explore the application

### Cash-flow dashboard and financial insights

The home screen brings together the current balance, period comparisons, algorithmic projections, and a financial health score.

Archlence also surfaces active subscriptions, unusual expenses, open debts, upcoming payments, and recent transactions without requiring separate reports.

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/subscriptions.png" alt="Recurring subscriptions and payments"></td>
    <td width="50%"><img src="docs/screenshots/insights.png" alt="Subscription radar and unusual spending insights"></td>
  </tr>
  <tr>
    <td align="center"><strong>Recurring payments</strong><br>Review subscriptions, due dates, and automated payment activity.</td>
    <td align="center"><strong>Smart insights</strong><br>Spot recurring-payment candidates and spending outside normal patterns.</td>
  </tr>
</table>

### Portfolio tracking

Monitor total wealth and profit or loss across supported asset classes.

The portfolio view combines income and expense trends with allocation data, while the active-assets list keeps purchase price, quantity, and current performance visible. Historical entries preserve the story behind purchases and sales.

![Portfolio overview](docs/screenshots/portfolio-overview.png)

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/active-assets.png" alt="Active investment positions"></td>
    <td width="50%"><img src="docs/screenshots/asset-history.png" alt="Asset transaction history"></td>
  </tr>
  <tr>
    <td align="center"><strong>Active positions</strong><br>Stocks, cryptocurrencies, gold, and currencies in a unified list.</td>
    <td align="center"><strong>Asset history</strong><br>Trace purchases, sales, and realized outcomes.</td>
  </tr>
</table>

Price refreshes run outside the main UI path and use asset-aware caching to keep navigation responsive while avoiding unnecessary requests.

### Accounts, cards, and installment-aware transactions

Archlence supports cash and checking accounts as well as credit cards.

Account balances contribute to net wealth using a consistent signed-balance model, while credit limits, card debt, statement details, and installment activity remain available in the account layer.

![Accounts and cards](docs/screenshots/accounts.png)

Transaction creation supports:

- income and expense categories;
- account selection and backdated entries;
- recurring monthly or yearly payments;
- automatic deductions;
- credit-card installments;
- pending, rescheduled, and settled transactions.

### Financial planning tools

The tools workspace groups frequently used planning features, including monthly budgets, a calendar, general and compound-interest calculators, loan planning, savings goals, what-if scenarios, and CSV-based data operations.

![Financial tools](docs/screenshots/financial-tools.png)

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/loan-calculator.png" alt="Loan calculator"></td>
    <td width="50%"><img src="docs/screenshots/payment-schedule.png" alt="Loan payment schedule"></td>
  </tr>
  <tr>
    <td align="center"><strong>Loan calculator</strong><br>Compare term, rate, and loan type before committing.</td>
    <td align="center"><strong>Payment schedule</strong><br>Inspect principal, interest, and remaining balance month by month.</td>
  </tr>
</table>

### Personalization and privacy controls

Choose Turkish or English, switch between light and dark appearances, select a visual theme, inspect balance history, and reset local data from a single settings screen.

![Settings](docs/screenshots/settings.png)

## Core capabilities

| Area | Capabilities |
| --- | --- |
| Dashboard | Period summaries, balance trends, projections, health score, and recent activity |
| Transactions | Income and expense entry, categories, dates, pending items, and installments |
| Subscriptions | Detection radar, recurring schedules, automatic deductions, price updates, and cancellation |
| Budgeting | Monthly plans, category allocations, recurring-payment reservations, and trend review |
| Accounts | Checking and cash accounts, credit cards, statements, limits, and available balance |
| Investments | Multi-asset portfolio, price updates, profit/loss calculations, and asset history |
| Debt and savings | Debt progress, automatic installments, and savings goals |
| Data portability | CSV import and export for transactions and other supported financial records |
| Experience | Turkish and English localization, dark and light modes, and desktop-oriented navigation |

## Architecture

Archlence keeps interface, business logic, and persistence responsibilities separated:

```text
main.py
├── ui/          Kivy layouts, reusable components, charts, themes, and i18n
├── mixins/      Application workflows and screen behavior
├── services/    Transactions, accounts, pricing, insights, and projections
├── database/    SQLite schema, migrations, and ledger primitives
├── security/    Local security and access-control services
├── utils/       Formatting, currency, cryptography, and ticker helpers
└── tests/       Unit, integration, and GUI-oriented regression tests
```

Notable implementation details include:

- atomic balance updates and ledger events;
- `SAVEPOINT`-backed settlement for due transactions;
- SQLite migration guards for existing installations;
- asynchronous asset-price workers with dynamic cache lifetimes;
- local field-level protection for selected sensitive values;
- daily balance snapshots and event replay for historical balances.

> The local security and encryption model is under active development. Broader database-level protection and stronger key management are planned.

## Project status

Archlence is under active development.

The current focus is:

- strengthening local encryption and key management;
- expanding automated and regression test coverage;
- improving packaging and installation;
- documenting architectural decisions;
- making the repository easier for outside contributors to understand and extend.

The project should currently be considered an early-stage open-source desktop application rather than production financial infrastructure.

## Getting started

### Requirements

- Python 3.11 or newer
- A desktop environment supported by Kivy
- Git

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

Install the dependencies and start the application:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

On first launch, Archlence guides you through creating a local PIN and setting up your first account.

## Tests

The repository currently contains **297 test methods across 34 test modules**, covering areas including:

- ledger and balance integrity;
- transactions and accounts;
- subscriptions and recurring payments;
- asset pricing and caching;
- budgets and projections;
- historical balances;
- local security;
- user-interface contracts.

Run the complete test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

GUI checks may require a virtual display on headless Linux:

```bash
xvfb-run -a python -m unittest tests.test_gui tests.test_ids
```

## Privacy and data

Archlence is designed around local data ownership:

- core financial records are stored in `finance.db` on the user's machine;
- settings, local databases, and runtime data are excluded from Git by default;
- the application does not include analytics or advertising trackers;
- CSV export provides a human-readable way to move supported records elsewhere;
- portfolio price refreshes and some visual metadata features may contact external public data sources;
- core financial records remain local and are not intentionally uploaded by these features.

Keep regular backups of your local database.

Archlence is a personal finance management tool. It is not a bank, brokerage service, accounting platform, or source of financial advice.

## Roadmap

- Stronger local encryption and installation-specific key management
- Natural-language queries over local financial history
- Local receipt parsing and categorization
- More explainable forecasts and budget recommendations
- Additional portfolio data sources and reporting options
- Improved packaging and automated release workflows
- Contributor documentation and architecture decision records

## Contributing

Issues and pull requests are welcome.

For changes to financial logic, include tests that demonstrate balance, ledger, and transaction integrity before and after the operation.

For UI changes, screenshots or short screen recordings are helpful whenever possible.

Before opening a large pull request, consider creating an issue to discuss the proposed change and its expected behavior.

## Security

Please avoid publishing sensitive personal or financial information in issues, screenshots, test fixtures, or pull requests.

For security-related findings, open a private GitHub security advisory when possible instead of creating a public issue.

## License

Archlence is licensed under the [MIT License](LICENSE).
