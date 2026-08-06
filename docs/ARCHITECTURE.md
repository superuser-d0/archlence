# Architecture

This document describes the current repository boundaries and the contracts
that changes should preserve. It is not a claim that every boundary is already
complete; remaining UI-layer and broad-exception debt is tracked in the
[security and reliability status](SECURITY_RELIABILITY_STATUS.md).

## Repository map

```text
main.py
├── ui/          Kivy layouts, reusable components, charts, theme, and i18n
├── mixins/      Application workflows and screen-level behavior
├── services/    Domain operations, pricing, insights, projections, and recovery
├── database/    SQLite schema, migrations, models, connections, and ledger
├── security/    Local authentication, password policy, and login throttling
├── utils/       Decimal, encryption, key storage, paths, logging, and formatting
└── tests/       Unit, integration, security, packaging, and UI regressions
```

`main.py` is the composition root. It initializes the Kivy/KivyMD application,
connects mixin-provided workflows to screens, starts required services, and
coordinates refreshes. New domain rules should not be added there when they
can live in a service with a direct test.

## Application flow

```text
Kivy UI and events
        ↓
Application workflows in mixins
        ↓
Domain and orchestration services
        ↓
Ledger operations and SQLite persistence
        ↓
Authenticated field encryption and OS-backed key storage
```

The boundaries are directional guidelines rather than separate processes.
Some existing mixins still own more error handling and state coordination than
the target architecture requires.

## Persistence and financial integrity

SQLite is the local system of record. Connection helpers and service-level
transactions protect operations that must update balances, financial records,
and ledger events together.

Important contracts include:

- balance changes and corresponding ledger events are atomic;
- due-transaction settlement uses transaction or savepoint boundaries;
- migrations are guarded and must preserve existing profiles;
- unreadable encrypted values that feed totals fail closed instead of becoming
  a confident zero;
- daily snapshots and ledger replay support historical balance views;
- financial-number boundaries use the shared Decimal policy where migration is
  complete, with remaining paths tracked as stabilization work.

Financial-logic pull requests should prove these contracts with regression
tests covering success, rollback, and failure paths.

## Encryption and key storage

Sensitive fields are written with the versioned AEAD format implemented under
`utils/`. Key-provider selection uses Windows DPAPI, Linux Secret Service or
KWallet through `keyring`, or a permission-restricted local-file fallback when
no suitable OS key store is available.

Legacy CBC data remains read-only compatibility input and is migrated through a
backup-first transactional workflow. Key rotation, backup, and restore validate
key/database compatibility before replacing active material.

See [Key management](KEY_MANAGEMENT.md),
[Backup and recovery](BACKUP_RECOVERY.md), and
[Legacy encryption migration](ENCRYPTION_MIGRATION.md) for the detailed
security contracts.

## Background and external data

Asset-price work runs outside the main UI path. Provider fallbacks, caching,
and freshness metadata are service responsibilities; UI code should render the
result without hiding its source or age. External requests are limited to price
and selected visual metadata features.

Background work must report failures through the persistent logger and return
UI updates through Kivy's scheduling boundary. It must not mutate widgets from
a worker thread.

## Localization and UI

`ui/` owns shared Kivy components, charts, theme values, and Turkish/English
translation data. `mixins/` coordinate dialogs, screens, and user actions.
Reusable business rules belong in `services/`, not in translated strings or
widget callbacks.

UI changes should be checked in both languages, light and dark themes where
relevant, and representative display scaling. Include screenshots or a short
recording in the pull request.

## Test and CI boundaries

`python run_tests.py` is the primary suite entry point. It establishes the
headless environment before Kivy imports and preserves test reporting and exit
status.

The Tests workflow runs the suite on Linux and Windows. Linux jobs also enforce
critical lint rules, the broad-exception baseline, selected type checks, version
consistency, and visual contracts across Turkish/English and two DPI settings.
Packaging workflows separately build and smoke-test the Windows installer and
Linux AppImage.

Tests should be placed close to the contract they protect:

- services and database tests for financial state transitions;
- migration and recovery tests for rollback and compatibility;
- encryption tests for tamper, corruption, and unavailable-key behavior;
- mixin or GUI tests for workflow and rendering contracts;
- packaging checks for installed-launch, upgrade, persistence, and removal.

## Change checklist

Before changing a boundary, answer these questions:

1. Can the rule move into a service that can be tested without a live window?
2. Does the operation update all related balances and ledger entries atomically?
3. Does a failure preserve the previous database and key state?
4. Are external data source, age, and failure behavior still visible?
5. Does the change need a migration or previous-release compatibility test?
6. Are Turkish/English and packaged-runtime behavior covered where relevant?
