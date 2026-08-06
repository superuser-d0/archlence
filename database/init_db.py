from database.db import get_connection
from datetime import date
from database.models import ASSET_PRICE_CACHE_SCHEMA

def initialize_database():
    """Şemayı kurar/günceller — bağlantıyı HER ÇIKIŞ YOLUNDA kapatarak.

    Gövde ayrı bir fonksiyona alındı ki `try/finally` tek yerde dursun ve
    600 satır yeniden girintilenmesin. Sarmalayıcı olmadan kurulum ortasında
    fırlayan herhangi bir istisna bağlantıyı AÇIK bırakıyordu; bu teorik
    değil: `_maybe_backfill_account_type` gibi migration adımları bilerek
    fırlatabiliyor (bkz. tests/test_migration_retry_safety.py, kesinti
    enjeksiyonu) ve `initialize_database` aynı süreçte İKİ kez çağrılıyor
    (main.py açılış + sıfırlama akışı). Linux'ta sızan handle yalnız bir
    descriptor; Windows'ta ise finance.db üzerinde duran bir kilit, yani
    sonraki restore/rename/silme adımını bloklardı.
    """
    conn = get_connection()
    try:
        _initialize_database(conn)
    finally:
        conn.close()


def _initialize_database(conn):
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
    # ŞEMA ADIMI ile VERİ ADIMI AYRI. Eskiden backfill `if column not in
    # cols` bloğunun İÇİNDEYDİ ve bu, kesintiye karşı savunmasızdı:
    # `ALTER TABLE` kalıcı olur, backfill patlarsa sonraki açılış sütunu
    # MEVCUT görüp bloğa hiç girmez ve `account_type` kalıcı olarak NULL
    # kalırdı (denetim bulgusu P1-2, kanıt: account_type_after_retry=None).
    #
    # Artık sütunun varlığı TAMAMLANMA KANITI SAYILMIYOR. Backfill kendi
    # postcondition'ına bakıyor: "geriye doldurulmamış satır var mı?"
    # Bu, adımı idempotent ve retry-safe yapıyor — kaç kez kesilirse
    # kesilsin, bir sonraki açılış eksiği tamamlar.
    if "account_type" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN account_type TEXT")
    cursor.execute(
        "SELECT COUNT(*) FROM accounts "
        "WHERE account_type IS NULL OR TRIM(account_type) = ''"
    )
    if cursor.fetchone()[0]:
        cursor.execute("""
            UPDATE accounts
            SET account_type = CASE WHEN type = 'credit' THEN 'credit_card' ELSE 'checking' END
            WHERE account_type IS NULL OR TRIM(account_type) = ''
        """)

    if "credit_limit" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN credit_limit REAL DEFAULT 0")
    # Aynı gerekçe: backfill kendi eksikliğine bakar.
    cursor.execute("UPDATE accounts SET credit_limit = 0 WHERE credit_limit IS NULL")
    if "statement_date" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN statement_date INTEGER")
        
    if "card_number_full" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN card_number_full TEXT")
    if "expiry_date" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN expiry_date TEXT")
    if "cvc_code" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN cvc_code TEXT")

    # card_number_full/expiry_date/cvc_code artık YAZILMIYOR (bkz.
    # AccountService.create_account, docs/ROADMAP.md Faz 1 madde 1). CVC ve
    # son kullanma tarihinin uygulamada hiçbir tüketicisi yoktu — saklamanın
    # ürünsel bir karşılığı olmadan risk taşıyordu. Tam kart numarası ise
    # yalnızca son-4-hane + kart ağı GÖSTERİMİ için kullanılıyordu; bu ikisi
    # artık hesap oluşturulduğu ANDA türetilip ayrı, hassas olmayan
    # sütunlarda (masked_number, network_logo) saklanıyor — çözülecek ham
    # numara bir daha diske hiç yazılmıyor.
    if "masked_number" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN masked_number TEXT")
    if "network_logo" not in existing_account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN network_logo TEXT")
    if "is_frozen" not in existing_account_cols:
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN is_frozen INTEGER DEFAULT 0"
        )
        cursor.execute(
            "UPDATE accounts SET is_frozen = 0 WHERE is_frozen IS NULL"
        )
    if "online_payments_enabled" not in existing_account_cols:
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN "
            "online_payments_enabled INTEGER DEFAULT 1"
        )
        cursor.execute(
            "UPDATE accounts SET online_payments_enabled = 1 "
            "WHERE online_payments_enabled IS NULL"
        )

    # Tek seferlik geri dolgu + temizlik migration'ı. Idempotent: ikinci
    # çalıştırmada `card_number_full IS NOT NULL` koşulunu karşılayan satır
    # kalmaz. Önce MEVCUT şifreli kart numarasından masked_number/
    # network_logo türetilir (kullanıcı kartını yeniden girmek zorunda
    # kalmasın), SONRA ham PAN/SKT/CVC null'lanır — sıra önemli, tersi
    # türetmeden önce veriyi kaybederdi.
    cursor.execute(
        "SELECT id, card_number_full FROM accounts WHERE card_number_full IS NOT NULL"
    )
    rows_to_migrate = cursor.fetchall()
    if rows_to_migrate:
        from utils.crypto import decrypt
        from database.db import SECRET_KEY
        from services.account_service import AccountService

        for row in rows_to_migrate:
            account_id, enc_number = row[0], row[1]
            try:
                dec_num = decrypt(enc_number, SECRET_KEY)
                network_logo = AccountService.check_card_network(dec_num)
                last4 = dec_num[-4:] if len(dec_num) >= 4 else dec_num
                masked_number = f"**** **** **** {last4}"
            except (ValueError, TypeError) as e:
                # decrypt() hiçbir zaman raise etmez, string işlemleri de
                # (slicing/len) raise etmez — bu except pratikte tetiklenemez.
                # Yine de daraltılmış hâliyle bırakıldı: bu, tek seferlik bir
                # migration, sessizce yanlış davranmaması önemli.
                from utils.logging_config import get_logger
                get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] accounts id={account_id} kart no migration'ı başarısız")
                # Çözülemeyen/bozuk bir kayıt bile ham veriyi diskte
                # bırakmamalı; yalnızca görüntüleme bilgisi kaybolur.
                masked_number, network_logo = None, None
            cursor.execute(
                "UPDATE accounts SET masked_number = ?, network_logo = ? WHERE id = ?",
                (masked_number, network_logo, account_id),
            )
    cursor.execute(
        "UPDATE accounts SET card_number_full = NULL, expiry_date = NULL, cvc_code = NULL "
        "WHERE card_number_full IS NOT NULL OR expiry_date IS NOT NULL OR cvc_code IS NOT NULL"
    )

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


    cursor.execute("PRAGMA table_info(transactions)")
    existing_trans_cols = {row[1] for row in cursor.fetchall()}
    if "status" not in existing_trans_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN status TEXT DEFAULT 'completed'")
    if "execution_date" not in existing_trans_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN execution_date TEXT")

    # Durable financial-operation identities.  UI state is not an idempotency
    # boundary: retries and two processes must be rejected by SQLite itself.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_operation_markers (
            recurring_payment_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            transaction_id INTEGER,
            PRIMARY KEY (recurring_payment_id, due_date, operation_type)
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
            amount REAL NOT NULL,
            target_month INTEGER DEFAULT 1,
            target_year INTEGER,
            category_name TEXT,
            rollover_enabled INTEGER DEFAULT 0,
            is_template INTEGER DEFAULT 0,
            alert_threshold_pct INTEGER DEFAULT 80
        )
    """)
    cursor.execute("PRAGMA table_info(monthly_budget_plan)")
    existing_budget_cols = {row[1] for row in cursor.fetchall()}
    if "target_month" not in existing_budget_cols:
        cursor.execute(
            "ALTER TABLE monthly_budget_plan "
            "ADD COLUMN target_month INTEGER DEFAULT 1"
        )
    budget_migrations = {
        "target_year": "INTEGER",
        "category_name": "TEXT",
        "rollover_enabled": "INTEGER DEFAULT 0",
        "is_template": "INTEGER DEFAULT 0",
        "alert_threshold_pct": "INTEGER DEFAULT 80",
    }
    for column, definition in budget_migrations.items():
        if column not in existing_budget_cols:
            cursor.execute(
                f"ALTER TABLE monthly_budget_plan "
                f"ADD COLUMN {column} {definition}"
            )
    cursor.execute(
        "UPDATE monthly_budget_plan SET target_year = ? "
        "WHERE target_year IS NULL",
        (date.today().year,),
    )
    cursor.execute(
        "UPDATE monthly_budget_plan SET rollover_enabled = 0 "
        "WHERE rollover_enabled IS NULL"
    )
    cursor.execute(
        "UPDATE monthly_budget_plan SET is_template = 0 "
        "WHERE is_template IS NULL"
    )
    cursor.execute(
        "UPDATE monthly_budget_plan SET alert_threshold_pct = 80 "
        "WHERE alert_threshold_pct IS NULL"
    )

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

    # Dinamik TTL fiyat önbelleği. Eski sürüm aynı tablo adını
    # (price_try REAL, updated_at INTEGER) ile tembel oluşturuyordu; satırları
    # kaybetmeden yeni DateTime/metaveri sözleşmesine taşı.
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='asset_price_cache'"
    )
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(asset_price_cache)")
        price_cache_cols = {row[1] for row in cursor.fetchall()}
        if not {"price", "asset_type"}.issubset(price_cache_cols):
            cursor.execute(
                "ALTER TABLE asset_price_cache "
                "RENAME TO asset_price_cache_legacy"
            )
            cursor.execute(ASSET_PRICE_CACHE_SCHEMA)
            if "price_try" in price_cache_cols:
                cursor.execute("""
                    INSERT OR REPLACE INTO asset_price_cache
                        (symbol, price, asset_type, updated_at)
                    SELECT symbol, price_try, 'UNKNOWN',
                           datetime(updated_at, 'unixepoch', 'localtime')
                      FROM asset_price_cache_legacy
                """)
            cursor.execute("DROP TABLE asset_price_cache_legacy")
        # `source` sütunu (hangi sağlayıcı verdi) sonradan eklendi. Aynı
        # migration price_service._ensure_cache içinde de var — orası fiyat
        # cache'ine her erişimin geçtiği kapı, burası ise açılıştaki tek
        # seferlik yol. İkisi de idempotent; hangisi önce koşarsa koşsun.
        cursor.execute("PRAGMA table_info(asset_price_cache)")
        if "source" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute(
                "ALTER TABLE asset_price_cache ADD COLUMN source TEXT")
    else:
        cursor.execute(ASSET_PRICE_CACHE_SCHEMA)


    # NOT: Bir ara ayrı bir `subscriptions` tablosu oluşturuluyordu ama hiçbir
    # yerden okunmuyor/yazılmıyordu. Abonelikler `recurring_payments` üzerinde
    # yaşıyor (arayüz, radar ve vade motoru hep onu okuyor); ikinci bir boş
    # tablo tutmak "hangisi doğru?" sorusunu ve sessiz tutarsızlık riskini
    # getiriyordu, o yüzden kaldırıldı. Var olan kurulumlardaki boş tabloyu da
    # temizliyoruz — içinde hiç veri üretilmemişti.
    cursor.execute("DROP TABLE IF EXISTS subscriptions")


    # 7. Tekrarlanan Ödemeler Tablosu (Kira, Netflix, Spotify vb.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount TEXT NOT NULL,
            category TEXT,
            frequency TEXT NOT NULL DEFAULT 'monthly',
            next_due_date TEXT NOT NULL,
            recurrence_day INTEGER CHECK (recurrence_day BETWEEN 1 AND 31),
            auto_deduct INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            account_id INTEGER DEFAULT 1,
            transaction_type TEXT NOT NULL DEFAULT 'expense'
        )
    """)
    cursor.execute("PRAGMA table_info(recurring_payments)")
    existing_recurring_cols = {row[1] for row in cursor.fetchall()}
    if "recurrence_day" not in existing_recurring_cols:
        cursor.execute(
            "ALTER TABLE recurring_payments ADD COLUMN recurrence_day INTEGER"
        )
    if "transaction_type" not in existing_recurring_cols:
        # Eski tablodaki bütün kayıtlar abonelik/fatura gideriydi.
        cursor.execute(
            "ALTER TABLE recurring_payments ADD COLUMN transaction_type TEXT "
            "NOT NULL DEFAULT 'expense'"
        )
    cursor.execute("""
        UPDATE recurring_payments
        SET recurrence_day = CAST(strftime('%d', next_due_date) AS INTEGER)
        WHERE recurrence_day IS NULL
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

    # Eski sürüm her dashboard yenilemesinde yeni bir satır yazıyordu. Aynı
    # güne ait gürültüyü temizle, en son hesabı koru ve DB seviyesinde bundan
    # sonra günde tek kayıt garantisi ver.
    cursor.execute("""
        DELETE FROM financial_health_history
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM financial_health_history
            GROUP BY substr(date, 1, 10)
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_health_history_day
        ON financial_health_history(substr(date, 1, 10))
    """)

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

    # 11. Görülmüş/Gizlenmiş Anomaliler
    # Anomali gerçek bir transaction satırına dayanır; transaction_id bu
    # nedenle hash türetmekten daha kararlı ve tekil kimliktir.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomaly_dismissals (
            transaction_id INTEGER PRIMARY KEY,
            dismissed_at TEXT NOT NULL
        )
    """)

    # 12. Bakiye Olay Defteri (Faz 2 — değişmez hareket kaydı)
    # accounts.balance ve savings_goals.current_amount'a dokunan HER nokta
    # buraya bir satır yazar. Kayıt, değişikliği yapan UPDATE ile AYNI cursor
    # ve AYNI commit içinde yazılır: işlem yarıda kalırsa defter de geri alınır,
    # yani defter ile gerçek bakiye asla ayrışamaz.
    #   delta           : bu olayın değeri ne kadar değiştirdiği (işaretli)
    #   resulting_value : olaydan SONRAKİ değer (replay'i doğrulamak için)
    #   source          : olayı üreten akış ('transaction', 'savings_deposit', ...)
    #   ref_id          : varsa ilgili kaydın id'si (transactions.id gibi)
    # Tutarlar burada DÜZ tutulur: defterin amacı zaman içinde toplam/fark
    # hesaplamak, şifreli kolonla replay her satırı tek tek çözmek zorunda kalırdı.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS balance_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            delta REAL NOT NULL,
            resulting_value REAL,
            source TEXT,
            ref_id INTEGER
        )
    """)

    # Migration guard: erken bir sürüm ref_id'siz kurmuş olabilir.
    cursor.execute("PRAGMA table_info(balance_events)")
    existing_event_cols = {row[1] for row in cursor.fetchall()}
    if "ref_id" not in existing_event_cols:
        cursor.execute("ALTER TABLE balance_events ADD COLUMN ref_id INTEGER")
    if "resulting_value" not in existing_event_cols:
        cursor.execute("ALTER TABLE balance_events ADD COLUMN resulting_value REAL")

    # Replay her zaman "tarihe göre" tarandığı için ts indeksi şart.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_balance_events_ts ON balance_events(ts)")

    # 12. Günlük Bakiye Anlık Görüntüsü (Faz 2 — replay kısayolu)
    # get_balance_at() sıfırdan replay etmek yerine tarihe en yakın snapshot'ı
    # alıp yalnızca sonrasındaki olayları oynatır. snapshot_date UNIQUE: günde
    # tek satır, on_start aynı gün ikinci kez çalışsa da tekrar yazmaz.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_balance_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL UNIQUE,
            total_balance REAL NOT NULL,
            breakdown_json TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(daily_balance_snapshot)")
    existing_snap_cols = {row[1] for row in cursor.fetchall()}
    if "breakdown_json" not in existing_snap_cols:
        cursor.execute("ALTER TABLE daily_balance_snapshot ADD COLUMN breakdown_json TEXT")

    conn.commit()

    # ── Defter başlangıç çizgisi (backfill) ───────────────────────────────────
    # Defter boşsa ama hesaplar doluysa, mevcut bakiyeler için birer "açılış"
    # olayı yazılır. İki durumu birden kapsar:
    #   * yeni kurulum  — varsayılan hesaplar aşağıda eklendikten sonra,
    #   * MEVCUT veritabanı — Faz 2 öncesinden gelen bakiyeler.
    #
    # Bu satır olmadan `get_balance_at` defteri baştan oynattığında sonucu tam
    # olarak açılış toplamı kadar eksik çıkar: accounts.balance'a INSERT ile
    # konan para hiçbir UPDATE üretmediği için defterde karşılığı olmaz.
    #
    # DÜRÜSTLÜK NOTU: bu olayın zaman damgası BUGÜNDÜR, çünkü paranın gerçekte
    # ne zaman girdiği bilinmiyor — defter o tarihten önce yoktu. Bu yüzden
    # history_service, defter başlangıcından ÖNCEKİ tarihler için "veri yok"
    # der; sıfır bakiye varmış gibi göstermez.
    def _backfill_ledger_baseline():
        """Açılış çizgisi olmayan her varlık için birer baseline olayı yazar.

        "Defter tamamen boş mu" diye bakmak yetmez: defter kısmen dolu da
        olabilir (ör. bazı hareketler kaydedilmişken uygulama güncellenmiş).
        O yüzden VARLIK BAZINDA bakılır ve baseline şöyle hesaplanır:

            açılış = bugünkü değer − o varlık için defterdeki deltaların toplamı

        Böylece defterin toplamı her zaman gerçek bakiyeye eşitlenir; zaten
        açılış çizgisi olan varlıklar tekrar yazılmaz (idempotent).
        """
        from database.db import ACCOUNT, SAVINGS_GOAL, record_balance_event

        def _baseline(entity_type, table, value_column, marker_source):
            cursor.execute(
                f"SELECT id, {value_column} AS value FROM {table}"
            )
            rows = [(r["id"], r["value"] or 0.0) for r in cursor.fetchall()]
            for entity_id, current_value in rows:
                cursor.execute(
                    "SELECT COUNT(*) FROM balance_events"
                    " WHERE entity_type = ? AND entity_id = ? AND source = ?",
                    (entity_type, entity_id, marker_source),
                )
                if cursor.fetchone()[0] > 0:
                    continue  # açılış çizgisi zaten var

                cursor.execute(
                    "SELECT COALESCE(SUM(delta), 0) AS total, MIN(ts) AS first_ts"
                    " FROM balance_events WHERE entity_type = ? AND entity_id = ?",
                    (entity_type, entity_id),
                )
                agg = cursor.fetchone()
                recorded = agg["total"] or 0.0
                opening = current_value - recorded

                record_balance_event(cursor, entity_type, entity_id, opening,
                                     opening, marker_source)
                # Baseline kronolojik olarak mevcut olayların ÖNÜNE geçmeli,
                # yoksa "o tarihteki bakiye" sorgusu açılışı sonradan görür.
                if agg["first_ts"]:
                    cursor.execute(
                        "UPDATE balance_events SET ts = ? WHERE id = ?",
                        (f"{agg['first_ts'][:10]} 00:00:00", cursor.lastrowid),
                    )

        _baseline(ACCOUNT, "accounts", "balance", "account_opened")
        _baseline(SAVINGS_GOAL, "savings_goals", "current_amount", "savings_goal_created")
        conn.commit()

    # 4. Varsayılan Hesapları Ekle
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        # Dummy veriler kaldırıldı, başlangıçta hesap oluşturulmayacak.
        pass

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
            ("Elektrik", "expense", "main"), ("Su", "expense", "main"), ("Doğalgaz", "expense", "main"), ("İnternet", "expense", "main"), ("Cep Telefonu", "expense", "main"), ("Dijital Platformlar", "expense", "extra"), ("Dijital Abonelik", "expense", "extra"),
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
    cursor.execute(
        "SELECT 1 FROM categories WHERE name = ? AND type = ?",
        ("Dijital Abonelik", "expense"),
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO categories(name, type, importance) VALUES(?,?,?)",
            ("Dijital Abonelik", "expense", "extra"),
        )
    conn.commit()

    # Varsayılan hesaplar kurulduktan SONRA çalışmalı ki yeni kurulumda da
    # açılış bakiyeleri deftere girsin.
    _backfill_ledger_baseline()
    # ─────────────────────────────────────────────────────────────────────────
    # Kapatma ARTIK BURADA DEĞİL: sarmalayıcı `initialize_database`'in
    # `finally` bloğu yapıyor, böylece hata yolları da kapsanıyor.
