#!/usr/bin/env python3
"""Verify recovery against a profile created by the packaged Windows app.

The Windows workflow launches the frozen executable with an isolated
``ARCHLENCE_HOME`` before invoking this script. This check therefore starts
from the database and DPAPI blob produced by the actual package, then exercises
the production backup and restore services against that profile.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"Packaged Windows profile verification failed: {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--home",
        required=True,
        help="ARCHLENCE_HOME used when the packaged executable was launched.",
    )
    args = parser.parse_args()

    if os.name != "nt":
        _fail("this check must run on Windows")

    home = Path(args.home).resolve()
    os.environ["ARCHLENCE_HOME"] = str(home)

    # Imports must happen after ARCHLENCE_HOME is fixed because database.db
    # resolves its production path at import time.
    from services.account_service import AccountService, CHECKING
    from services.backup_service import create_backup, restore_backup, verify_backup
    from utils.key_provider import create_platform_key_provider

    data = home / "data"
    database = data / "finance.db"
    protected_key = data / "encryption.key.dpapi"
    raw_key = data / "encryption.key"
    if not database.is_file():
        _fail(f"the packaged app did not create {database}")
    if not protected_key.is_file():
        _fail("the packaged app did not create a DPAPI-protected key blob")
    if raw_key.exists():
        _fail("the packaged app left a raw encryption.key file")

    provider = create_platform_key_provider(data)
    if provider.status.method != "Windows DPAPI" or not provider.status.secure_store:
        _fail(f"unexpected key protection status: {provider.status!r}")
    key_before = provider.load_key()
    if key_before is None or len(key_before) != 32:
        _fail("the packaged DPAPI key could not be loaded")
    blob = protected_key.read_bytes()
    if key_before == blob or key_before in blob:
        _fail("the DPAPI blob contains the raw key")

    before_name = "packaged-recovery-before"
    after_name = "packaged-recovery-after"
    AccountService.create_account(before_name, CHECKING, initial_balance=4321.09)

    package = home / "packaged-profile.archlence-backup"
    safety = home / "packaged-profile-safety.archlence-backup"
    passphrase = "Archlence-packaged-recovery-check-2026!"
    created = create_backup(
        package,
        passphrase,
        db_path=database,
        key_provider=provider,
    )
    verified = verify_backup(package, passphrase)
    if created["database_sha256"] != verified["metadata"]["database_sha256"]:
        _fail("the published backup digest changed during verification")

    AccountService.create_account(after_name, CHECKING, initial_balance=99.99)
    restored = restore_backup(
        package,
        passphrase,
        db_path=database,
        key_provider=provider,
        safety_backup_path=safety,
    )
    if not restored.get("restored"):
        _fail("restore did not report success")

    accounts = {row["name"]: row for row in AccountService.get_accounts()}
    if before_name not in accounts:
        _fail("the account stored before backup was not restored")
    if after_name in accounts:
        _fail("the post-backup account survived restore")
    if abs(float(accounts[before_name]["balance"]) - 4321.09) > 0.001:
        _fail("the restored account balance changed")

    key_after = create_platform_key_provider(data).load_key()
    if key_after != key_before:
        _fail("the DPAPI key changed across backup and restore")
    if raw_key.exists():
        _fail("backup or restore introduced a raw encryption.key file")
    if not safety.is_file():
        _fail("restore did not create its safety backup")

    print(
        "Packaged Windows DPAPI profile and backup/restore round trip verified."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
