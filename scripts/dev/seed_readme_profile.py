#!/usr/bin/env python3
"""Build an isolated, deterministic profile for README screenshots.

The script refuses to touch a non-empty directory. It never discovers or
opens the normal Archlence profile: ``--profile`` becomes ``ARCHLENCE_HOME``
before application modules are imported.

Example:
    .venv/bin/python scripts/dev/seed_readme_profile.py \
        --profile /tmp/archlence-readme-profile --as-of 2026-08-06
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import random
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_MARKER = ".archlence-readme-sample"
RANDOM_SEED = 20260806


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="New, empty directory used as ARCHLENCE_HOME",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help="Last day in the generated year (default: today)",
    )
    return parser.parse_args()


def require_empty_profile(path: Path) -> Path:
    profile = path.expanduser().resolve()
    if profile == Path.home() or profile == PROJECT_ROOT:
        raise SystemExit("Refusing to use a home or repository directory as a sample profile.")
    if profile.exists() and any(profile.iterdir()):
        raise SystemExit(f"Profile must be empty: {profile}")
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def iter_months(start: date, end: date, day: int):
    year, month = start.year, start.month
    while True:
        current = date(year, month, min(day, calendar.monthrange(year, month)[1]))
        if current > end:
            return
        if current >= start:
            yield current
        month += 1
        if month == 13:
            month, year = 1, year + 1


def dt_on(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute))


def main():
    args = parse_args()
    profile = require_empty_profile(args.profile)
    as_of = args.as_of
    start = as_of - timedelta(days=365)

    os.environ["ARCHLENCE_HOME"] = str(profile)
    os.environ["KIVY_NO_ARGS"] = "1"
    os.chdir(PROJECT_ROOT)
    sys.path.insert(0, str(PROJECT_ROOT))

    # A README fixture must never share the desktop session's real keyring
    # entry. Force the explicit owner-only provider before utils.crypto loads.
    from utils import key_provider

    def isolated_key_provider(data_directory, *, keyring_module=None):
        fallback = key_provider.FileKeyProvider(
            os.path.join(str(data_directory), "encryption.key")
        )
        return key_provider.MigratingKeyProvider(
            None,
            fallback,
            key_provider.KeyProtectionStatus(
                "owner-only file", False,
                "OS key store unavailable; key kept in a local file with 0600 permissions.",
            ),
        )

    key_provider.create_platform_key_provider = isolated_key_provider

    from database.db import ACCOUNT, SECRET_KEY, get_connection
    from database.init_db import initialize_database
    from services.account_service import AccountService, CHECKING, CREDIT_CARD
    from utils.crypto import encrypt

    initialize_database()
    rng = random.Random(RANDOM_SEED)

    accounts = {
        "daily": AccountService.create_account(
            "Everyday Account", CHECKING, initial_balance=350_000
        ),
        "salary": AccountService.create_account(
            "Salary & Savings", CHECKING, initial_balance=325_000
        ),
        "cash": AccountService.create_account(
            "Cash Wallet", CHECKING, initial_balance=60_000
        ),
        "world": AccountService.create_account(
            "World Platinum", CREDIT_CARD, credit_limit=120_000,
            statement_date=10, card_number_full="4111111111114826",
        ),
        "bonus": AccountService.create_account(
            "Bonus Flexi", CREDIT_CARD, credit_limit=75_000,
            statement_date=23, card_number_full="5555555555557391",
        ),
    }

    # AccountService timestamps openings at runtime. Move those baseline events
    # to the beginning of the synthetic year so balance replay is meaningful.
    opening_ts = dt_on(start, 8).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            "UPDATE balance_events SET ts = ? WHERE source = 'account_opened'",
            (opening_ts,),
        )
        conn.commit()

    events: list[dict] = []

    def add(day, account, amount, kind, category, description, hour=12, minute=None):
        if not start <= day <= as_of:
            return
        events.append({
            "when": dt_on(day, hour, rng.randrange(60) if minute is None else minute),
            "account": account,
            "amount": round(float(amount), 2),
            "kind": kind,
            "category": category,
            "description": description,
        })

    # Stable income and housing history, including a visible January raise.
    for day in iter_months(start, as_of, 1):
        salary = 118_000 if day < date(as_of.year, 1, 1) else 132_000
        add(day, "salary", salary, "income", "Maaş", "Monthly salary", 8, 30)
    for day, amount, description in [
        (start + timedelta(days=72), 18_500, "Design workshop"),
        (start + timedelta(days=194), 24_000, "Consulting project"),
        (date(as_of.year, 3, 27), 36_000, "Performance bonus"),
        (as_of - timedelta(days=52), 22_000, "Quarterly research project"),
    ]:
        add(day, "salary", amount, "income", "Freelance", description, 18)

    recurring_history = [
        (1, "salary", 31_500, "Ev Kirası", "Rent"),
        (5, "daily", 1_480, "Elektrik", "Electricity bill"),
        (7, "daily", 410, "Su", "Water bill"),
        (9, "daily", 1_350, "Doğalgaz", "Natural gas bill"),
        (11, "daily", 690, "İnternet", "Fiber internet"),
        (12, "daily", 510, "Cep Telefonu", "Mobile plan"),
        (14, "world", 229.99, "Dijital Platformlar", "Netflix"),
        (17, "bonus", 99.99, "Dijital Platformlar", "Spotify"),
        (19, "world", 149.99, "Dijital Abonelik", "iCloud+"),
        (21, "daily", 1_650, "Spor Salonu", "Neighborhood gym"),
    ]
    for due_day, account, base, category, description in recurring_history:
        for day in iter_months(start, as_of, due_day):
            seasonal = 1.0
            if category == "Doğalgaz":
                seasonal = 2.2 if day.month in (11, 12, 1, 2, 3) else 0.45
            amount = base * seasonal
            if category in ("Elektrik", "Su"):
                amount *= rng.uniform(0.88, 1.14)
            add(day, account, amount, "expense", category, description, 7)

    # Daily life: around 600 varied records spread over the full year.
    daily_pool = [
        ("Süpermarket", "Grocery market", 260, 1_950, 0.62),
        ("Dışarıda Yemek", "Lunch or dinner", 240, 1_150, 0.27),
        ("Toplu Taşıma", "Transit card", 40, 170, 0.29),
        ("Akaryakıt", "Fuel", 1_100, 2_250, 0.11),
        ("İlaç/Eczane", "Pharmacy", 120, 1_050, 0.055),
        ("Kitap/Kırtasiye", "Books and stationery", 180, 950, 0.052),
        ("Kişisel Bakım", "Personal care", 260, 1_250, 0.052),
        ("Evcil Hayvan", "Pet supplies", 280, 1_180, 0.045),
        ("Sinema/Tiyatro", "Cinema or theatre", 300, 1_100, 0.035),
        ("Kıyafet", "Clothing", 650, 3_900, 0.04),
        ("Paket Servis", "Food delivery", 260, 920, 0.075),
    ]
    card_monthly = defaultdict(float)
    day = start
    while day <= as_of:
        for category, description, low, high, probability in daily_pool:
            if rng.random() >= probability:
                continue
            if category in ("Toplu Taşıma", "İlaç/Eczane"):
                account = "cash" if rng.random() < 0.35 else "daily"
            else:
                account = rng.choices(
                    ["daily", "world", "bonus", "cash"],
                    weights=[44, 29, 20, 7],
                )[0]
            amount = rng.uniform(low, high)
            add(day, account, amount, "expense", category, description, rng.randint(9, 21))
            if account in ("world", "bonus"):
                card_monthly[(account, day.year, day.month)] += amount
        day += timedelta(days=1)

    # Recurring candidate signals: regular but intentionally not tracked yet.
    for description, amount, due_day in [
        ("MUBI.COM", 129.99, 8),
        ("Storytel", 169.99, 26),
    ]:
        candidate_start = max(start, as_of - timedelta(days=165))
        for day in iter_months(candidate_start, as_of, due_day):
            add(day, "bonus", amount, "expense", "Dijital Abonelik", description, 10)
            card_monthly[("bonus", day.year, day.month)] += amount

    # Education, health, travel and technology create realistic peaks and an
    # anomaly among several ordinary technology purchases.
    for day, account, amount, category, description in [
        (start + timedelta(days=49), "world", 8_900, "Okul/Kurs", "Language course"),
        (start + timedelta(days=131), "daily", 4_750, "Hastane", "Annual health check"),
        (start + timedelta(days=219), "world", 18_400, "Tatil/Konaklama", "Weekend trip"),
        (start + timedelta(days=240), "salary", 28_000, "Tatil/Konaklama", "Summer travel booking"),
        (as_of - timedelta(days=78), "world", 1_450, "Oyun/Uygulama", "USB-C hub"),
        (as_of - timedelta(days=72), "bonus", 980, "Oyun/Uygulama", "Charging stand"),
        (as_of - timedelta(days=61), "world", 1_890, "Oyun/Uygulama", "Mechanical keyboard"),
        (as_of - timedelta(days=54), "world", 1_120, "Oyun/Uygulama", "Laptop sleeve"),
        (as_of - timedelta(days=44), "bonus", 2_250, "Oyun/Uygulama", "Backup drive"),
        (as_of - timedelta(days=36), "bonus", 1_640, "Oyun/Uygulama", "Webcam light"),
        (as_of - timedelta(days=28), "world", 890, "Oyun/Uygulama", "Cable organizer"),
        (as_of - timedelta(days=17), "world", 28_900, "Oyun/Uygulama", "Ergonomic monitor"),
    ]:
        add(day, account, amount, "expense", category, description, 15)
        if account in ("world", "bonus"):
            card_monthly[(account, day.year, day.month)] += amount

    # Debt instalments and active debt definitions agree with each other.
    debt_history = [
        ("Vehicle loan", 12_500, 6, start + timedelta(days=5)),
        ("Laptop instalment", 3_200, 16, start + timedelta(days=122)),
        ("Education loan", 4_800, 28, start + timedelta(days=243)),
    ]
    for _name, amount, due_day, debt_start in debt_history:
        for day in iter_months(debt_start, as_of, due_day):
            add(day, "salary", amount, "expense", "Kredi Taksiti", _name, 7, 15)

    # Asset cash flows and active positions. The transaction descriptions are
    # the same shape the application uses for its history parser.
    assets = [
        ("Turkish Airlines", "THYAO", "Hisse", 252.0, 120.0, 318.0, start + timedelta(days=38)),
        ("Aselsan", "ASELS", "Hisse", 73.0, 250.0, 92.0, start + timedelta(days=82)),
        ("BİM Stores", "BIMAS", "Hisse", 425.0, 80.0, 512.0, start + timedelta(days=143)),
        ("Şişecam", "SISE", "Hisse", 55.0, 450.0, 49.8, start + timedelta(days=206)),
        ("Bitcoin", "BTC-USD", "Kripto", 2_700_000.0, 0.025, 3_350_000.0, start + timedelta(days=64)),
        ("Ethereum", "ETH-USD", "Kripto", 115_000.0, 0.4, 142_000.0, start + timedelta(days=171)),
        ("Gram Gold", "GC=F", "Altın", 3_180.0, 35.0, 4_210.0, start + timedelta(days=19)),
        ("US Dollar", "USDTRY=X", "Döviz", 34.5, 2_500.0, 41.2, start + timedelta(days=108)),
        ("Euro", "EURTRY=X", "Döviz", 37.8, 1_200.0, 47.3, start + timedelta(days=235)),
    ]
    for name, code, asset_type, price, quantity, _current, bought in assets:
        value = price * quantity
        description = (
            f"{name} ({code}) alındı — {quantity:g} adet, "
            f"birim fiyat {price:,.2f} ₺"
        )
        add(bought, "salary", value, "expense", "Varlık Alımı", description, 11)

    # Two completed round trips enrich asset history without pretending they
    # remain open positions.
    for name, code, quantity, buy_price, sell_price, bought, sold in [
        ("Koza Gold", "KOZAA", 180, 26.4, 34.1, start + timedelta(days=31), start + timedelta(days=231)),
        ("Technology Fund", "AFT", 420, 0.49, 0.63, start + timedelta(days=96), start + timedelta(days=302)),
    ]:
        add(bought, "salary", buy_price * quantity, "expense", "Varlık Alımı",
            f"{name} ({code}) alındı — {quantity:g} adet, birim fiyat {buy_price:,.2f} ₺", 11)
        profit = (sell_price - buy_price) * quantity
        add(sold, "salary", sell_price * quantity, "income", "Varlık Satışı",
            f"{name} ({code}) satıldı — {quantity:g} adet, birim fiyat {sell_price:,.2f} ₺ (K/Z: +{profit:,.2f} ₺)", 14)

    # Pay the previous month's card spending on each statement cycle. The
    # source-account movement is recorded as a transfer ledger event while the
    # card receives a visible payment transaction, avoiding double-counting a
    # transfer as new consumption in reports.
    for (account, year, month), total in sorted(card_monthly.items()):
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        payment_day = 12 if account == "world" else 25
        paid_on = next_month.replace(day=payment_day)
        if paid_on <= as_of:
            events.append({
                "when": dt_on(paid_on, 9, 15),
                "account": account,
                "source": "salary",
                "amount": round(total, 2),
                "kind": "card_payment",
                "category": "Kredi Kartı",
                "description": "Statement payment",
            })

    events.sort(key=lambda item: item["when"])

    def insert_balance_event(cursor, ts, account_id, delta, result, source, ref_id=None):
        cursor.execute(
            """INSERT INTO balance_events
               (ts, entity_type, entity_id, delta, resulting_value, source, ref_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ts, ACCOUNT, account_id, delta, result, source, ref_id),
        )

    with get_connection() as conn:
        cursor = conn.cursor()
        balances = {
            row["id"]: float(row["balance"] or 0)
            for row in cursor.execute("SELECT id, balance FROM accounts")
        }
        for item in events:
            ts = item["when"].strftime("%Y-%m-%d %H:%M:%S")
            amount = item["amount"]
            account_id = accounts[item["account"]]
            if item["kind"] == "card_payment":
                source_id = accounts[item["source"]]
                amount = min(amount, max(0.0, -balances[account_id]))
                if amount <= 0:
                    continue
                balances[source_id] -= amount
                cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (balances[source_id], source_id))
                insert_balance_event(cursor, ts, source_id, -amount, balances[source_id], "card_payment_source")
                tx_type, delta = "payment", amount
            else:
                tx_type = item["kind"]
                delta = amount if tx_type == "income" else -amount

            cursor.execute(
                """INSERT INTO transactions
                   (account_id, amount, type, category, description,
                    transaction_date, status, execution_date)
                   VALUES (?, ?, ?, ?, ?, ?, 'completed', NULL)""",
                (
                    account_id,
                    encrypt(str(round(amount, 2)), SECRET_KEY),
                    tx_type,
                    item["category"],
                    encrypt(item["description"], SECRET_KEY),
                    ts,
                ),
            )
            tx_id = cursor.lastrowid
            balances[account_id] += delta
            cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (balances[account_id], account_id))
            insert_balance_event(cursor, ts, account_id, delta, balances[account_id], "sample_transaction", tx_id)

        # Make the latest dashboard list visibly current and varied.
        for offset, account, amount, kind, category, description, hour in [
            (0, "daily", 785.40, "expense", "Süpermarket", "Weekly groceries", 18),
            (0, "cash", 95.00, "expense", "Toplu Taşıma", "Transit card", 9),
            (0, "world", 420.00, "expense", "Dışarıda Yemek", "Team lunch", 13),
            (1, "daily", 680.00, "expense", "İlaç/Eczane", "Pharmacy", 17),
        ]:
            tx_day = as_of - timedelta(days=offset)
            account_id = accounts[account]
            ts = dt_on(tx_day, hour, 20).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """INSERT INTO transactions
                   (account_id, amount, type, category, description, transaction_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'completed')""",
                (account_id, encrypt(str(amount), SECRET_KEY), kind, category,
                 encrypt(description, SECRET_KEY), ts),
            )
            delta = amount if kind == "income" else -amount
            balances[account_id] += delta
            cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (balances[account_id], account_id))
            insert_balance_event(cursor, ts, account_id, delta, balances[account_id], "sample_transaction", cursor.lastrowid)

        # Active portfolio and a fresh, offline price snapshot.
        for name, code, asset_type, price, quantity, current, bought in assets:
            cursor.execute(
                """INSERT INTO active_assets
                   (asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, code, asset_type, encrypt(str(price), SECRET_KEY),
                 encrypt(str(quantity), SECRET_KEY), dt_on(bought, 11).strftime("%Y-%m-%d %H:%M:%S")),
            )
            cursor.execute(
                """INSERT OR REPLACE INTO asset_price_cache
                   (symbol, price, asset_type, updated_at, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (code, current, asset_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Generated sample snapshot"),
            )

        # Current debt cards.
        debts = [
            ("Vehicle loan", 375_000, 12_500, 30, 14, 1, 6),
            ("Laptop instalment", 38_400, 3_200, 12, 7, 0, 16),
            ("Education loan", 57_600, 4_800, 12, 9, 1, 28),
        ]
        for name, total, monthly, instalments, paid, auto, due_day in debts:
            cursor.execute(
                """INSERT INTO active_debts
                   (debt_name, total_amount, monthly_payment, total_installments,
                    paid_installments, is_active, is_auto_pay, auto_pay_day, last_auto_pay_date)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (encrypt(name, SECRET_KEY), encrypt(str(total), SECRET_KEY),
                 encrypt(str(monthly), SECRET_KEY), instalments, paid, auto,
                 due_day, (as_of.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")),
            )

        # Active subscriptions/income with several upcoming dates in the next week.
        recurring = [
            ("Monthly salary", 132_000, "Maaş", 1, "salary", "income"),
            ("Rent", 31_500, "Ev Kirası", 1, "salary", "expense"),
            ("Netflix", 229.99, "Dijital Platformlar", 4, "world", "expense"),
            ("Spotify", 99.99, "Dijital Platformlar", 6, "bonus", "expense"),
            ("iCloud+", 149.99, "Dijital Abonelik", 9, "world", "expense"),
            ("Fiber internet", 690, "İnternet", 3, "daily", "expense"),
            ("Mobile plan", 510, "Cep Telefonu", 12, "daily", "expense"),
            ("Neighborhood gym", 1_650, "Spor Salonu", 14, "daily", "expense"),
        ]
        for name, amount, category, offset, account, tx_type in recurring:
            next_due = as_of + timedelta(days=offset)
            cursor.execute(
                """INSERT INTO recurring_payments
                   (name, amount, category, frequency, next_due_date,
                    recurrence_day, auto_deduct, is_active, account_id, transaction_type)
                   VALUES (?, ?, ?, 'monthly', ?, ?, 0, 1, ?, ?)""",
                (encrypt(name, SECRET_KEY), encrypt(str(amount), SECRET_KEY), category,
                 next_due.isoformat(), next_due.day, accounts[account], tx_type),
            )

        # Twelve months of budget history plus the current plan.
        budget_items = [
            ("income", "Expected salary", 132_000, "Maaş"),
            ("expense", "Housing", 31_500, "Ev Kirası"),
            ("expense", "Groceries", 16_000, "Süpermarket"),
            ("expense", "Transport", 7_000, "Akaryakıt"),
            ("expense", "Dining", 6_500, "Dışarıda Yemek"),
            ("expense", "Health", 3_500, "İlaç/Eczane"),
            ("expense", "Education", 5_000, "Okul/Kurs"),
            ("expense", "Entertainment", 3_000, "Sinema/Tiyatro"),
            ("expense", "Investing", 15_000, "Varlık Alımı"),
        ]
        month_cursor = start.replace(day=1)
        while month_cursor <= as_of.replace(day=1):
            for kind, name, amount, category in budget_items:
                cursor.execute(
                    """INSERT INTO monthly_budget_plan
                       (type, name, amount, target_month, target_year,
                        category_name, rollover_enabled, is_template, alert_threshold_pct)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, 80)""",
                    (kind, name, amount, month_cursor.month, month_cursor.year,
                     category, int(category in ("Süpermarket", "Varlık Alımı"))),
                )
            next_month = month_cursor.month % 12 + 1
            next_year = month_cursor.year + (month_cursor.month == 12)
            month_cursor = date(next_year, next_month, 1)

        goals = [
            ("Emergency fund", 300_000, 212_000, as_of + timedelta(days=210)),
            ("Japan trip", 180_000, 94_500, as_of + timedelta(days=330)),
            ("Home office refresh", 85_000, 53_000, as_of + timedelta(days=120)),
        ]
        for name, target, current, target_date in goals:
            cursor.execute(
                """INSERT INTO savings_goals
                   (goal_name, target_amount, current_amount, target_date, status)
                   VALUES (?, ?, ?, ?, 'aktif')""",
                (encrypt(name, SECRET_KEY), target, current, target_date.isoformat()),
            )
            goal_id = cursor.lastrowid
            cursor.execute(
                """INSERT INTO balance_events
                   (ts, entity_type, entity_id, delta, resulting_value, source)
                   VALUES (?, 'savings_goal', ?, ?, ?, 'savings_goal_created')""",
                (opening_ts, goal_id, current, current),
            )

        for index, day in enumerate(iter_months(start, as_of, 1)):
            score = min(86, 72 + index * 0.9 + rng.uniform(-2.2, 2.2))
            cursor.execute(
                """INSERT OR REPLACE INTO financial_health_history
                   (date, score, breakdown_json) VALUES (?, ?, ?)""",
                (day.isoformat(), round(score, 1), json.dumps({
                    "savings_rate": round(70 + index * 0.8, 1),
                    "debt_ratio": round(63 + index * 0.7, 1),
                    "volatility": round(76 + index * 0.4, 1),
                })),
            )
        conn.commit()

    data_dir = profile / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "archlence_config.json").write_text(
        json.dumps({
            "language": {"code": "en"},
            "display": {"style": "Dark"},
            "theme": {"name": "premium"},
        }, indent=2),
        encoding="utf-8",
    )
    (profile / SAMPLE_MARKER).write_text(
        f"Synthetic README profile generated through {as_of.isoformat()}\n",
        encoding="utf-8",
    )

    with get_connection() as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "accounts", "transactions", "active_assets", "active_debts",
                "recurring_payments", "savings_goals", "monthly_budget_plan",
            )
        }
        account_rows = conn.execute(
            "SELECT name, balance FROM accounts ORDER BY id"
        ).fetchall()

    print(f"Created isolated sample profile: {profile}")
    print(f"Synthetic period: {start.isoformat()} through {as_of.isoformat()}")
    print("Rows: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for row in account_rows:
        print(f"  {row['name']}: {row['balance']:,.2f} TRY")


if __name__ == "__main__":
    main()
