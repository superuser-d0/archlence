"""TANI ARACI — kalıcı kapı DEĞİL. `REAL` sütununda biriken sapmayı ölçer.

NEDEN VAR: `adjust_account_balance` bakiyeyi `UPDATE accounts SET balance =
balance + ?` ile günceller, yani toplama Python'da değil SQLite'ın `REAL`
sütununda yapılıyor. Python tarafı tamamen `Decimal`'a geçse bile bu birikim
ikili kayan noktada kalır.

Bu aracın cevapladığı soru "REAL kusurlu mu?" DEĞİL — o zaten biliniyor.
Sorulan şu: **temsil hatası, uygulamanın verdiği İŞ KARARINI değiştirebiliyor
mu?** Ham bakiye 99,999999999x iken kullanıcı 100 TL harcayamıyorsa bu bir
gösterim sorunundan çok daha ciddidir.

Bilerek `tests/` altında değil ve CI kapısı değil: mevcut şema altında "ham
bakiye Decimal'a birebir eşit olmalı" YANLIŞ bir beklenti olurdu ve kapıyı
kalıcı kırmızıya çevirirdi. Kalıcı test yalnız uygulamanın gerçekten garanti
ettiği iş invariant'ını sınamalı — o `tests/test_real_balance_invariants.py`
içinde.

Çalıştırma:
    python scripts/audit/measure_real_column_drift.py
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest import mock


def _accumulate(step: str, times: int, sign: int = 1) -> float:
    """Uygulamanın kullandığı SQL kalıbının ta kendisi, izole bir tabloda."""
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
        conn.execute("INSERT INTO a (id, balance) VALUES (1, 0)")
        delta = sign * float(step)
        for _ in range(times):
            conn.execute("UPDATE a SET balance = balance + ? WHERE id=1", (delta,))
        return conn.execute("SELECT balance FROM a WHERE id=1").fetchone()[0]


def _round_trip(step: str, times: int) -> float:
    """Aynı tutarı ekleyip sonra çıkar: simetri sapması (transfer benzeri)."""
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
        conn.execute("INSERT INTO a (id, balance) VALUES (1, 0)")
        delta = float(step)
        for _ in range(times):
            conn.execute("UPDATE a SET balance = balance + ? WHERE id=1", (delta,))
        for _ in range(times):
            conn.execute("UPDATE a SET balance = balance - ? WHERE id=1", (delta,))
        return conn.execute("SELECT balance FROM a WHERE id=1").fetchone()[0]


def measure_accumulation():
    from utils.financial_decimal import fiat

    print("\n=== 1. Birikimli sapma: balance += 0.01 ===")
    print(f"{'n':>8} {'ham REAL':>24} {'tam':>10} {'mutlak hata':>14} {'fiat(ham)':>12} {'fiat dogru mu':>14}")
    for times in (10, 100, 1000, 10000, 100000):
        raw = _accumulate("0.01", times)
        exact = Decimal("0.01") * times
        error = abs(Decimal(repr(raw)) - exact)
        quantised = fiat(raw)
        print(f"{times:>8} {raw!r:>24} {str(exact):>10} {error:>14.3e} "
              f"{str(quantised):>12} {str(quantised == exact):>14}")

    print("\n=== 2. Simetri: n kez +0.01, sonra n kez -0.01 (beklenen 0) ===")
    print(f"{'n':>8} {'ham REAL':>24} {'fiat(ham)':>12}")
    for times in (10, 1000, 10000, 100000):
        raw = _round_trip("0.01", times)
        print(f"{times:>8} {raw!r:>24} {str(fiat(raw)):>12}")

    print("\n=== 3. Karışık isaret: +0.07 ve -0.03 donusumlu, 10.000 tur ===")
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
        conn.execute("INSERT INTO a (id, balance) VALUES (1, 0)")
        for _ in range(10000):
            conn.execute("UPDATE a SET balance = balance + ? WHERE id=1", (0.07,))
            conn.execute("UPDATE a SET balance = balance - ? WHERE id=1", (0.03,))
        raw = conn.execute("SELECT balance FROM a WHERE id=1").fetchone()[0]
    exact = (Decimal("0.07") - Decimal("0.03")) * 10000
    print(f"  ham={raw!r}  tam={exact}  hata={abs(Decimal(repr(raw)) - exact):.3e}  fiat={fiat(raw)}")


def measure_business_decisions():
    """ASIL SORU: sapma bir iş kararını değiştiriyor mu?

    Gerçek servisler, gerçek şema, geçici profil. Her senaryoda bakiye
    ÖNCE sapma üretecek kadar çok mutasyonla oluşturuluyor, SONRA sınır
    kararı deneniyor.
    """
    tempdir = tempfile.TemporaryDirectory(prefix="archlence-realaudit-")
    root = Path(tempdir.name)
    db_path = root / "finance.db"
    key = os.urandom(32)

    db_patch = mock.patch("database.db.DB_NAME", str(db_path))
    key_patch = mock.patch("utils.crypto._get_aead_key", return_value=key)
    db_patch.start()
    key_patch.start()
    try:
        from database.init_db import initialize_database
        initialize_database()

        from database.db import get_connection
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        print("\n=== 4. Karar sinirlari (gercek servisler) ===")

        # --- 4a. Vadesiz hesap: 10.000 x 0,01 birikimle tam 100,00 olmali
        account_id = AccountService.create_account("Drift", "checking",
                                                   initial_balance=0.0)
        with closing(get_connection()) as conn, conn:
            for _ in range(10000):
                conn.execute("UPDATE accounts SET balance = balance + ? WHERE id=?",
                             (0.01, account_id))
        raw = _raw_balance(account_id)
        shown = AccountService.get_account(account_id)["balance"]
        print(f"  4a vadesiz  ham={raw!r}  gosterilen={shown}  (beklenen 100.0)")

        # --- 4b. Tam bakiye kadar harcama kabul ediliyor mu?
        allowed, reason = AccountService.check_spending_allowed(
            account_id, 100.00, "expense")
        print(f"  4b tam-tutar harcama izni={allowed}  gerekce={reason!r}")

        # --- 4c. Kredi karti: limitin TAMAMI kadar harcama
        card_id = AccountService.create_account("Drift card", "credit_card",
                                                credit_limit=100.0)
        with closing(get_connection()) as conn, conn:
            for _ in range(5000):          # 5000 x 0,01 = 50,00 borc
                conn.execute("UPDATE accounts SET balance = balance - ? WHERE id=?",
                             (0.01, card_id))
        raw_card = _raw_balance(card_id)
        card = AccountService.get_account(card_id)
        print(f"  4c kart ham={raw_card!r}  borc={card['debt']}  "
              f"kullanilabilir={card['available_limit']}")
        allowed, reason = AccountService.check_spending_allowed(
            card_id, 50.00, "expense")
        print(f"     kalan limitin TAMAMI kadar harcama izni={allowed}  gerekce={reason!r}")
        allowed_over, reason_over = AccountService.check_spending_allowed(
            card_id, 50.01, "expense")
        print(f"     bir kurus FAZLASI izni={allowed_over}  (False olmali)")

        # --- 4d. Gercek islem yolu: tam tutar yazilabiliyor mu?
        try:
            TransactionService.add_transaction(
                card_id, 50.00, "expense", "Audit", "sinir", detect_subscription=False)
            print("  4d gercek islem: KABUL EDILDI")
        except ValueError as exc:
            print(f"  4d gercek islem: REDDEDILDI -> {exc}")

        # --- 4e. Birikim hedefi: gosterilen tutarin TAMAMINI cekme
        from services.savings_service import SavingsService
        goal_id = SavingsService.create_goal("Drift goal", 1000.0)
        with closing(get_connection()) as conn, conn:
            for _ in range(30000):        # 30.000 x 0,01 = 300,00
                conn.execute(
                    "UPDATE savings_goals SET current_amount = current_amount + ? WHERE id=?",
                    (0.01, goal_id))
        raw_goal = _raw_goal(goal_id)
        print(f"  4e hedef ham={raw_goal!r}  (beklenen 300.0)")
        try:
            SavingsService.withdraw_from_goal(goal_id, 300.00, account_id)
            print("     gosterilen tutarin TAMAMINI cekme: KABUL EDILDI")
        except ValueError as exc:
            print(f"     gosterilen tutarin TAMAMINI cekme: REDDEDILDI -> {exc}")
    finally:
        key_patch.stop()
        db_patch.stop()
        tempdir.cleanup()


def _raw_balance(account_id):
    from database.db import get_connection
    with closing(get_connection()) as conn, conn:
        return conn.execute("SELECT balance FROM accounts WHERE id=?",
                            (account_id,)).fetchone()[0]


def _raw_goal(goal_id):
    from database.db import get_connection
    with closing(get_connection()) as conn, conn:
        return conn.execute("SELECT current_amount FROM savings_goals WHERE id=?",
                            (goal_id,)).fetchone()[0]


if __name__ == "__main__":
    measure_accumulation()
    measure_business_decisions()
