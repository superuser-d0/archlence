"""
generate_mock_data.py — Archlence stres testi için 1 yıllık gerçekçi kullanım verisi üretir.

Çalıştırma:  .venv/bin/python generate_mock_data.py

Tasarım notları:
- SADECE EKLEME yapar (INSERT); mevcut hiçbir kaydı silmez/değiştirmez.
  Çalıştırmadan önce finance.db yedeği alınması önerilir (bkz. README/rapor).
- db.py fonksiyonları tarih parametresi kabul ettiği yerde doğrudan kullanılır
  (insert_asset, insert_recurring_payment, insert_debt, update_debt_*).
  TransactionService.add_transaction tarihi datetime.now() ile sabitlediği
  için, geriye dönük işlemler aynı INSERT şablonu + encrypt() ile buradan
  yazılır (şifreleme formatı birebir aynı).
- Rastgelelik sabit tohumludur (seed=2026): betik her çalıştığında aynı
  veri setini üretir — hata ayıklama tekrarlanabilir kalır.
- Tüm işlemler uygulamanın kullandığı account_id=1 üzerinden yazılır.
"""
import random
import sys
from datetime import date, timedelta

from database.db import (
    DB_NAME, SECRET_KEY, get_connection,
    insert_asset, insert_debt, insert_recurring_payment,
    update_debt_auto_pay, update_debt_last_auto_pay, update_debt_progress,
)
from utils.crypto import encrypt
from utils.errors import ArchlenceError

random.seed(2026)

TODAY = date(2026, 7, 19)
START = TODAY - timedelta(days=365)
ACCOUNT_ID = 1

MOCK_TAG = "[MOCK]"


def format_price_tl(price):
    """mixins/asset_mixin.py ile aynı Türkçe biçim: 1234.5 → '1.234,50 ₺'"""
    return f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"


def add_tx(cursor, amount, tx_type, category, description, d, hour=None, minute=None):
    """TransactionService.add_transaction ile birebir aynı INSERT — sadece tarih
    parametrik. amount/description şifreli, type/category düz metin (JOIN'ler için)."""
    hour = hour if hour is not None else random.randint(9, 21)
    minute = minute if minute is not None else random.randint(0, 59)
    tx_date = f"{d.isoformat()} {hour:02d}:{minute:02d}:{random.randint(0, 59):02d}"
    cursor.execute(
        """INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ACCOUNT_ID, encrypt(str(amount), SECRET_KEY), tx_type, category,
         encrypt(f"{description} {MOCK_TAG}", SECRET_KEY), tx_date),
    )


def month_days(year, month):
    import calendar
    return calendar.monthrange(year, month)[1]


def clamp_day(year, month, day):
    return min(day, month_days(year, month))


def iter_monthly(start_d, end_d, day):
    """start..end aralığında her ayın `day`. gününü (ay sonuna kırparak) üretir."""
    y, m = start_d.year, start_d.month
    while True:
        d = date(y, m, clamp_day(y, m, day))
        if d > end_d:
            return
        if d >= start_d:
            yield d
        m += 1
        if m > 12:
            m, y = 1, y + 1


def main():
    """Bağlantıyı her çıkış yolunda kapatır.

    `database/init_db.py::initialize_database` ile aynı kalıp ve aynı gerekçe:
    gövde ayrı bir fonksiyonda ki `try/finally` tek yerde dursun ve 180 satır
    yeniden girintilenmesin. Bu bir geliştirici aracı, paketlenmiyor — ama
    `tests/test_connection_ownership_contract.py` sahiplik sözleşmesini
    depo genelinde arıyor ve tek istisna bırakmak kuralı yumuşatırdı.
    """
    conn = get_connection()
    try:
        _main(conn)
    finally:
        conn.close()


def _main(conn):
    cursor = conn.cursor()
    n_tx = 0


    for d in iter_monthly(START, TODAY, 1):
        salary = 85_000.0 if d < date(2026, 1, 1) else 110_500.0
        add_tx(cursor, salary, "income", "Maaş", "Aylık maaş", d, hour=8, minute=30)
        n_tx += 1
    # Occasional income: two freelance payments and one bonus
    for d, amt, cat, desc in [
        (date(2025, 10, 14), 22_500.0, "Freelance", "Web sitesi projesi"),
        (date(2026, 3, 6), 18_000.0, "Freelance", "Danışmanlık raporu"),
        (date(2025, 12, 28), 42_500.0, "Prim", "Yıl sonu primi"),
    ]:
        add_tx(cursor, amt, "income", cat, desc, d)
        n_tx += 1


    daily_pool = [
        ("Süpermarket", 250, 2200, 0.75),
        ("Dışarıda Yemek", 180, 950, 0.35),
        ("Paket Servis", 150, 600, 0.25),
        ("Akaryakıt", 900, 2000, 0.18),
        ("Toplu Taşıma", 30, 120, 0.30),
        ("Kişisel Bakım", 100, 700, 0.08),
        ("Sinema/Tiyatro", 200, 800, 0.06),
        ("Kıyafet", 400, 3500, 0.07),
        ("İlaç/Eczane", 80, 900, 0.07),
        ("Oyun/Uygulama", 50, 600, 0.04),
        ("Evcil Hayvan", 150, 900, 0.05),
        ("Kitap/Kırtasiye", 100, 500, 0.04),
    ]
    d = START
    while d <= TODAY:
        for cat, lo, hi, p in daily_pool:
            if random.random() < p:
                add_tx(cursor, round(random.uniform(lo, hi), 2), "expense", cat, cat, d)
                n_tx += 1
        d += timedelta(days=1)


    for cat, lo, hi, day in [
        ("Elektrik", 800, 2400, 5), ("Su", 250, 700, 7), ("Doğalgaz", 300, 4500, 9),
        ("İnternet", 549.9, 549.9, 11), ("Cep Telefonu", 420, 420, 12),
    ]:
        for md in iter_monthly(START, TODAY, day):

            if cat == "Doğalgaz":
                amt = random.uniform(2500, 4500) if md.month in (11, 12, 1, 2, 3) else random.uniform(300, 700)
            else:
                amt = random.uniform(lo, hi)
            add_tx(cursor, round(amt, 2), "expense", cat, f"{cat} faturası", md)
            n_tx += 1


    add_tx(cursor, 64_990.0, "expense", "Ev Eşyası", "Yeni TV ve süpürge", date(2025, 12, 20))
    add_tx(cursor, 38_500.0, "expense", "Hobiler", "Yılbaşı alışverişi", date(2025, 12, 27))
    add_tx(cursor, 72_000.0, "expense", "Tatil/Konaklama", "Bodrum yazlık tatili", date(2026, 6, 12))
    add_tx(cursor, 21_400.0, "expense", "Dışarıda Yemek", "Tatil yeme-içme", date(2026, 6, 18))
    n_tx += 4


    conn.commit()
    recurring_defs = [
        ("Kira", 18_000.0, "Ev Kirası", 1, "2026-08-01"),
        ("Netflix", 229.99, "Dijital Platformlar", 24, "2026-07-24"),
        ("Spotify", 59.99, "Dijital Platformlar", 21, "2026-07-21"),
        ("Spor Salonu Üyeliği", 1_250.0, "Spor Salonu", 15, "2026-08-15"),
    ]
    for name, amount, category, day, next_due in recurring_defs:
        for md in iter_monthly(START, TODAY, day):
            add_tx(cursor, amount, "expense", category, f"{name} (Otomatik)", md, hour=6, minute=0)
            n_tx += 1
        conn.commit()
        insert_recurring_payment(name, amount, category, "monthly", next_due,
                                 auto_deduct=True, account_id=ACCOUNT_ID)


    def last_debt_id():
        cursor.execute("SELECT MAX(id) m FROM active_debts")
        return cursor.fetchone()["m"]


    conn.commit()
    insert_debt(f"Telefon Taksiti {MOCK_TAG}", 24_000.0, 2_000.0, 12)
    finished_id = last_debt_id()
    update_debt_progress(finished_id, 12, is_active=0)
    for md in iter_monthly(START, date(2025, 12, 31), 10):
        add_tx(cursor, 2_000.0, "expense", "Kredi Taksiti",
               "Telefon Taksiti (1 Taksit Ödemesi)", md)
        n_tx += 1


    conn.commit()
    insert_debt(f"Taşıt Kredisi {MOCK_TAG}", 480_000.0, 20_000.0, 24)
    active_id = last_debt_id()
    update_debt_progress(active_id, 11, is_active=1)
    update_debt_auto_pay(active_id, True, 5)
    update_debt_last_auto_pay(active_id, "2026-07")
    for md in iter_monthly(date(2025, 9, 1), TODAY, 5):
        add_tx(cursor, 20_000.0, "expense", "Kredi Taksiti",
               "Taşıt Kredisi (Otomatik Taksit Ödemesi)", md, hour=7, minute=15)
        n_tx += 1


    assets = [

        ("Türk Hava Yolları", "THYAO", "Hisse", 285.50, 100, date(2025, 9, 12)),
        ("Aselsan", "ASELS", "Hisse", 62.30, 150, date(2025, 11, 3)),
        ("Şişecam", "SISE", "Hisse", 39.80, 500, date(2026, 2, 18)),
        ("Bitcoin", "BTC-USD", "Kripto", 2_750_000.0, 0.015, date(2025, 10, 5)),
        ("Ethereum", "ETH-USD", "Kripto", 145_000.0, 0.25, date(2026, 1, 22)),
        ("Gram Altın", "GC=F", "Altın", 2_450.0, 20, date(2025, 8, 20)),
        ("Çeyrek Altın", "GOLD-CEYREK", "Altın", 4_300.0, 5, date(2026, 3, 14)),
        ("Amerikan Doları", "USDTRY=X", "Döviz", 34.20, 1500, date(2025, 12, 10)),
        ("Euro", "EURTRY=X", "Döviz", 37.90, 800, date(2026, 4, 25)),
    ]
    conn.commit()
    for name, code, a_type, price, qty, buy_d in assets:
        insert_asset(name, code, a_type, price, qty,
                     purchase_date=f"{buy_d.isoformat()} 11:{random.randint(10,59):02d}:00")
        desc = (f"{name} ({code}) alındı — {qty:g} adet, "
                f"birim fiyat {format_price_tl(price)}")
        add_tx(cursor, round(price * qty, 2), "expense", "Varlık Alımı", desc, buy_d, hour=11)
        n_tx += 1
        conn.commit()


    buy_d, sell_d = date(2025, 8, 25), date(2026, 5, 8)
    add_tx(cursor, 5_100.0, "expense", "Varlık Alımı",
           f"Koza Altın (KOZAA) alındı — 200 adet, birim fiyat {format_price_tl(25.50)}",
           buy_d, hour=10)
    add_tx(cursor, 6_340.0, "income", "Varlık Satışı",
           f"Koza Altın (KOZAA) satıldı — 200 adet, birim fiyat {format_price_tl(31.70)} "
           f"(K/Z: +{format_price_tl(1240.0)})",
           sell_d, hour=14)
    n_tx += 2

    conn.commit()


    from utils.crypto import decrypt
    cursor.execute("""
        SELECT strftime('%Y-%m', transaction_date) ym, type, amount
        FROM transactions
    """)
    monthly = {}
    for ym, t, enc_amt in cursor.fetchall():
        try:
            amt = float(decrypt(enc_amt, SECRET_KEY))
        except (ArchlenceError, TypeError, ValueError):


            continue
        monthly.setdefault(ym, [0.0, 0.0])
        monthly[ym][0 if t == "income" else 1] += amt

    print(f"\nToplam eklenen işlem: {n_tx}")
    cursor.execute("SELECT COUNT(*) FROM transactions")
    print(f"transactions tablosu toplam satır: {cursor.fetchone()[0]}")
    for t in ("active_assets", "active_debts", "recurring_payments"):
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"{t}: {cursor.fetchone()[0]}")

    print("\nAy bazında Gelir / Gider / Net (eksi aylar işaretli):")
    for ym in sorted(monthly):
        inc, exp = monthly[ym]
        net = inc - exp
        flag = "  << EKSİ" if net < 0 else ""
        print(f"  {ym}:  +{inc:>12,.2f}  -{exp:>12,.2f}  net {net:>12,.2f}{flag}")


if __name__ == "__main__":
    if not DB_NAME.endswith("finance.db"):
        sys.exit("Beklenmeyen DB yolu, çıkılıyor.")
    main()
