"""Backend-only resource trend probe; uses a generated temporary profile."""
from __future__ import annotations

import gc
import json
import os
import sqlite3
import tempfile
import threading
import tracemalloc
import sys
from contextlib import closing
from pathlib import Path
from unittest import mock
from utils.errors import ArchlenceError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sample(label):
    rss = None
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ValueError, TypeError, ArithmeticError, sqlite3.Error, OSError, ArchlenceError):
        pass
    return {
        "label": label,
        "threads": len(threading.enumerate()),
        "fds": len(os.listdir("/proc/self/fd")) if Path("/proc/self/fd").is_dir() else None,
        "rss_kib": rss,
        "python_bytes": tracemalloc.get_traced_memory()[0],
    }


def main():
    from database.init_db import initialize_database
    from database.db import get_connection
    from services.account_service import AccountService
    from services.backup_service import create_backup, verify_backup

    tracemalloc.start()
    with tempfile.TemporaryDirectory(prefix="archlence-resource-audit-") as root:
        root = Path(root)
        db_path, key_path = root / "finance.db", root / "encryption.key"
        key_path.write_bytes(os.urandom(32)); os.chmod(key_path, 0o600)
        with mock.patch("database.db.DB_NAME", str(db_path)), mock.patch(
            "utils.crypto._get_aead_key", return_value=key_path.read_bytes()
        ):
            initialize_database()
            account_id = AccountService.create_account("Resource audit", "checking", 1000)
            samples = [_sample("baseline")]
            for iteration in range(1, 101):
                with get_connection() as conn:
                    conn.execute("SELECT balance FROM accounts WHERE id=?", (account_id,)).fetchone()
                    conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
                # Explicit raw open/close checks the connection factory does not retain FDs.
                with closing(sqlite3.connect(db_path)) as conn:
                    conn.execute("SELECT 1").fetchone()
                if iteration in (10, 50, 100):
                    samples.append(_sample(f"iteration_{iteration}"))
            package = root / "resource.archlence-backup"
            for _ in range(10):
                create_backup(package, "yalnizca-audit-icin-parola", db_path=db_path, key_path=key_path)
                verify_backup(package, "yalnizca-audit-icin-parola")
            samples.append(_sample("after_backup_10"))
            gc.collect()
            samples.append(_sample("after_gc"))
    result = {"scope": "backend_db_and_backup_only", "samples": samples}
    print("AUDIT_RESOURCE " + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
