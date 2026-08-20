import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from utils.crypto import encrypt, decrypt
from utils.errors import (
    DecryptionError,
    FinancialDataIntegrityError,
    KeyUnavailableError,
)
from utils.app_paths import LEGACY_CBC_PASSWORD, data_dir, migrate_legacy_path
from utils.financial_decimal import decimal_from, fiat

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# docs/ROADMAP.md Faz 1 madde 4. Paketlenmiş bir Windows kurulumunda
# BASE_DIR (uygulamanın kendi kurulum klasörü) genelde salt-okunur
# (`Program Files` altı) — artık kullanıcı-veri dizinine (platformdirs)
# yazıyoruz. BASE_DIR hâlâ var: NETWORK_LOGOS gibi salt-okunur, PAKETLE
# BİRLİKTE GELEN varlıklar için hâlâ doğru yer, o değişmedi.
_LEGACY_DB_PATH = os.path.join(BASE_DIR, "finance.db")
DB_NAME = os.path.join(data_dir(), "finance.db")
# Eski AES-256-CBC kayıtlarının çözme parolası. Adı `SECRET_KEY` çünkü
# yüzlerce çağrı yeri bu adı kullanıyor, ama artık HİÇBİR ŞEY bu parolayla
# ŞİFRELENMİYOR: `utils.crypto.encrypt` kurulum başına rastgele bir AEAD
# anahtarı kullanıyor ve `password` parametresini yok sayıyor. Değer yalnız
# `decrypt()`'in eski kayıtları okuyabilmesi için duruyor.
# Tanımı ve neden değiştirilemeyeceği: `utils/app_paths.py`.
SECRET_KEY = LEGACY_CBC_PASSWORD


def migrate_legacy_database_location() -> bool:
    """Var olan bir kurulumdan geçiş: eski BASE_DIR/finance.db'yi (varsa)
    yeni kullanıcı-veri konumuna taşır. main.py'nin başlangıcında,
    initialize_database()'DEN ÖNCE açıkça çağrılır — bu modülün salt
    import edilmesiyle OTOMATİK tetiklenmez, çünkü test suite'i bu modülü
    sürekli import ediyor ve import'un kendisi gerçek kullanıcı verisini
    taşımamalı."""
    return migrate_legacy_path(_LEGACY_DB_PATH, DB_NAME)

# Arayüzde henüz hesap seçimi olmadığından işlem ekleyen tüm çağıranlar
# (transaction_mixin, debt_mixin, recurring_mixin, asset_mixin) bu tek
# noktadan varsayılan hesabı okur — ileride bir hesap seçici eklenirse
# değişmesi gereken tek yer burası, 8 ayrı dosyaya dağılmış literal "1" değil.
DEFAULT_ACCOUNT_ID = 1

NETWORK_LOGOS = {
    "Visa": "assets/visa.png",
    "Mastercard": "assets/mastercard.png",
    "Troy": "assets/troy.png",
}

# İleri tarihli (status='pending') işlemler bakiyeye HENÜZ işlenmemiştir
# (bkz. TransactionService.settle_due_transactions). Bu yüzden bakiyeyi
# yansıtan her raporlama sorgusu — gelir/gider metrikleri, tasarruf oranı,
# trend, kategori toplamları, "Son İşlemler" — bu koşulu eklemek ZORUNDA;
# yoksa dashboard bakiyeden fazlasını gösterir ve ikisi birbirini tutmaz.
# COALESCE, status kolonu eklenmeden önce yazılmış eski satırları kapsar.
# İstisna: veri dökümü/migration ve "Bekleyen İşlemler" paneli tüm
# satırları görmek ister, onlar bu koşulu kullanmaz.
COMPLETED_TX = "COALESCE(status, 'completed') = 'completed'"
COMPLETED_TX_T = "COALESCE(t.status, 'completed') = 'completed'"

def get_connection():
    # DB_NAME artık kullanıcı-veri dizininde (bkz. yukarıdaki not) — o dizin
    # ilk gerçek yazımdan önce OLUŞMAMIŞ olabilir (platformdirs.data_dir()
    # yalnızca yolu ÇÖZER, oluşturmaz). exist_ok=True ile idempotent; zaten
    # varsa maliyeti bir stat() kadar.
    directory = os.path.dirname(DB_NAME)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    enable_foreign_keys(conn)
    return conn


def enable_foreign_keys(conn):
    """`PRAGMA foreign_keys=ON` — bağlantı kurulur kurulmaz, DML'den ÖNCE.

    SQLite'ta foreign key zorlaması BAĞLANTI BAŞINA ve VARSAYILAN OLARAK
    KAPALIDIR (3.6.19'da eklenirken geriye dönük uyumluluk için alınmış bir
    karar). Şemada `transactions.account_id REFERENCES accounts(id)` yazıyor
    olması tek başına HİÇBİR ŞEY zorlamıyordu — ölçüldü: var olmayan bir
    hesaba işlem yazmak kabul ediliyor, `PRAGMA foreign_key_check` ise
    ihlali bildiriyordu. Yani şema bir kural olduğunu sanıyor, motor
    uygulamıyordu.

    SIRA ÖNEMLİ: bu PRAGMA bir transaction'ın İÇİNDE sessiz bir NO-OP'tur.
    Burada, `connect`'ten hemen sonra ve herhangi bir `BEGIN`/DML'den önce
    çalışıyor.

    SONUÇ DOĞRULANIYOR: PRAGMA, foreign key desteği olmadan derlenmiş bir
    SQLite'ta hata VERMEDEN hiçbir şey yapmaz. Sessizce korumasız devam
    etmek, korumanın var olduğunu sanarak yazılmış her çağrıyı yanıltır;
    bu yüzden fail-closed.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if not row or not row[0]:
        conn.close()
        raise FinancialDataIntegrityError(
            "sqlite", None, "foreign_keys",
            reason="PRAGMA foreign_keys=ON etkinleştirilemedi.",
        )


@contextmanager
def managed_connection():
    """Bağlantıyı HER ÇIKIŞ YOLUNDA kapatan context manager.

    Bu modüldeki fonksiyonlar eskiden `conn = get_connection()` ... `conn.close()`
    kalıbını try/finally OLMADAN kullanıyordu — yani araya giren herhangi bir
    istisnada `close()` hiç çalışmıyordu. Bu teorik bir risk değildi:
    `adjust_account_balance` hesap bulunamadığında BİLEREK ValueError fırlatır
    (aşağıdaki `cursor.rowcount == 0` koruması) ve onu çağıran
    `process_due_recurring_payment` tam da bu kalıptaydı. Yazma bütünlüğü zaten güvendeydi (commit'e ulaşılmadığı için
    yarım kayıt oluşmaz), sızan şey bağlantı nesnesinin kendisiydi.

    Servis katmanı (services/account_service.py, transaction_service.py vb.)
    bu işi zaten try/finally ile doğru yapıyordu; eksik olan tek katman
    buydu. Context manager tercih edildi ki bundan SONRA eklenecek
    fonksiyonlar da kalıbı yeniden yazmak zorunda kalmadan güvenli olsun.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


ACCOUNT = "account"
SAVINGS_GOAL = "savings_goal"


def record_balance_event(cursor, entity_type, entity_id, delta,
                         resulting_value, source, ref_id=None):
    """balance_events'e tek satır yazar — ÇAĞIRANIN cursor'ıyla, aynı commit'te.

    Kendi bağlantısını AÇMAZ: defter, kaydettiği bakiye değişikliğiyle aynı
    işlemde durmak zorunda. Ayrı bağlantı açsaydı UPDATE geri alındığında
    defterde hayalet bir satır kalırdı ve replay gerçek bakiyeden sapardı.

    delta 0 olan olaylar da yazılır (örn. hedef açılışı): toplamı etkilemezler
    ama defterin varlık geçmişini eksiksiz tutarlar.
    """
    cursor.execute(
        """
        INSERT INTO balance_events
            (ts, entity_type, entity_id, delta, resulting_value, source, ref_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            entity_type,
            int(entity_id),
            float(delta),
            None if resulting_value is None else float(resulting_value),
            source,
            None if ref_id is None else int(ref_id),
        ),
    )
    # Hesap bakiyesini değiştiren HER yol buradan geçer (defter değişmezi), bu
    # yüzden "ekrandaki snapshot bayatladı" işareti tek bir yerden düşürülür.
    #
    # Alternatif — her çağrı noktasına tazeleme eklemek — zaten denenmiş ve
    # tutmamıştı: işlem ekleme ve kart silme tazeliyordu ama hesap ekleme, kart
    # borcu ödeme, birikim aktarımı ve otomatik ödeme talimatları unutulmuştu.
    # Yeni bir yazım yolu eklendiğinde defter satırı yazmak zaten zorunlu
    # olduğundan, bayrak da kendiliğinden düşer.
    #
    # Commit'ten ÖNCE işaretlenir: yazım geri alınırsa bayrak boş yere kalkmış
    # olur, bu da yalnızca bir kez fazladan (ve doğru sonucu veren) okuma demek.
    # İçeriden import: database katmanı servis katmanını modül düzeyinde import
    # edemez (döngü olurdu).
    event_id = cursor.lastrowid
    if entity_type == ACCOUNT:
        from services.asset_service import mark_account_cache_stale
        mark_account_cache_stale()
    # Yazılan defter satırının id'si DÖNDÜRÜLÜYOR. Çağıranın onu çağrıdan
    # SONRA `cursor.lastrowid` ile okuması, bu fonksiyonun içinde kaç INSERT
    # olduğuna bağlı görünmez bir bağ kurar — `database/init_db.py`'deki
    # açılış çizgisi tam olarak öyle okuyordu. Değer burada, tek INSERT'ün
    # hemen ardından alınıyor; mevcut çağıranlar dönüşü yok saydığı için
    # davranış değişmiyor.
    return event_id


def current_account_balance(cursor, account_id):
    """Açık cursor üzerinden hesabın güncel bakiyesi (olay sonrası değer için)."""
    cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    return (row["balance"] if row else 0.0) or 0.0


def current_goal_amount(cursor, goal_id):
    """Açık cursor üzerinden hedefin güncel birikimi."""
    cursor.execute("SELECT current_amount FROM savings_goals WHERE id = ?", (goal_id,))
    row = cursor.fetchone()
    return (row["current_amount"] if row else 0.0) or 0.0


def adjust_account_balance(cursor, account_id, transaction_type, amount,
                           ref_id=None, source="transaction"):
    """accounts.balance'ı işlem tutarına göre senkron günceller (Hesaplar Kopuk
    düzeltmesi). Açık bir cursor alır ki çağıran INSERT ile aynı commit'te atomik
    olarak yazılsın — ayrı bir connection açılırsa iki yazım arasında tutarsız bir
    ara durum oluşabilir.

    İŞARET KONVANSİYONU (kredi kartı desteğinin temeli):
    accounts.balance her zaman "bu hesabın net servete KATKISI"dır.
      * Vadesiz (checking): bakiye pozitiftir, gider onu DÜŞÜRÜR.
      * Kredi kartı (credit_card): borç NEGATİF bakiye olarak tutulur. Karttan
        gider işlenince bakiye daha da negatife gider, yani KART BORCU ARTAR;
        karta ödeme yapılınca (income) bakiye 0'a yaklaşır, borç azalır.

    Bu konvansiyonun tek ama kritik faydası: net servet hâlâ düz bir
    SUM(balance) ile doğru çıkar (kart borçları kendiliğinden eksi düşer) ve
    accounts.balance'a dokunan diğer yerler (savings_service, admin sıfırlama,
    CSV içe aktarımı) hiçbir tür ayrımı yapmak zorunda kalmaz. Borcu pozitif bir
    sayı olarak saklasaydık SUM(balance) borcu servete EKLERDİ ve tek bir unutulan
    çağrı noktası sessizce yanlış net servet üretirdi.

    Ekrana pozitif borç ("₺3.500 borcunuz var") göstermek isteyen taraf
    services/account_service.py içindeki türetilmiş `debt` / `available_limit`
    alanlarını kullanır; ham işaretli değeri UI'da göstermez."""
    delta = amount if transaction_type in ("income", "Gelir") else -amount
    cursor.execute(
        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
        (delta, account_id),
    )
    # Var olmayan bir hesaba yazmak SQLite'ta hata değildir; UPDATE sessizce 0
    # satır etkiler ve para hiçbir yere gitmemiş olur. Bu, varsayılan hesap
    # seed'i kaldırıldıktan sonra gerçek bir veri kaybı yoluydu: DEFAULT_ACCOUNT_ID
    # artık taze kurulumda hiçbir satıra denk gelmiyor. Sessiz kaybı gürültülü
    # hataya çeviriyoruz — çağıranın commit'i çalışmayacağı için işlem satırı da
    # yazılmaz, yani yarım kayıt kalmaz (atomik geri alma).
    if cursor.rowcount == 0:
        raise ValueError(
            f"Hesap bulunamadı (id={account_id}); işlem bakiyeye yazılamadı. "
            "Önce bir hesap oluşturulmalı."
        )
    # [Faz 2 · defter 1/6] Aynı cursor, aynı commit.
    record_balance_event(
        cursor, ACCOUNT, account_id, delta,
        current_account_balance(cursor, account_id), source, ref_id,
    )

def insert_debt(debt_name, total_amount, monthly_payment, total_installments, is_auto_pay=0, auto_pay_day=1):
    with managed_connection() as conn:
        cursor = conn.cursor()
        # Tutarlar kuruşa yuvarlanarak SAKLANIR. Buradaki değerler tipik
        # olarak HESAPLANMIŞ olarak gelir: kredi hesaplayıcısı anüite
        # formülünden `emi` üretir ve yuvarlamaz, `total_amount` da `emi * n`
        # olarak türetilir. Ham hâlleriyle 5493.320123592063 ve
        # 197759.52444931428 gibi on altı anlamlı haneli değerler deftere
        # şifrelenip yazılıyordu.
        #
        # Yalnızca kozmetik değil: otomatik taksit döngüsü
        # (mixins/recurring_mixin.py) saklanan `monthly_payment` ile GERÇEK
        # işlem yazıp bakiyeden düşüyor — 36 taksitlik bir kredide ham tutar
        # bakiyeyi kuruşlu tutardan 0,0044 TL saptırır ve her işlem satırı
        # ekranda "5.493,32" görünürken diskte farklı bir sayı tutar.
        #
        # Sınır burada seçildi (çağıranlarda değil) çünkü paranın veriye
        # dönüştüğü yer burası; her çağıran ayrı ayrı yuvarlamayı hatırlamak
        # zorunda kalmasın.
        enc_name = encrypt(str(debt_name), SECRET_KEY)
        enc_total = encrypt(str(fiat(total_amount)), SECRET_KEY)
        enc_monthly = encrypt(str(fiat(monthly_payment)), SECRET_KEY)

        cursor.execute("""
            INSERT INTO active_debts (debt_name, total_amount, monthly_payment, total_installments, paid_installments, is_active, is_auto_pay, auto_pay_day)
            VALUES (?, ?, ?, ?, 0, 1, ?, ?)
        """, (enc_name, enc_total, enc_monthly, total_installments, int(is_auto_pay), auto_pay_day))
        conn.commit()

def update_debt_progress(debt_id, extra_installments_paid, is_active=1):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET paid_installments = paid_installments + ?, is_active = ?
            WHERE id = ?
        """, (extra_installments_paid, is_active, debt_id))
        conn.commit()

def update_debt_auto_pay(debt_id, is_auto_pay, auto_pay_day):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET is_auto_pay = ?, auto_pay_day = ?
            WHERE id = ?
        """, (int(is_auto_pay), auto_pay_day, debt_id))
        conn.commit()

def get_active_debts():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_debts WHERE is_active = 1")
        rows = cursor.fetchall()


    debts = []
    for r in rows:
        try:
            dec_name = decrypt(r["debt_name"], SECRET_KEY)
            dec_total = float(decrypt(r["total_amount"], SECRET_KEY))
            dec_monthly = float(decrypt(r["monthly_payment"], SECRET_KEY))
        except (DecryptionError, ValueError, TypeError) as exc:
            raise FinancialDataIntegrityError(
                "active_debts", r["id"], "encrypted_fields", reason=exc
            ) from exc
            
        debts.append({
            "id": r["id"],
            "debt_name": dec_name,
            "total_amount": dec_total,
            "monthly_payment": dec_monthly,
            "total_installments": r["total_installments"],
            "paid_installments": r["paid_installments"],
            "is_auto_pay": bool(r["is_auto_pay"]) if "is_auto_pay" in r.keys() and r["is_auto_pay"] else False,
            "auto_pay_day": r["auto_pay_day"] if "auto_pay_day" in r.keys() and r["auto_pay_day"] else 1,
            "last_auto_pay_date": r["last_auto_pay_date"] if "last_auto_pay_date" in r.keys() else None
        })
    return debts

# ─── Aktif Varlıklar ─────────────────────────────────────────────────────────

def insert_asset(asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date=None):
    # ÜRETİM YOLU BURASI DEĞİL — portföye varlık ekleyen tek üretim çağrısı
    # `AssetPurchaseService.create_purchase` (o, alımı işlem + bakiye + defter
    # ile aynı transaction'da yazar). Burası mock veri üreteci ve şema
    # denetimi tarafından kullanılıyor. Yine de doğrulanıyor: sonlu olmayan
    # tutar kabul eden TEK yazma sınırı buydu (ölçüldü — 18 sınırın 17'si
    # `nan`/`inf`/`-inf` üçünü de reddederken bu üçünü de yazıyordu) ve
    # ileride buraya bağlanacak bir çağıran açığı sessizce geri getirirdi.
    #
    # KURUŞA YUVARLAMA YOK, bilerek: `create_purchase` fiyat ve miktarı
    # yuvarlamadan saklıyor (nakit tutar ayrı yuvarlanıyor) ve bu fonksiyon
    # aynı iki sütuna yazıyor. `decimal_from` yalnız sonluluğu doğrular.
    if decimal_from(purchase_price) <= 0 or decimal_from(quantity) <= 0:
        raise ValueError("Fiyat ve miktar sıfırdan büyük olmalıdır.")
    from datetime import datetime
    with managed_connection() as conn:
        cursor = conn.cursor()
        enc_purchase_price = encrypt(str(purchase_price), SECRET_KEY)
        enc_quantity       = encrypt(str(quantity),       SECRET_KEY)
        if purchase_date is None:
            purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO active_assets (asset_name, asset_code, asset_type, purchase_price, quantity, purchase_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (asset_name, asset_code.upper(), asset_type, enc_purchase_price, enc_quantity, purchase_date))
        conn.commit()


def get_all_assets():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_assets ORDER BY id DESC")
        rows = cursor.fetchall()

    assets = []
    for r in rows:
        try:
            dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
            dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
        except (DecryptionError, ValueError, TypeError) as exc:
            raise FinancialDataIntegrityError(
                "active_assets", r["id"], "purchase_price/quantity",
                reason=exc,
            ) from exc
        assets.append({
            "id":             r["id"],
            "asset_name":     r["asset_name"],
            "asset_code":     r["asset_code"],
            "asset_type":     r["asset_type"],
            "purchase_price": dec_price,
            "quantity":       dec_quantity,
        })
    return assets


def delete_asset(asset_id):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_assets WHERE id = ?", (asset_id,))
        conn.commit()


def get_asset_by_id(asset_id):
    """Returns a single asset row as a dict (decrypted)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_assets WHERE id = ?", (asset_id,))
        r = cursor.fetchone()
    if not r:
        return None
    try:
        dec_price    = float(decrypt(r["purchase_price"], SECRET_KEY))
        dec_quantity = float(decrypt(r["quantity"],       SECRET_KEY))
    except (DecryptionError, ValueError, TypeError) as exc:
        raise FinancialDataIntegrityError(
            "active_assets", r["id"], "purchase_price/quantity", reason=exc
        ) from exc
    return {
        "id":             r["id"],
        "asset_name":     r["asset_name"],
        "asset_code":     r["asset_code"],
        "asset_type":     r["asset_type"],
        "purchase_price": dec_price,
        "quantity":       dec_quantity,
        "purchase_date":  r["purchase_date"],
    }


def get_asset_transaction_history(limit=50):
    """
    Returns all investment ledger entries (Varlık Alımı + Varlık Satışı)
    ordered by most recent first, for the 'Varlık Geçmişi' section.
    """
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            -- `id` yalnızca hata kaydı için seçiliyor: aşağıdaki iki
            -- [VERİ BÜTÜNLÜĞÜ] log satırı kaydı kimliğiyle işaretliyor.
            -- Eskiden sorguda YOKTU, dolayısıyla gerçek bir bozuk satırda
            -- hata işleyicisinin KENDİSİ `IndexError` ile çöküyordu; bu
            -- yol hiç çalıştırılmadığı için fark edilmemişti
            -- (tests/test_decrypt_error_contract.py yakaladı).
            SELECT id, type, category, amount, description,
                   strftime('%d/%m/%Y %H:%M', transaction_date) as t_date
            FROM transactions
            WHERE category IN ('Varlık Alımı', 'Varlık Satışı')
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

    result = []
    for r in rows:
        try:
            dec_amount = float(decrypt(str(r["amount"]), SECRET_KEY))
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] transactions id={r['id']} tutar çözülemedi")
            dec_amount = 0.0
        try:
            dec_desc = decrypt(str(r["description"]), SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] transactions id=%s açıklaması çözülemedi",
                r["id"])
            dec_desc = ""
        result.append({
            "type":        r["type"],
            "category":    r["category"],
            "amount":      dec_amount,
            "description": dec_desc,
            "date":        r["t_date"],
        })
    return result


# ─── Tekrarlanan Ödemeler ─────────────────────────────────────────────────────

def insert_recurring_payment(
        name, amount, category, frequency, next_due_date, auto_deduct,
        account_id=DEFAULT_ACCOUNT_ID, recurrence_day=None,
        transaction_type="expense"):
    if recurrence_day is None:
        recurrence_day = int(str(next_due_date)[8:10])
    recurrence_day = int(recurrence_day)
    if not 1 <= recurrence_day <= 31:
        raise ValueError("Tekrarlama günü 1 ile 31 arasında olmalıdır.")
    transaction_type = str(transaction_type or "expense").strip().lower()
    if transaction_type not in ("income", "expense"):
        raise ValueError("Tekrarlanan işlem türü income veya expense olmalıdır.")
    # TUTAR BURADA DOĞRULANIYOR — paranın veriye dönüştüğü nokta burası.
    # Eskiden hiç doğrulanmıyordu: `str(amount)` ne verilirse şifreleyip
    # yazıyordu, yani `nan`, `inf`, `-inf`, negatif ve sıfır tutarlar
    # KALICI olarak diske giriyordu (ölçüldü: sekiz değerin sekizi de kabul
    # edildi). Arayüz bunları üretemiyordu (`parse_amount` yalnız rakam ve
    # ayraç kabul eder) ama servis sınırı açıktı; ve bir kez yazıldıktan
    # sonra tahsilat yolu değil, AYLIK BÜTÇE kırılıyordu — `nan` okuma
    # yolunda "geçerli" sayılıp bütçe rezervini hesaplanamaz hâle
    # getiriyordu.
    #
    # `fiat` projenin ortak para primitifi: sonlu olmayanı ve sayı olmayanı
    # reddeder, kuruşa yuvarlar. Yuvarlama BİLİNÇLİ — tahsilat yolu zaten
    # `fiat(payment["amount"])` ile kesiyor, yani saklanan tutar artık
    # gerçekten kesilecek tutarla aynı (aynı gerekçe: `insert_debt`).
    try:
        amount_decimal = fiat(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("Tekrarlanan işlem tutarı geçerli bir sayı olmalıdır.") from exc
    if amount_decimal <= 0:
        raise ValueError("Tekrarlanan işlem tutarı 0'dan büyük olmalıdır.")
    with managed_connection() as conn:
        cursor = conn.cursor()
        enc_name = encrypt(str(name), SECRET_KEY)
        enc_amount = encrypt(str(amount_decimal), SECRET_KEY)
        cursor.execute("""
            INSERT INTO recurring_payments
                (name, amount, category, frequency, next_due_date, recurrence_day,
                 auto_deduct, is_active, account_id, transaction_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            enc_name, enc_amount, category, frequency, next_due_date,
            recurrence_day, int(bool(auto_deduct)), account_id,
            transaction_type,
        ))
        conn.commit()


def has_active_recurring_payment(name):
    """Aktif tekrarlanan ödemeler arasında aynı isimde (büyük/küçük harf
    duyarsız) bir kayıt olup olmadığını kontrol eder. İsimler şifreli
    tutulduğundan SQL WHERE ile aranamaz; aktif kayıtlar çözülüp Python'da
    karşılaştırılır (abonelik duplikasyonunu engellemek için)."""
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM recurring_payments WHERE is_active = 1")
        rows = cursor.fetchall()

    target = str(name).strip().lower()
    for r in rows:
        try:
            existing_name = decrypt(r["name"], SECRET_KEY)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            # Arama döngüsü: çözülemeyen kayıt eşleşme sayılamaz, atlanır.
            # Yine de iz bırakılır — sessiz atlama, "böyle bir kayıt yok" ile
            # "kayıt bozuk" arasındaki farkı siler ve mükerrer abonelik
            # oluşmasına yol açabilir.
            from utils.logging_config import get_logger
            get_logger().exception(
                "[VERİ BÜTÜNLÜĞÜ] recurring_payments adı çözülemedi, "
                "isim çakışma kontrolünde atlandı")
            continue
        if existing_name.strip().lower() == target:
            return True
    return False


def get_active_recurring_payments():
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recurring_payments WHERE is_active = 1 ORDER BY next_due_date ASC")
        rows = cursor.fetchall()

    payments = []
    for r in rows:
        try:
            dec_name = decrypt(r["name"], SECRET_KEY)
            # ÇÖZÜLEBİLMEK YETMEZ, SAYI DA OLMALI. `float("nan")` ve
            # `float("inf")` istisna ÜRETMEZ; doğrulama yalnız decrypt'e
            # bakarsa `nan` buradan "geçerli tutar" olarak çıkar ve
            # `amount_is_valid` bayrağı — tam da toplam alan tarafı korumak
            # için var olan bayrak — yalan söyler. `decimal_from` projenin
            # ortak sınırı ve sonlu olmayanı reddediyor; yazma yolları artık
            # kapalı olduğu için buraya ancak eski bir yapının ya da dışarıdan
            # düzenlemenin bıraktığı satır düşebilir.
            amount_decimal = decimal_from(decrypt(r["amount"], SECRET_KEY))
            # POZİTİFLİK DE SONLULUK KADAR SÖZLEŞMENİN PARÇASI. Buradaki
            # tutar bir BÜYÜKLÜK; yön `transaction_type` (income/expense)
            # ile taşınır (bkz. process_due_recurring_payment ->
            # adjust_account_balance). Dolayısıyla sıfır ya da negatif bir
            # tutar "ters yönlü ödeme" değil, GEÇERSİZ kayıttır — üç yazma
            # yolunun üçü de (insert/update/charge) onu reddediyor.
            #
            # Sonlu olmama gürültülü kırılıyordu, negatif ise SESSİZ: eski
            # bir yapının bıraktığı -10,00'lık satır bütçe rezervine
            # -10,00 olarak giriyor ve "harcanabilir" tutarı 10 TL FAZLA
            # gösteriyordu (ölçüldü). Sessiz yanlış toplam, gürültülü
            # hatadan kötüdür.
            #
            # Veri DÜZELTİLMİYOR: `abs()` alınmıyor, satır güncellenmiyor.
            # Yalnızca "bu tutara güvenilemez" deniyor.
            if amount_decimal <= 0:
                raise ValueError("recurring amount must be positive")
            dec_amount = float(amount_decimal)
        except KeyUnavailableError:
            raise
        except (DecryptionError, ValueError, TypeError):
            from utils.logging_config import get_logger
            get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] recurring_payments id={r['id']} okunamadı")
            dec_name = "Bilinmeyen Ödeme"
            dec_amount = 0.0
            amount_is_valid = False
        else:
            amount_is_valid = True
        payments.append({
            "id":            r["id"],
            "name":          dec_name,
            "amount":        dec_amount,
            # Bu satır DÖRT görüntü listesini VE bütçe rezervi toplamını
            # birden besliyor. Fonksiyonun tamamen raise etmesi listeleri de
            # kırardı; 0.0'ı sessizce toplamak ise bütçeyi yanlış gösterirdi.
            # Bayrak ikisini ayırıyor: listeler "Bilinmeyen Ödeme" gösterip
            # çalışmaya devam eder, TOPLAM alan taraf (budget_service)
            # bayrağı görüp reddeder.
            "amount_is_valid": amount_is_valid,
            "category":      r["category"],
            "frequency":     r["frequency"],
            "next_due_date": r["next_due_date"],
            "recurrence_day": r["recurrence_day"],
            "auto_deduct":   bool(r["auto_deduct"]),
            "account_id":    r["account_id"],
            "transaction_type": (
                r["transaction_type"]
                if "transaction_type" in r.keys()
                else "expense"
            ),
        })
    return payments


def deactivate_recurring_payment(payment_id):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE recurring_payments SET is_active = 0 WHERE id = ?", (payment_id,))
        conn.commit()


def _advance_due_date(date_str, frequency):
    """Vadeyi desteklenen sıklık kadar ileri alır.

    Haftalık periyotlar sabit gün, aylık periyotlar takvim ayı üzerinden
    ilerler. Böylece 31 Ocak + üç ay 30 Nisan olur; bilinmeyen bir değer de
    sessizce aylık kabul edilmek yerine açıkça reddedilir.
    """
    from datetime import date, timedelta
    import calendar

    d = date.fromisoformat(date_str)
    if frequency == "weekly":
        return (d + timedelta(days=7)).isoformat()
    if frequency == "biweekly":
        return (d + timedelta(days=14)).isoformat()
    if frequency == "yearly":
        try:
            return d.replace(year=d.year + 1).isoformat()
        except ValueError:
            return d.replace(year=d.year + 1, day=28).isoformat()
    if frequency not in ("monthly", "quarterly"):
        raise ValueError(f"Desteklenmeyen tekrarlama sıklığı: {frequency}")

    months = 3 if frequency == "quarterly" else 1
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day).isoformat()


def process_due_recurring_payment(payment):
    """Vadesi gelen tekrarlanan gelir/gideri işler ve vadeyi ilerletir."""
    from datetime import datetime
    # Sıklığı herhangi bir finansal yazımdan önce doğrula. Geçersiz eski bir
    # kayıt transaction/bakiye yazıp sonra vade hesabında yarım kalmamalı.
    from services.recurring_service import next_due_for_recurrence
    from utils.financial_decimal import fiat
    # Karar Decimal'de veriliyor, yazma float'ta: `sqlite3`'ün Decimal adaptörü
    # yok ve bu şemadaki para REAL. İki aşama AYRI İSİMLE duruyor — aynı adı
    # önce Decimal sonra float'a bağlamak geçişi görünmez kılıyor ve tip
    # denetleyicinin de haklı olarak itiraz ettiği şey buydu.
    amount_decimal = fiat(payment["amount"])
    if amount_decimal <= 0:
        raise ValueError("Tekrarlanan işlem tutarı 0'dan büyük olmalıdır.")
    amount = float(amount_decimal)
    new_due = next_due_for_recurrence(
        payment["next_due_date"],
        payment["frequency"],
        payment.get("recurrence_day")
        or int(str(payment["next_due_date"])[8:10]),
    )
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        # Stale UI objects intentionally retain the old due date.  The marker
        # therefore keys the financial generation, not the mutable next due.
        cursor.execute(
            "INSERT OR IGNORE INTO recurring_operation_markers "
            "(recurring_payment_id, due_date, operation_type) VALUES (?, ?, 'charge')",
            (payment["id"], payment["next_due_date"]),
        )
        if cursor.rowcount == 0:
            return False
        transaction_type = str(
            payment.get("transaction_type") or "expense"
        ).strip().lower()
        if transaction_type not in ("income", "expense"):
            raise ValueError("Geçersiz tekrarlanan işlem türü.")
        from services.account_service import AccountService
        # AYNI CURSOR. `check_spending_allowed` kendi bağlantısını açar ve
        # kendi sözleşmesi "bir yazmanın önünde koruma olarak kullanma" diyor
        # (bkz. o fonksiyonun docstring'i). `transaction_service` ve
        # `asset_purchase_service` kararı zaten `BEGIN IMMEDIATE`'in arkasına,
        # çağıranın cursor'ına taşımıştı; bu yol dışarıda kalmıştı. Karar
        # burada da yazma kilidinin İÇİNDEN veriliyor: fazladan bağlantı
        # açılmıyor ve kontrol, yazmanın gördüğü durumu görüyor.
        AccountService.assert_spending_allowed(
            cursor, payment["account_id"], amount, transaction_type,
        )
        enc_amount = encrypt(str(amount), SECRET_KEY)
        enc_desc = encrypt(f"{payment['name']} (Otomatik)", SECRET_KEY)
        tx_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # `lastrowid` CURSOR'A AİT, deyime değil: aynı cursor'la yapılan her
        # INSERT onu ezer. İşlem satırının id'si bu yüzden HEMEN buraya
        # alınıyor. Alınmazsa `adjust_account_balance` içindeki
        # `record_balance_event` INSERT'ü değeri balance_events id'siyle
        # değiştirir ve araya giren UPDATE'ler onu geri getirmez — marker
        # aşağıda işlemi değil defter satırını göstermeye başlardı (ölçüldü:
        # transactions.id=1 iken marker.transaction_id=2).
        cursor.execute("""
            INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payment["account_id"], enc_amount, transaction_type,
            payment["category"], enc_desc, tx_date,
        ))
        transaction_id = cursor.lastrowid
        adjust_account_balance(
            cursor, payment["account_id"], transaction_type,
            amount, ref_id=transaction_id,
            source="recurring_payment",
        )

        cursor.execute("UPDATE recurring_payments SET next_due_date = ? WHERE id = ?", (new_due, payment["id"]))
        cursor.execute(
            "UPDATE recurring_operation_markers SET transaction_id=? "
            "WHERE recurring_payment_id=? AND due_date=? AND operation_type='charge'",
            (transaction_id, payment["id"], payment["next_due_date"]),
        )
        conn.commit()
    return True

def update_debt_last_auto_pay(debt_id, current_month_str):
    with managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_debts
            SET last_auto_pay_date = ?
            WHERE id = ?
        """, (current_month_str, debt_id))
        conn.commit()
