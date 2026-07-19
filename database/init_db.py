from database.db import get_connection

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Hesaplar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    """)

    # 2. İşlemler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            amount TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            description TEXT,
            transaction_date TEXT,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )
    """)

    # 3. Kategoriler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            importance TEXT DEFAULT 'extra'
        )
    """)

    # 4. Bütçe Planlama Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_budget_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)

    # 5. Aktif Borçlar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_name TEXT NOT NULL,
            total_amount TEXT NOT NULL,
            monthly_payment TEXT NOT NULL,
            total_installments INTEGER NOT NULL,
            paid_installments INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Mevcut veritabanlarında "name" sütununu "debt_name" olarak güncelleme (migration guard)
    cursor.execute("PRAGMA table_info(active_debts)")
    existing_debt_cols = {row[1] for row in cursor.fetchall()}
    if "name" in existing_debt_cols and "debt_name" not in existing_debt_cols:
        cursor.execute("ALTER TABLE active_debts RENAME COLUMN name TO debt_name")


    # 6. Aktif Varlıklar Tablosu (Hisse, Altın, Tahvil vb.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_code TEXT NOT NULL,
            asset_type TEXT NOT NULL DEFAULT 'Diğer',
            purchase_price TEXT NOT NULL,
            quantity TEXT NOT NULL,
            purchase_date TEXT
        )
    """)

    # Mevcut veritabanları için purchase_date sütunu ekleme (migration guard)
    cursor.execute("PRAGMA table_info(active_assets)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "purchase_date" not in existing_cols:
        cursor.execute("ALTER TABLE active_assets ADD COLUMN purchase_date TEXT")

    # 7. Tekrarlanan Ödemeler Tablosu (Kira, Netflix, Spotify vb.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount TEXT NOT NULL,
            category TEXT,
            frequency TEXT NOT NULL DEFAULT 'monthly',
            next_due_date TEXT NOT NULL,
            auto_deduct INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            account_id INTEGER DEFAULT 1
        )
    """)

    conn.commit()

    # 4. Varsayılan Hesapları Ekle
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        accounts = [
            ("Nakit", "cash", 2500),
            ("Banka", "bank", 15000),
            ("Kredi Kartı", "credit", -3500),
        ]
        cursor.executemany(
            "INSERT INTO accounts(name,type,balance) VALUES(?,?,?)",
            accounts,
        )
        conn.commit()

    # 5. Kapsamlı Varsayılan Kategorileri Ekle (importance verisiyle birlikte)
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            # GELİR KATEGORİLERİ (Ad, Tür, Önem)
            ("Maaş", "income", "main"), ("Avans", "income", "main"), ("Prim", "income", "extra"), ("Mesai", "income", "extra"), ("Kıdem Tazminatı", "income", "extra"), ("İhbar Tazminatı", "income", "extra"),
            ("Freelance", "income", "extra"), ("Danışmanlık", "income", "extra"), ("Proje Bedeli", "income", "extra"), ("Ürün Satışı", "income", "extra"), ("E-Ticaret", "income", "extra"), ("Hak Ediş", "income", "extra"),
            ("Ev Kirası (Gelir)", "income", "extra"), ("Dükkan Kirası", "income", "extra"), ("Araç Kirası", "income", "extra"), ("Faiz Getirisi", "income", "extra"), ("Temettü", "income", "extra"), ("Kripto Kazancı", "income", "extra"), ("Fon Getirisi", "income", "extra"), ("Kupon Ödemesi", "income", "extra"),
            ("Emekli Maaşı", "income", "main"), ("İşsizlik Maaşı", "income", "extra"), ("Çocuk Yardımı", "income", "extra"), ("Burs", "income", "extra"), ("Nafaka", "income", "extra"), ("Devlet Teşviki", "income", "extra"),
            ("Piyango/Loto", "income", "extra"), ("Miras", "income", "extra"), ("Borç Tahsilatı", "income", "extra"), ("Nakit Hediye", "income", "extra"), ("İade", "income", "extra"), ("Varlık Satışı", "income", "extra"),
            
            # GİDER KATEGORİLERİ (Ad, Tür, Önem)
            ("Ev Kirası", "expense", "main"), ("Aidat", "expense", "main"), ("Emlak Vergisi", "expense", "extra"), ("Ev Bakım/Onarım", "expense", "extra"), ("Ev Eşyası", "expense", "extra"),
            ("Elektrik", "expense", "main"), ("Su", "expense", "main"), ("Doğalgaz", "expense", "main"), ("İnternet", "expense", "main"), ("Cep Telefonu", "expense", "main"), ("Dijital Platformlar", "expense", "extra"),
            ("Akaryakıt", "expense", "main"), ("Toplu Taşıma", "expense", "main"), ("Taksi", "expense", "extra"), ("Araç Bakım", "expense", "extra"), ("MTV", "expense", "extra"), ("Sigorta/Kasko", "expense", "extra"), ("Otopark/Köprü", "expense", "extra"),
            ("Süpermarket", "expense", "main"), ("Pazaryeri", "expense", "main"), ("Dışarıda Yemek", "expense", "extra"), ("Paket Servis", "expense", "extra"), ("Su Siparişi", "expense", "main"),
            ("Hastane", "expense", "main"), ("İlaç/Eczane", "expense", "main"), ("Sağlık Sigortası", "expense", "main"), ("Kişisel Bakım", "expense", "extra"), ("Kuaför/Berber", "expense", "extra"), ("Spor Salonu", "expense", "extra"),
            ("Okul/Kurs", "expense", "main"), ("Kitap/Kırtasiye", "expense", "extra"), ("Sınav Ücretleri", "expense", "extra"),
            ("Sinema/Tiyatro", "expense", "extra"), ("Oyun/Uygulama", "expense", "extra"), ("Tatil/Konaklama", "expense", "extra"), ("Hobiler", "expense", "extra"),
            ("Kıyafet", "expense", "extra"), ("Ayakkabı", "expense", "extra"), ("Çanta", "expense", "extra"), ("Takı/Aksesuar", "expense", "extra"),
            ("Kredi Kartı", "expense", "main"), ("Kredi Taksiti", "expense", "main"), ("Borç Ödeme", "expense", "main"), ("Vergi Ödemeleri", "expense", "main"), ("Bağış/Zekat", "expense", "extra"),
            ("Çocuk Bakımı", "expense", "main"), ("Evcil Hayvan", "expense", "main"), ("Varlık Alımı", "expense", "extra")
        ]
        cursor.executemany(
            "INSERT INTO categories(name, type, importance) VALUES(?,?,?)",
            default_categories,
        )
        conn.commit()

    # ── Migration Guard: Varlık Alımı / Varlık Satışı kategorilerini ekle ──────
    cursor.execute("SELECT name FROM categories WHERE name='Varlık Alımı'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO categories(name, type, importance) VALUES(?,?,?)",
                       ("Varlık Alımı", "expense", "extra"))
    cursor.execute("SELECT name FROM categories WHERE name='Varlık Satışı'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO categories(name, type, importance) VALUES(?,?,?)",
                       ("Varlık Satışı", "income", "extra"))
    conn.commit()
    # ─────────────────────────────────────────────────────────────────────────

    conn.close()