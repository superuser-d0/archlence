#!/usr/bin/env python3
"""Generate populated old-tag profiles and compare upgrades to current schema.

The default command operates only in newly-created temporary directories.  It
never discovers or opens an Archlence user profile.  Old releases must already
be available as detached worktrees named ``/tmp/archlence-audit-v001`` through
``v008`` (or supplied with ``--worktree-root``).

Usage:
    python scripts/audit/check_schema_consistency.py --output /tmp/matrix.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

CURRENT_ROOT = Path(__file__).resolve().parents[2]
VERSIONS = tuple(f"v0.0.{index}" for index in range(1, 9))


def _db_schema(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        tables = {}
        for (table,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            tables[table] = {
                "columns": [tuple(row[1:6]) for row in conn.execute(
                    f"PRAGMA table_info({table})"
                )],
                "indexes": [tuple(row[1:4]) for row in conn.execute(
                    f"PRAGMA index_list({table})"
                )],
                "foreign_keys": [tuple(row) for row in conn.execute(
                    f"PRAGMA foreign_key_list({table})"
                )],
                "rows": conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0],
            }
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    return {"user_version": user_version, "tables": tables}


def _schema_structure(schema):
    """Drop data-dependent row counts before comparing fresh vs upgraded."""
    return {
        "user_version": schema["user_version"],
        "tables": {
            table: {
                key: value
                for key, value in details.items()
                if key != "rows"
            }
            for table, details in schema["tables"].items()
        },
    }


def _value(row, name, default=None):
    return row[name] if name in row.keys() else default


def _semantic_snapshot(db_path, decrypt):
    encrypted = {
        "transactions": ("amount", "description"),
        "active_assets": ("purchase_price", "quantity"),
        "active_debts": ("debt_name", "total_amount", "monthly_payment"),
        "recurring_payments": ("name", "amount"),
        "savings_goals": ("goal_name",),
    }
    common = {
        "accounts": (
            "id", "name", "type", "balance", "account_type", "credit_limit"
        ),
        "transactions": (
            "id", "account_id", "amount", "type", "category", "description",
            "transaction_date", "status", "execution_date",
        ),
        "active_assets": (
            "id", "asset_name", "asset_code", "asset_type", "purchase_price",
            "quantity", "purchase_date",
        ),
        "active_debts": (
            "id", "debt_name", "total_amount", "monthly_payment",
            "total_installments", "paid_installments", "is_active",
        ),
        "recurring_payments": (
            "id", "name", "amount", "category", "frequency", "next_due_date",
            "recurrence_day", "auto_deduct", "is_active", "account_id",
            "transaction_type",
        ),
        "savings_goals": (
            "id", "goal_name", "target_amount", "current_amount", "status",
        ),
    }
    snapshot = {}
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        available_tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table, wanted in common.items():
            if table not in available_tables:
                snapshot[table] = []
                continue
            actual = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table})")
            }
            rows = []
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY id"):
                item = {}
                for column in wanted:
                    if column not in actual:
                        continue
                    value = row[column]
                    if column in encrypted.get(table, ()) and value is not None:
                        value = decrypt(str(value), "finora_secure_2026")
                    item[column] = value
                rows.append(item)
            snapshot[table] = rows
    payload = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "state": snapshot,
    }


def _configure_isolated_home(profile):
    os.environ["ARCHLENCE_HOME"] = str(profile)
    os.environ["XDG_DATA_HOME"] = str(profile / "xdg-data")
    os.environ["XDG_CACHE_HOME"] = str(profile / "xdg-cache")
    os.environ["XDG_CONFIG_HOME"] = str(profile / "xdg-config")
    # KIVY DA İZOLE EDİLMELİ. XDG dizinleri ayrılıyordu ama Kivy kendi
    # durumunu `~/.kivy` altında tutuyor ve orası paylaşık kalıyordu: aynı
    # profil için önce ESKİ sürümün kodu, sonra GÜNCEL kod çalışıyor, yani
    # ikinci koşum birincinin yazdığı Kivy config'ini okuyor. Bu, izolasyon
    # iddiasındaki gerçek bir boşluktu.
    os.environ["KIVY_HOME"] = str(profile / "kivy-home")


def _load_code(code_root, db_path, profile):
    sys.path.insert(0, str(code_root))
    os.chdir(code_root)
    _configure_isolated_home(profile)
    from database import db as db_module

    db_module.DB_NAME = str(db_path)
    from database.init_db import initialize_database

    return db_module, initialize_database


def _old_worker(args):
    code_root = Path(args.code_root).resolve()
    db_path = Path(args.db).resolve()
    profile = Path(args.profile).resolve()
    db_module, initialize_database = _load_code(code_root, db_path, profile)
    initialize_database()

    from services.account_service import AccountService
    from services.savings_service import SavingsService
    from services.transaction_service import TransactionService

    account_id = AccountService.create_account(
        "Göç Vadesiz", "checking", initial_balance=20_000.0
    )
    AccountService.create_account(
        "Göç Kart", "credit_card", credit_limit=50_000.0
    )
    for amount, kind, category, description, timestamp in (
        (125.50, "expense", "Market", "Türkçe şifreli açıklama", "2025-12-31 23:59:59"),
        (250.00, "income", "Diğer", "Yıl sonu geliri", "2026-01-01 00:00:01"),
        (0.29, "expense", "Diğer", "Kuruş sınırı", "2024-02-29 12:00:00"),
    ):
        TransactionService.add_transaction(
            account_id, amount, kind, category, description,
            transaction_date=timestamp,
        )
    db_module.insert_debt("Göç Borcu", 12_500.00, 1041.67, 12, 1, 31)
    db_module.insert_asset("Göç Altını", "GAU", "Altın", 2890.45, 1.2345)
    db_module.insert_asset_transaction(
        account_id, 300.0, "expense", "Varlık Alımı", "Göç varlık kaydı"
    )
    db_module.insert_recurring_payment(
        "Göç Aboneliği", 99.99, "Dijital Platformlar", "monthly",
        "2026-02-28", True, account_id=account_id, recurrence_day=31,
    )
    SavingsService.create_goal("Göç Birikimi", 10_000.0, current_amount=321.09)

    before = {
        "schema": _db_schema(db_path),
        "financial": _semantic_snapshot(db_path, db_module.decrypt),
    }
    Path(args.result).write_text(
        json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def _current_worker(args):
    code_root = Path(args.code_root).resolve()
    db_path = Path(args.db).resolve()
    profile = Path(args.profile).resolve()
    db_module, initialize_database = _load_code(code_root, db_path, profile)
    initialize_database()
    first = _db_schema(db_path)
    initialize_database()
    second = _db_schema(db_path)
    # Import is the headless part of application startup that is meaningful
    # without opening a GUI window.
    import main  # noqa: F401

    result = {
        "schema": second,
        "idempotent_schema": first == second,
        "financial": _semantic_snapshot(db_path, db_module.decrypt),
        "application_import": "ok",
    }
    Path(args.result).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def _subprocess(worker, code_root, db_path, profile, result):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        f"--{worker}-worker",
        "--code-root", str(code_root),
        "--db", str(db_path),
        "--profile", str(profile),
        "--result", str(result),
    ]
    # HEADLESS SÖZLEŞMESİ WORKER'A DA GEÇMELİ. `run_tests.py` bu dört
    # değişkeni kendisi kuruyor; buradaki alt süreçler kurmuyordu ve CI'da
    # Kivy'nin girdi sağlayıcı taraması `kivy.input.providers.mtdev`'i import
    # edip `libmtdev.so.1` yükleyemeyince patlıyordu ("Couldn't connect to X
    # server" da aynı kökten). Geliştirici makinesinde kütüphane ve X sunucusu
    # var, o yüzden yalnızca CI'da görüldü.
    environment = {
        **os.environ,
        "KIVY_NO_ARGS": "1",
        "ARCHLENCE_HEADLESS": "1",
        "KIVY_WINDOW": "sdl2",
    }
    # SDL SÜRÜCÜSÜ EKRANIN VARLIĞINA GÖRE SEÇİLİR.
    #
    # Worker `import main` yapıyor, yani Kivy GERÇEKTEN bir Window
    # sağlayıcısı kuruyor. `dummy` sürücüsünde OpenGL yok; sağlayıcı
    # bulunamayınca Kivy `sys.exit(1)` çağırıyor ve worker kendi hata
    # mesajını bile üretemeden ölüyor (CI'da stderr'de yalnız Kivy'nin
    # CRITICAL'i vardı, Python traceback'i yoktu).
    #
    # Bunu `dummy` olarak SABİTLEMEK, adımı `xvfb` altında koştursak bile
    # sanal ekranı işe yaramaz kılıyordu — hata mesajındaki
    # "current SDL video driver (dummy)" tam olarak bunu söylüyor.
    #
    # `main.py` ARCHLENCE_HEADLESS altında `setdefault` ile `dummy` yazıyor;
    # burada AÇIKÇA set edildiğinde o varsayılan devreye girmiyor.
    if environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY"):
        environment["SDL_VIDEODRIVER"] = "x11"
    else:
        environment["SDL_VIDEODRIVER"] = "dummy"

    completed = subprocess.run(
        command, text=True, capture_output=True, timeout=120, env=environment
    )
    if completed.returncode:
        raise RuntimeError(
            f"{worker} worker failed ({code_root}):\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _ensure_worktree(worktree, version):
    """Eksikse etiketten detached worktree kurar; kurduysa `True` döner.

    NEDEN VAR: bu adım worktree'leri HAZIR BULMAYI bekliyordu ve yoksa
    `SystemExit` atıyordu. Kimse onları oluşturmadığı için `reliability-gates`
    job'ında hiç çalışamadı — job `ad6296f` ile eklendi ama CI yalnız
    `main`/PR'da koştuğu ve bu dal hiç push edilmediği için kırmızı olduğu
    ilk gerçek koşuma kadar görülmedi. Yerelde de kırılgandı: worktree'ler
    `/tmp` altındaydı, sistem `/tmp`'yi temizleyince adım bozuluyordu.

    Artık eksikse kendisi kuruyor. Etiket yoksa açık hata verir — `git tag`
    boşsa checkout tag çekmemiş demektir, bunu sessizce atlamak adımı
    ölçmeden yeşile çevirirdi.
    """
    if (worktree / ".git").exists():
        return False
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", f"{version}^{{commit}}"],
        cwd=CURRENT_ROOT, text=True, capture_output=True,
    )
    if probe.returncode:
        raise SystemExit(
            f"{version} etiketi bulunamadı; migration matrisi çalıştırılamaz. "
            "CI'da checkout `fetch-depth: 0` (ya da `fetch-tags`) istiyor."
        )
    worktree.parent.mkdir(parents=True, exist_ok=True)
    created = subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(worktree), version],
        cwd=CURRENT_ROOT, text=True, capture_output=True,
    )
    if created.returncode:
        raise SystemExit(
            f"{version} için worktree kurulamadı:\n{created.stderr}"
        )
    return True


def _main(args):
    created_worktrees = []
    try:
        return _run_matrix(args, created_worktrees)
    finally:
        # YALNIZCA bu koşumun kurduklarını kaldır. Önceden var olan bir
        # worktree'yi silmek, geliştiricinin elle kurduğu ortamı bozardı.
        for worktree in created_worktrees:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=CURRENT_ROOT, capture_output=True,
            )
        subprocess.run(
            ["git", "worktree", "prune"], cwd=CURRENT_ROOT, capture_output=True,
        )


def _run_matrix(args, created_worktrees):
    worktree_root = Path(args.worktree_root).resolve()
    output = Path(args.output).resolve()
    with tempfile.TemporaryDirectory(prefix="archlence-migration-matrix-") as tmp:
        root = Path(tmp)
        rows = []
        fresh_dir = root / "fresh"
        fresh_dir.mkdir()
        fresh_result = fresh_dir / "current.json"
        _subprocess(
            "current", CURRENT_ROOT, fresh_dir / "finance.db",
            fresh_dir / "profile", fresh_result,
        )
        fresh_schema = json.loads(fresh_result.read_text(encoding="utf-8"))[
            "schema"
        ]
        for patch in range(1, 9):
            version = f"v0.0.{patch}"
            worktree = worktree_root / f"archlence-audit-v00{patch}"
            if _ensure_worktree(worktree, version):
                created_worktrees.append(worktree)
            case = root / version
            case.mkdir()
            db_path = case / "finance.db"
            profile = case / "profile"
            old_result = case / "old.json"
            new_result = case / "current.json"
            _subprocess("old", worktree, db_path, profile, old_result)
            _subprocess("current", CURRENT_ROOT, db_path, profile, new_result)
            before = json.loads(old_result.read_text(encoding="utf-8"))
            after = json.loads(new_result.read_text(encoding="utf-8"))
            rows.append({
                "version": version,
                "financial_hash_before": before["financial"]["hash"],
                "financial_hash_after": after["financial"]["hash"],
                "financial_state_preserved": (
                    before["financial"]["hash"] == after["financial"]["hash"]
                ),
                "row_counts_before": {
                    name: info["rows"]
                    for name, info in before["schema"]["tables"].items()
                },
                "row_counts_after": {
                    name: info["rows"]
                    for name, info in after["schema"]["tables"].items()
                },
                "schema_matches_fresh": (
                    _schema_structure(after["schema"])
                    == _schema_structure(fresh_schema)
                ),
                "idempotent_schema": after["idempotent_schema"],
                "application_import": after["application_import"],
                "user_version_before": before["schema"]["user_version"],
                "user_version_after": after["schema"]["user_version"],
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"current_root": str(CURRENT_ROOT), "rows": rows}, indent=2),
        encoding="utf-8",
    )
    for row in rows:
        print(
            f"{row['version']}: state={row['financial_state_preserved']} "
            f"fresh_schema={row['schema_matches_fresh']} "
            f"idempotent={row['idempotent_schema']} "
            f"user_version={row['user_version_after']}"
        )
    print(output)
    return 0 if all(
        row["financial_state_preserved"] and row["idempotent_schema"]
        for row in rows
    ) else 1


def parse_args():
    parser = argparse.ArgumentParser(
        description="Populated v0.0.1-v0.0.8 DB migration/schema matrix."
    )
    parser.add_argument("--worktree-root", default="/tmp")
    parser.add_argument("--output", default="/tmp/archlence-migration-matrix.json")
    parser.add_argument("--old-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--current-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--code-root", help=argparse.SUPPRESS)
    parser.add_argument("--db", help=argparse.SUPPRESS)
    parser.add_argument("--profile", help=argparse.SUPPRESS)
    parser.add_argument("--result", help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.old_worker:
        raise SystemExit(_old_worker(parsed))
    if parsed.current_worker:
        raise SystemExit(_current_worker(parsed))
    raise SystemExit(_main(parsed))
