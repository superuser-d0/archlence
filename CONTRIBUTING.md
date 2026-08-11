# Contributing to Archlence

Contributions are welcome. Archlence handles sensitive financial state, so a
small, well-tested change is easier to review and safer to merge than a broad
rewrite.

By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Development environment

Use Python 3.11 or newer; CI and packaged builds currently use Python 3.12.
Follow the [installation guide](docs/INSTALLATION.md) for platform packages and
source setup, then install the complete development requirements:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

On Windows, use `.venv\Scripts\python.exe`. Virtual-environment activation is
optional.

## Before opening an issue

- Search existing issues and the [changelog](CHANGELOG.md).
- Reproduce the behavior on the latest public pre-release or current `main`.
- Use generated sample data whenever possible.
- Remove account names, amounts, descriptions, keys, tokens, and personal paths
  from logs and screenshots.
- Use the private process in [SECURITY.md](SECURITY.md) for suspected
  vulnerabilities; do not open a public issue.

Bug reports should identify the Archlence version, operating system,
installation method, exact reproduction steps, expected and actual behavior,
and sanitized logs. Explain whether the issue was reproduced with sample or
real data without attaching real financial records.

## Small and large changes

Typo fixes, focused documentation improvements, narrow regressions, and
well-scoped tests can usually go directly to a pull request.

Open an issue before a large feature, schema change, dependency change,
architecture rewrite, security-policy change, or modification to encryption,
key management, backup, or recovery. Describe the user problem and compatibility
risk before investing in an implementation.

For a larger accepted change, open a draft pull request early so design,
migration, and test boundaries can be reviewed before the diff grows.

## Branches and commits

- Branch from the latest `main`.
- Use a short purpose-based name such as `fix/card-settlement` or
  `docs/install-guide`.
- Keep one logical change per branch.
- Write imperative commit subjects that explain the outcome.
- Avoid mixing formatting sweeps or unrelated cleanup into a functional fix.
- Do not commit local databases, recovery packages, logs, generated user data,
  secrets, or environment-specific configuration.

## Tests

Run the complete suite before opening a pull request:

```bash
python run_tests.py
```

The wrapper is the primary entry point because it establishes headless Kivy
defaults before test discovery and preserves a failing exit status. CI runs it
on Linux and Windows. The workflow also runs critical lint checks, an exception
baseline, selected type checks, version consistency, and visual regressions.

### Type checking

`services/` and `database/` are type-checked in CI, with imports followed, so
their dependencies are checked too.

Reproduce a CI type-check result in a **clean Python 3.12** environment with
**both** requirement sets installed:

```bash
python3.12 -m venv /tmp/archlence-typecheck
/tmp/archlence-typecheck/bin/python -m pip install -r requirements-runtime.txt -r requirements-dev.txt
/tmp/archlence-typecheck/bin/python -m mypy --no-incremental services database
```

Three details matter, each of them learned from a diagnostic that appeared in
CI and not locally:

- **CI runs Python 3.12.** A newer local interpreter is not an acceptance
  criterion; a 3.14 environment has reported clean while CI failed.
- **Runtime dependencies must be installed.** Without them Pillow, requests and
  keyring resolve to `Any` and real boundary errors disappear.
- **Use `--no-incremental` when reproducing.** A stale `.mypy_cache` can hide a
  diagnostic that a fresh run reports.

### Financial integrity

Changes to transactions, balances, accounts, credit cards, subscriptions,
budgets, debt, savings, assets, migrations, or recovery must include regression
tests appropriate to the operation. Demonstrate that:

- the ledger and affected balances agree after success;
- multi-step changes are atomic;
- rollback leaves prior state intact;
- duplicate or repeated actions do not apply money twice;
- unreadable encrypted values do not become zero inside totals;
- existing profiles and migrations retain their data.

Tests should include the failure path that motivated the change, not only the
successful path.

### UI and localization

Include screenshots or a short recording for visible UI changes. Check Turkish
and English, relevant empty/error/loading states, and light/dark appearance when
the change affects styling. Avoid embedding user-facing text outside the
localization system.

Localization changes should update both languages, preserve format placeholders,
and include or update translation tests. Use generated sample data in every
capture.

## Pull requests

Complete the pull request template and keep the summary focused on the problem
being solved. Link the relevant issue when one exists.

Before requesting review:

- [ ] The branch contains one focused change.
- [ ] The full test suite passes locally.
- [ ] New behavior and failure paths have regression coverage.
- [ ] Financial-integrity impact is explained.
- [ ] UI evidence is included or marked not applicable.
- [ ] Turkish and English were checked where relevant.
- [ ] Documentation and changelog impact were considered.
- [ ] No real financial data, credentials, keys, or private paths are present.
- [ ] Security-sensitive details are being handled privately.

Maintainers may ask for a smaller diff, a migration plan, or stronger rollback
evidence before merging a change that touches stored financial data.
