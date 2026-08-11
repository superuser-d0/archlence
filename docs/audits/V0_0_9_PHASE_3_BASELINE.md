# v0.0.9 Phase 3 Baseline

Date: 2026-08-06. Start branch: `audit/v0.0.9-deep-review` at `4eb0160`;
fix branch: `fix/v0.0.9-reliability`.

Environment: Python 3.14.6, SQLite 3.53.4, Linux CachyOS, Kivy 2.3.1.

## Baseline commands

* `python run_tests.py` under isolated Xvfb: **699 PASS, 2 skipped**.
* `python -m compileall .`: PASS.
* `python scripts/check_version_consistency.py`: PASS.
* `python scripts/audit_exception_handlers.py`: PASS.

The explicit Phase 2 adversarial modules were intentionally red before
production work: mutable backup manifest; duplicate recurring charge/refund;
asset/debt partial commit; Infinity persistence; restore config rollback;
migration retry; CSV permissions; concurrent card limit. Exact pre-fix DB
states are retained in the Phase 2 reports and test output.
