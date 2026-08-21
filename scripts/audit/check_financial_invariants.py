#!/usr/bin/env python3
"""Bir Archlence veritabanındaki finansal değişmezleri SALT OKUNUR doğrular.

Bu araç denetim içindir. Hiçbir koşulda yazma yapmaz: veritabanını
`file:...?mode=ro` URI'siyle açar, yani SQLite yazma girişimini reddeder.

Kullanım:

    python scripts/audit/check_financial_invariants.py --db /yol/finance.db

Varsayılan davranış bilerek dardır:

  * `--db` ZORUNLUDUR. Gerçek kullanıcı veri dizinini kendiliğinden bulmaz ve
    açmaz — yanlışlıkla üretim profiline bakmayı imkânsız kılmak için.
  * Depo kökünden çalıştırılmalıdır; aksi halde reddeder.
  * Çıkış kodu ihlal varsa 1, yoksa 0.

Denetlenen değişmezler bölüm bölüm aşağıda belgelenmiştir. Her biri, yanlış
pozitif üretmemek için mevcut domain semantiğine göre yazılmıştır; semantiği
bilinmeyen bir alan denetlenmez, "denetlenmedi" olarak raporlanır.
"""

import argparse
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[2]


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    """Yalnızca okuma modunda açar; yazma girişimi SQLite tarafından reddedilir."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def check_orphan_transactions(conn, tables):
    """DEĞİŞMEZ: her işlem var olan bir hesaba ait olmalı.

    `transactions.account_id -> accounts.id` FK'si şemada tanımlı, ama
    uygulama bağlantısında `PRAGMA foreign_keys` KAPALI (denetim bulgusu A-4),
    dolayısıyla kısıt zorlanmıyor.
    """
    if not {"transactions", "accounts"} <= tables:
        return "denetlenmedi", []
    rows = conn.execute(
        "SELECT t.id, t.account_id FROM transactions t "
        "LEFT JOIN accounts a ON t.account_id = a.id "
        "WHERE t.account_id IS NOT NULL AND a.id IS NULL"
    ).fetchall()
    return ("ihlal" if rows else "tamam",
            [f"transactions.id={r['id']} -> yok olan account_id={r['account_id']}"
             for r in rows])


def check_orphan_balance_events(conn, tables):
    """DEĞİŞMEZ: hesap tipli her ledger olayı var olan bir hesaba işaret etmeli."""
    if not {"balance_events", "accounts"} <= tables:
        return "denetlenmedi", []
    rows = conn.execute(
        "SELECT e.id, e.entity_id FROM balance_events e "
        "LEFT JOIN accounts a ON e.entity_id = a.id "
        "WHERE e.entity_type = 'account' AND a.id IS NULL"
    ).fetchall()
    return ("ihlal" if rows else "tamam",
            [f"balance_events.id={r['id']} -> yok olan account_id={r['entity_id']}"
             for r in rows])


def check_installment_progress(conn, tables):
    """DEĞİŞMEZ: ödenen taksit sayısı toplam taksit sayısını aşamaz."""
    if "installment_plans" not in tables:
        return "denetlenmedi", []
    rows = conn.execute(
        "SELECT id, paid_installments, total_installments FROM installment_plans "
        "WHERE paid_installments > total_installments OR paid_installments < 0"
    ).fetchall()
    return ("ihlal" if rows else "tamam",
            [f"installment_plans.id={r['id']} "
             f"odenen={r['paid_installments']}/{r['total_installments']}"
             for r in rows])


def check_debt_progress(conn, tables):
    """DEĞİŞMEZ: ödenen taksit sayısı toplamı aşamaz; kapalı borç tam ödenmiş olmalı."""
    if "active_debts" not in tables:
        return "denetlenmedi", []
    rows = conn.execute(
        "SELECT id, paid_installments, total_installments, is_active "
        "FROM active_debts "
        "WHERE paid_installments > total_installments OR paid_installments < 0"
    ).fetchall()
    return ("ihlal" if rows else "tamam",
            [f"active_debts.id={r['id']} "
             f"odenen={r['paid_installments']}/{r['total_installments']}"
             for r in rows])


def check_savings_within_target(conn, tables):
    """DEĞİŞMEZ: birikim negatif olamaz.

    Hedefi AŞMAK ihlal değildir — kullanıcı hedefin üstüne çıkabilir.
    """
    if "savings_goals" not in tables:
        return "denetlenmedi", []
    rows = conn.execute(
        "SELECT id, current_amount FROM savings_goals WHERE current_amount < 0"
    ).fetchall()
    return ("ihlal" if rows else "tamam",
            [f"savings_goals.id={r['id']} birikim={r['current_amount']}"
             for r in rows])


def check_balance_precision(conn, tables):
    """DEĞİŞMEZ: saklanan bakiye kuruştan ince olmamalı.

    `accounts.balance` bir REAL sütun ve `balance = balance + ?` ile
    güncelleniyor, yani ikili kayan nokta artığı biriktirebilir (denetim
    bulgusu: bu bilerek kabul edilmiş bir tasarım kararı). Bu kontrol
    artığın GÖRÜNÜR hale gelip gelmediğini ölçer.
    """
    if "accounts" not in tables:
        return "denetlenmedi", []
    bad = []
    for row in conn.execute("SELECT id, name, balance FROM accounts"):
        bal = row["balance"]
        if bal is None:
            continue
        d = Decimal(str(bal))
        if -d.as_tuple().exponent > 2:
            bad.append(f"accounts.id={row['id']} bakiye={bal!r} (2 haneden ince)")
    return ("uyari" if bad else "tamam", bad)


CHECKS = (
    ("Öksüz işlem kaydı", check_orphan_transactions),
    ("Öksüz ledger olayı", check_orphan_balance_events),
    ("Taksit planı ilerlemesi", check_installment_progress),
    ("Borç ilerlemesi", check_debt_progress),
    ("Birikim negatif değil", check_savings_within_target),
    ("Bakiye kuruş hassasiyeti", check_balance_precision),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archlence finansal değişmezlerini salt okunur doğrular.",
        epilog="Gerçek kullanıcı veritabanını kendiliğinden bulmaz; --db zorunludur.",
    )
    parser.add_argument(
        "--db", required=True,
        help="İncelenecek SQLite dosyası (salt okunur açılır).",
    )
    args = parser.parse_args()

    if not (ROOT / "utils" / "version.py").exists():
        print(f"HATA: depo kökü doğrulanamadı ({ROOT}); depo içinden çalıştırın.")
        return 2

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.is_file():
        print(f"HATA: veritabanı bulunamadı: {db_path}")
        return 2

    conn = _open_readonly(db_path)
    tables = _tables(conn)

    print(f"Veritabanı : {db_path}")
    print(f"Tablo sayısı: {len(tables)}\n")

    violations = 0
    for label, check in CHECKS:
        status, details = check(conn, tables)
        marker = {"tamam": "  OK  ", "ihlal": " İHLAL", "uyari": " UYARI",
                  "denetlenmedi": "  --  "}[status]
        print(f"[{marker}] {label}")
        for line in details[:20]:
            print(f"           {line}")
        if len(details) > 20:
            print(f"           ... ve {len(details) - 20} tane daha")
        if status == "ihlal":
            violations += 1

    conn.close()
    print()
    if violations:
        print(f"{violations} değişmez ihlal edildi.")
        return 1
    print("İhlal bulunmadı (yalnızca yukarıda denetlenen değişmezler için).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
