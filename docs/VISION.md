# Archlence — product vision and scope

> See `CHANGELOG.md` for the current release status, `docs/ROADMAP.md` for the
> technical plan, and `docs/SECURITY_RELIABILITY_STATUS.md` for the current
> security and reliability summary.

## Product

Archlence is a **local-first, offline-capable** personal-finance desktop
application. User data remains on the user's computer; the application does
not send financial records to an Archlence server. Amount and description
fields are encrypted at rest.

The product covers accounts and credit cards, income and expense transactions,
budget planning, savings goals, portfolio tracking (stocks, precious metals,
foreign currencies, and cryptocurrencies), subscription and recurring-payment
detection, balance history, and scenario projections.

## Brand

The product name is **Archlence**. Its icon is a white “A” monogram on the
brand blue (`#5444E5`). This value intentionally matches
`ARCHLENCE_PRIMARY_HEX` in `ui/theme.py`, preventing the icon and application
theme from drifting into separate, unmanaged brand colors.

`assets/icon_source.svg` is the source of truth; `icon.png` and `icon.ico` are
derived from it. The design decision is empirical: the thin rays in the
previous identity disappeared at 48 pixels (taskbar and tray size), making the
mark unreadable. The solid letterform remains legible down to 16 pixels.
Evaluate the icon using the real `.ico` sizes, not only the 1024-pixel PNG.

## Release line and the meaning of “stable”

The current line is **1.x — stable**. Stable means that supported packages,
data integrity, upgrades, backup, restore, and recovery are guarded by release
tests and verified acceptance paths. It does not remove the need for backups
or turn the application into a regulated financial service.

Every stable release must continue to meet these conditions:

- No known defect may corrupt user data, especially any defect that records a
  value different from the value entered by the user.
- The upgrade path must be measured: opening a previous-release profile in the
  new release must preserve its data. The Windows workflow explicitly reports
  when no valid baseline release exists and the upgrade gate is skipped.
- Backup and restore must be verified.
- Windows and Linux packages must be shown to install and launch successfully.

“Stable” does not mean banking or accounting certification. It describes
package and usage stability together with the verified data-integrity and
recovery scope.

## Platform scope

Windows and Linux are supported targets. macOS is currently out of scope until
`.dmg`, signing, and notarization work is explicitly planned.

Packages are **unsigned**. Windows SmartScreen may warn on first launch. Code
signing has been deliberately deferred.

## Durable engineering decisions

These decisions were learned through expensive failures. Read their rationale
before changing them.

- **Packaging uses Python 3.12.** Local development may use a newer version,
  but Kivy and PyInstaller binary/DLL compatibility is risky on untested Python
  versions. The build workflows document this next to `setup-python`.
- **`collect_all("kivymd")` needs a real OpenGL context.** SDL's `dummy`
  driver supplies no GL surface. Linux builds use `xvfb-run` with Mesa
  llvmpipe; Windows builds use ANGLE (`KIVY_GL_BACKEND=angle_sdl2`).
- **Run tests through `run_tests.py`.** Direct `python -m unittest` calls skip
  the project's headless defaults. The runner also preserves reporting when
  Kivy replaces `sys.stderr`.
- **Financial reads fail closed.** An unreadable record is never counted as
  zero; its metric becomes invalid or partial. Showing no total is safer than
  showing a false total.

## Out of scope for now

Mobile applications, cloud synchronization, multi-user/shared budgets, open
banking integrations, and automatic receipt or invoice recognition.
