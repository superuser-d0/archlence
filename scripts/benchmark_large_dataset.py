"""Repeatable isolated 1K/10K/50K Archlence service benchmark."""

import argparse
import base64
import json
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def elapsed(callable_, repeats=1):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = callable_()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 3),
        "min_ms": round(min(samples), 3),
        "samples": len(samples),
    }, result


def legacy_encrypt(value, key):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(
        iv + cipher.encrypt(pad(str(value).encode("utf-8"), 16))
    ).decode("ascii")


def seed(db_path, count):
    from database.db import SECRET_KEY
    from utils.crypto import _get_key

    legacy_key = _get_key(SECRET_KEY)
    rng = random.Random(20260730 + count)
    now = datetime.now()
    rows = []
    for index in range(count):
        income = index % 7 == 0
        amount = (
            round(rng.uniform(5_000, 25_000), 2)
            if income
            else round(rng.uniform(10, 2_500), 2)
        )
        date = now - timedelta(days=index % 365)
        rows.append(
            (
                1,
                legacy_encrypt(amount, legacy_key),
                "income" if income else "expense",
                "Maaş" if income else "Süpermarket",
                legacy_encrypt(f"benchmark-{index}", legacy_key),
                date.strftime("%Y-%m-%d %H:%M:%S"),
                "completed",
                date.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO accounts "
            "(id,name,type,balance,account_type) VALUES (1,'Benchmark',"
            "'bank',0,'checking')"
        )
        conn.executemany(
            "INSERT INTO transactions "
            "(account_id,amount,type,category,description,transaction_date,"
            "status,execution_date) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()


def run_size(root, count):
    from database import db as db_module
    from database.init_db import initialize_database
    from services.backup_service import create_backup, restore_backup
    from services.budget_service import calculate_monthly_budget
    from services.crypto_migration_service import migrate_legacy_encryption
    from services.financial_summary_service import summarize_transactions
    from services.insights_service import compute_financial_health_score
    from utils.crypto import _get_aead_key, _get_key_provider
    from utils.key_provider import FileKeyProvider

    case = root / str(count)
    case.mkdir()
    db_path = case / "finance.db"
    key_path = case / "encryption.key"
    provider = FileKeyProvider(str(key_path))
    provider.get_or_create_key()
    db_module.DB_NAME = str(db_path)
    # Modules importing DB_NAME by value are not used in this benchmark.
    startup, _ = elapsed(initialize_database)
    seed(db_path, count)
    _get_key_provider.cache_clear()
    _get_aead_key.cache_clear()

    def dashboard():
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT t.id,t.amount,t.type,"
                "COALESCE(c.importance,'extra') importance "
                "FROM transactions t LEFT JOIN categories c "
                "ON t.category=c.name WHERE "
                "COALESCE(t.status,'completed')='completed'"
            ).fetchall()
        return summarize_transactions(rows)

    dashboard_time, _ = elapsed(dashboard, repeats=3)

    def monthly():
        month = datetime.now().strftime("%Y-%m")
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT t.id,t.amount,t.type,"
                "COALESCE(c.importance,'extra') importance "
                "FROM transactions t LEFT JOIN categories c "
                "ON t.category=c.name "
                "WHERE substr(t.transaction_date,1,7)=?",
                (month,),
            ).fetchall()
        return summarize_transactions(rows)

    monthly_time, _ = elapsed(monthly, repeats=3)
    budget_time, _ = elapsed(
        lambda: calculate_monthly_budget(
            datetime.now().month, datetime.now().year
        ),
        repeats=3,
    )
    insights_time, _ = elapsed(
        lambda: compute_financial_health_score(
            lookback_days=365, persist=False
        )
    )
    decrypt_time, _ = elapsed(dashboard)

    migration_backup = case / "pre-migration.backup"
    migration_time, migration_result = elapsed(
        lambda: migrate_legacy_encryption(
            "benchmark-kurtarma-parolasi",
            migration_backup,
            db_path=db_path,
            key_provider=provider,
        )
    )
    package = case / "verified.backup"
    backup_time, backup_result = elapsed(
        lambda: create_backup(
            package,
            "benchmark-kurtarma-parolasi",
            db_path=db_path,
            key_path=key_path,
        )
    )
    restore_db = case / "restored" / "finance.db"
    restore_key = case / "restored" / "encryption.key"
    restore_time, _ = elapsed(
        lambda: restore_backup(
            package,
            "benchmark-kurtarma-parolasi",
            db_path=restore_db,
            key_path=restore_key,
        )
    )
    return {
        "transactions": count,
        "database_startup": startup,
        "dashboard_summary": dashboard_time,
        "monthly_summary": monthly_time,
        "budget_summary": budget_time,
        "insights_365d": insights_time,
        "decrypt_full_dataset": decrypt_time,
        "legacy_migration": migration_time,
        "backup": backup_time,
        "restore": restore_time,
        "migrated_fields": migration_result["migrated_fields"],
        "backup_aead_fields": backup_result["aead_records_verified"],
        "database_bytes": db_path.stat().st_size,
        "backup_bytes": package.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="docs/performance/benchmark-results.json"
    )
    parser.add_argument(
        "--sizes", nargs="+", type=int, default=[1000, 10000, 50000]
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="archlence-benchmark-") as temp:
        results = [run_size(Path(temp), size) for size in args.sizes]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "python": sys.version,
                "platform": sys.platform,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
