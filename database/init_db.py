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
            balance REAL DEFAULT 0,
            account_type TEXT NOT NULL DEFAULT 'checking',
            credit_limit REAL DEFAULT 0,
            statement_date INTEGER
        )
    """)

    # Çoklu Hesap / Kredi Kartı sütunları (migration guard).
    # Mevcut veritabanlarında accounts tablosu yalnızca (id, name, type, balance)
    # içeriyor; aşağıdaki üç sütun sonradan eklendi. ALTER TABLE ... ADD COLUMN
    # eski satırlara NULL yazar, bu yüzden account_type hemen eski "type"
    # değerinden geriye doldurulur ('credit' -> 'credit_card', diğerleri
    # 'checking'). Böylece hiçbir mevcut hesap türsüz kalmaz.
    cursor.execute("PRAGMA table_info(accounts)")
    existing_account_cols = {row[1] for row in cursor.fetchall()}
    if "account_type" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN account_type TEXT")
        cursor.execute("""
            UPDATE accounts
            SET account_type = CASE WHEN type = 'credit' THEN 'credit_card' ELSE 'checking' END
        """)
    if "credit_limit" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN credit_limit REAL DEFAULT 0")
        cursor.execute("UPDATE accounts SET credit_limit = 0 WHERE credit_limit IS NULL")
    if "statement_date" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN statement_date INTEGER")

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

    # Borç kartındaki otomatik ödeme talimatı için sütunlar (migration guard)
    if "is_auto_pay" not in existing_debt_cols:
        cursor.execute("ALTER TABLE active_debts ADD COLUMN is_auto_pay INTEGER DEFAULT 0")
    if "auto_pay_day" not in existing_debt_cols:
        cursor.execute("ALTER TABLE active_debts ADD COLUMN auto_pay_day INTEGER DEFAULT 1")
    if "last_auto_pay_date" not in existing_debt_cols:
        cursor.execute("ALTER TABLE active_debts ADD COLUMN last_auto_pay_date TEXT")


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

    # 8. Birikim Hedefleri Tablosu (Yaz Tatili, Araç Peşinatı, Acil Durum Fonu vb.)
    # goal_name AES şifreli tutulur (kişisel hayal/plan bilgisidir); tutarlar
    # monthly_budget_plan'daki gibi düz REAL kalır — hedefe para ekleme/çekme
    # accounts.balance ile aynı SQL işleminde atomik güncellenmek zorunda,
    # şifreli kolonla "current_amount = current_amount + ?" yazılamazdı.
    # status: 'aktif' | 'tamamlandi'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            target_date TEXT,
            status TEXT DEFAULT 'aktif'
        )
    """)

    # 9. Finansal Sağlık Skoru Geçmişi (Faz 1 — içgörü motoru)
    # Skorun kendisi ve bileşenleri düz tutulur: kişisel tutar/açıklama değil,
    # 0-100 arası türetilmiş bir metrik ve onun ağırlık dökümü. Şifrelenseydi
    # trend grafiği için her satır tek tek çözülmek zorunda kalırdı.
    # breakdown_json: {"savings_rate": .., "debt_ratio": .., "volatility": ..}
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_health_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            score REAL NOT NULL,
            breakdown_json TEXT
        )
    """)

    # Migration guard: tabloyu breakdown_json'suz oluşturmuş bir ara sürüm
    # varsa sütun sonradan eklenir (mevcut satırlarda NULL kalır, okuyucu
    # tarafı boş döküm olarak tolere eder).
    cursor.execute("PRAGMA table_info(financial_health_history)")
    existing_health_cols = {row[1] for row in cursor.fetchall()}
    if "breakdown_json" not in existing_health_cols:
        cursor.execute("ALTER TABLE financial_health_history ADD COLUMN breakdown_json TEXT")

    # 10. Reddedilen Abonelik Adayları (Faz 1 — "sessiz sızıntı" radarı)
    # candidate_key: kategori + normalize edilmiş ad üzerinden üretilen kararlı
    # anahtar (bkz. services/insights_service.py::candidate_key). Kullanıcı bir
    # adayı "bu abonelik değil" diye kapattığında burada işaretlenir ve radar
    # onu bir daha önermez.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_candidate_dismissals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_key TEXT NOT NULL,
            dismissed_at TEXT NOT NULL
        )
    """)

    cursor.execute("PRAGMA table_info(recurring_candidate_dismissals)")
    existing_dismissal_cols = {row[1] for row in cursor.fetchall()}
    if "dismissed_at" not in existing_dismissal_cols:
        cursor.execute("ALTER TABLE recurring_candidate_dismissals ADD COLUMN dismissed_at TEXT")

    conn.commit()

    # 4. Varsayılan Hesapları Ekle
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        # balance İŞARETLİ tutulur: kredi kartı borcu NEGATİF bakiyedir
        # (bkz. database/db.py::adjust_account_balance docstring'i).
        accounts = [
            ("Nakit", "cash", 2500, "checking", 0, None),
            ("Banka", "bank", 15000, "checking", 0, None),
            ("Kredi Kartı", "credit", -3500, "credit_card", 20000, 15),
        ]
        cursor.executemany(
            "INSERT INTO accounts(name,type,balance,account_type,credit_limit,statement_date)"
            " VALUES(?,?,?,?,?,?)",
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