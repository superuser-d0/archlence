import sqlite3

from utils.errors import (
    ArchlenceError,
    DecryptionError,
    FinancialDataIntegrityError,
    KeyUnavailableError,
)
from database.db import (
    COMPLETED_TX, COMPLETED_TX_T, get_connection, managed_connection,
    adjust_account_balance,
)
from services.account_service import AccountService
from utils.crypto import encrypt, decrypt
from utils.financial_decimal import decimal_from, fiat
from datetime import datetime

SECRET_KEY = "fi" + "nora_secure_2026"

# Taksit planları tablosu tembel (lazy) oluşturulur — asset_service'teki
# asset_price_cache ile aynı desen; init_db'ye dokunmadan şema genişler.
_INSTALLMENTS_TABLE = "installment_plans"


def _period_date_cond(filter_type: str, column: str) -> str:
    """Dashboard dönem filtresini (Bugün/1 Hafta/...) bir SQL tarih koşuluna
    çevirir. `get_transactions_by_period` ve açılış bakiyesi sorgusu AYNI
    dönem tanımını kullanmalı — aksi halde "Bugün" filtresinde işlemler bir
    tarih aralığından, açılış bakiyesi başka bir aralıktan okunurdu.

    `column` çağıranın SQL'inde zaten var olan bir sütun/ifade olmalı (örn.
    "t.transaction_date", "ts"); değerler yalnızca bu sabit listeden geldiği
    için f-string'e gömülmesi güvenlidir (kullanıcı girdisi asla girmez).
    """
    if filter_type == "1 Hafta":
        return f"date({column}) >= date('now', '-7 days', 'localtime')"
    if filter_type == "1 Ay":
        return f"date({column}) >= date('now', '-1 month', 'localtime')"
    if filter_type == "1 Yıl":
        return f"date({column}) >= date('now', '-1 year', 'localtime')"
    if filter_type == "Hayat Boyu":
        return f"date({column}) IS NOT NULL"
    return f"date({column}) = date('now', 'localtime')"


def _ensure_installments_table(cursor) -> None:
    """Tutarlar diğer tablolardaki gibi şifreli TEXT tutulur (SQL'de toplanmaz,
    Python'da çözülür); taksit sayaçları sorgulanabilir düz INTEGER kalır."""
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS {_INSTALLMENTS_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        total_amount TEXT NOT NULL,
        monthly_amount TEXT NOT NULL,
        total_installments INTEGER NOT NULL,
        paid_installments INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""")


class TransactionService:
    @staticmethod
    def add_transaction(account_id, amount, transaction_type, category, description,
                        transaction_date=None, enforce_credit_limit=True,
                        installments=None, detect_subscription=True):
        """transaction_date verilmezse şu an kullanılır; CSV içe aktarımı gibi
        geçmiş tarihli kayıtlar tarihi açıkça geçer — bakiye senkronu dahil
        aynı atomik yoldan geçmiş olurlar.

        Kredi kartından yapılan giderlerde kullanılabilir limit kontrol edilir ve
        aşılıyorsa ValueError fırlatılır. CSV içe aktarımı gibi geçmişi olduğu
        gibi yeniden kuran çağıranlar `enforce_credit_limit=False` geçebilir —
        aksi halde geçmişte limiti zorlamış gerçek bir harcama içe aktarılamazdı.

        `installments` (2-12) verilirse işlem taksitli kredi kartı harcamasıdır:
        tutarın tamamı karta tek seferde borç yazılır (banka limiti toplam tutar
        kadar bloke eder), ayrıca AYNI commit içinde installment_plans'a aylık
        taksit planı eklenir (aylık tutar = toplam / taksit sayısı). Böylece
        işlem ile plan hiçbir zaman birbirinden kopamaz.
        """
        # This is the shared service boundary for user/API/import monetary
        # input.  SQLite must never be allowed to decide what NaN/Infinity
        # means for a financial operation.
        amount = fiat(amount)
        if amount <= 0:
            raise ValueError("İşlem tutarı 0'dan büyük olmalıdır.")
        # sqlite3 has no Decimal adapter; all persisted money in this legacy
        # schema is REAL, so pass the already-quantized finite value only.
        amount = float(amount)
        if installments is not None:
            installments = int(installments)
            if not 1 <= installments <= 12:
                raise ValueError("Taksit sayısı 1 ile 12 arasında olmalıdır.")
            if installments == 1:
                installments = None  # 1 taksit = tek çekim; plan kaydı gereksiz.

        # Donma kuralı gelir/gider ayrımı yapmadan ve CSV'nin geçmiş-limit
        # istisnasından bağımsız uygulanır. `enforce_credit_limit=False`
        # yalnız eski limit aşımını kabul eder; donmuş hesabı bypass etmez.
        # Hesabın varlığını burada doğrula: ileri tarihli (pending) kayıtlar
        # adjust_account_balance'ı HİÇ çağırmaz, dolayısıyla oradaki koruma bu
        # yolu kapsamaz. Kontrol olmasa sahipsiz bir pending satırı yazılır ve
        # vadesi geldiğinde settle sırasında sessizce başarısız olurdu.
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # The limit decision and the balance write must observe the same
            # SQLite snapshot. BEGIN IMMEDIATE serializes competing card
            # charges before either can consume the same available limit.
            cursor.execute("BEGIN IMMEDIATE")
            account = cursor.execute(
                "SELECT account_type, type, balance, credit_limit, is_frozen "
                "FROM accounts WHERE id=?", (account_id,)
            ).fetchone()
            if account is None:
                raise ValueError(f"Hesap bulunamadı (id={account_id}); işlem kaydedilemedi.")
            if bool(account["is_frozen"]):
                raise ValueError("Bu kart dondurulduğu için işlem yapılamaz.")
            is_expense = transaction_type in ("expense", "Gider")
            account_type = account["account_type"] or (
                "credit_card" if account["type"] == "credit" else "checking"
            )
            limit = float(account["credit_limit"] or 0)
            if (enforce_credit_limit and is_expense and
                    account_type == "credit_card" and limit > 0):
                debt = max(0.0, -float(account["balance"] or 0))
                if fiat(debt + amount) > fiat(limit):
                    raise ValueError("Limit yetersiz.")

            # Yalnızca tutar ve açıklama şifrelenir; type/category düz metin kalır
            # çünkü SQL sorguları (filtreleme ve categories JOIN'i) bu kolonlar
            # üzerinden çalışıyor — şifrelenirlerse raporlama sorguları bozulur.
            str_amount = str(amount)
            encrypted_amount = encrypt(str_amount, SECRET_KEY)
            encrypted_description = encrypt(description, SECRET_KEY)

            # transaction_date DB tarafında değil uygulamada üretilir; böylece
            # get_transactions_by_period'daki 'localtime' filtreleriyle aynı
            # saat diliminde kalır.
            date_now = transaction_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Check if transaction is in the future
            from datetime import datetime as dt
            parsed_date = dt.strptime(date_now[:10], "%Y-%m-%d") if len(date_now) >= 10 else dt.now()
            is_future = parsed_date.date() > dt.now().date()
            status = 'pending' if is_future else 'completed'

            cursor.execute("""
                INSERT INTO transactions (account_id, amount, type, category, description, transaction_date, status, execution_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (account_id, encrypted_amount, transaction_type, category, encrypted_description, date_now, status, date_now))

            # Hesaplar Kopuk düzeltmesi: accounts.balance işlemle aynı commit'te
            # senkron güncellenir (gelir artırır, gider azaltır).
            # SADECE geçmiş veya bugüne ait işlemler bakiyeye etki eder!
            if not is_future:
                adjust_account_balance(cursor, account_id, transaction_type, amount)

            if installments:
                # Taksit planı işlemle AYNI commit'te yazılır (atomiklik).
                #
                # Bölme Decimal'de: `round(float(amount)/n, 2)` anaparayı
                # korumuyordu. 1000,00 TL / 3 -> 333,33 ve 3 x 333,33 = 999,99;
                # 12.500,00 / 12 -> 1.041,67 ve 12 x 1.041,67 = 12.500,04.
                # Yani plan, anaparadan SAPAN bir borç gösteriyordu
                # ve sapma iki yönde de olabiliyordu.
                monthly = fiat(decimal_from(amount) / installments)
                _ensure_installments_table(cursor)
                cursor.execute(f"""
                    INSERT INTO {_INSTALLMENTS_TABLE}
                        (account_id, description, total_amount, monthly_amount,
                         total_installments, paid_installments, created_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                """, (
                    account_id,
                    encrypted_description,
                    encrypt(str(amount), SECRET_KEY),
                    encrypt(str(monthly), SECRET_KEY),
                    installments,
                    date_now,
                ))

            conn.commit()
        finally:
            conn.close()

        # ── ABONELİK INTERCEPTOR ────────────────────────────────────────────
        # İşlem defterine yazıldıktan SONRA çalışır: abonelik gibi görünen bir
        # gider ayrıca "Aktif Aboneliklerim" radarına da kaydedilir. İşlemin
        # kendi commit'inin dışında tutuluyor, çünkü radar kaydı yardımcı bir
        # kolaylık — orada çıkan bir hata kullanıcının gerçek harcamasının
        # kaydedilmesini ASLA geri almamalı.
        if detect_subscription and transaction_type in ("expense", "Gider"):
            try:
                from services.recurring_service import (
                    register_subscription_from_transaction,
                )
                account = AccountService.get_account(account_id)
                is_credit_card = bool(
                    account and account.get("account_type") == "credit_card")
                register_subscription_from_transaction(
                    account_id=account_id,
                    amount=amount,
                    category=category,
                    description=description,
                    transaction_date=date_now,
                    is_credit_card=is_credit_card,
                )
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik radarına yazılamadı")

    @staticmethod
    def settle_due_transactions(today=None):
        """Vadesi gelmiş ileri tarihli işlemleri bakiyeye işler.

        add_transaction ileri tarihli bir kaydı status='pending' yazar ve
        bakiyeye DOKUNMAZ (bankacılık davranışı: para tarih gelmeden hesapta
        görünmez). Bu metod o kayıtları vadesi geldiğinde 'completed'e çevirip
        bakiyeyi uygular; çağrılmazsa ileri tarihli gelir/gider bakiyeye hiç
        yansımaz.

        Her satır kendi SAVEPOINT'inde işlenir: tutarı çözülemeyen bozuk tek
        bir kayıt, vadesi gelen diğer işlemleri bloklamaz. Sorgu 'pending'e
        göre filtrelediği ve satırı 'completed' yaptığı için tekrar çağrılmak
        güvenlidir (idempotent) — aynı işlem iki kez bakiyeye işlenmez.

        Kredi limiti burada YENİDEN kontrol edilmez: vadesi gelen bir fatura
        gerçek hayatta da limit dolu diye "işlenmemiş" sayılmaz, karta borç
        olarak düşer. Limit kontrolü kaydın oluşturulduğu anda yapılmıştır.

        Bakiyeye işlenen işlem sayısını döndürür.
        """
        reference_day = today or datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT t.id, t.account_id, t.amount, t.type,"
                " COALESCE(a.is_frozen, 0) AS is_frozen"
                " FROM transactions AS t"
                " LEFT JOIN accounts AS a ON a.id = t.account_id"
                " WHERE status = 'pending' AND date(execution_date) <= date(?)"
                " ORDER BY date(execution_date), t.id",
                (reference_day,),
            )
            due_rows = cursor.fetchall()

            settled = 0
            for row in due_rows:
                # Planlandıktan sonra hesap dondurulmuş olabilir. Vade gelince
                # donmayı bypass edip bakiyeyi değiştirme; kayıt pending kalsın.
                if bool(row["is_frozen"]):
                    continue
                try:
                    amount = float(decrypt(str(row["amount"]), SECRET_KEY))
                except KeyUnavailableError:
                    raise
                except (DecryptionError, ValueError, TypeError):
                    from utils.logging_config import get_logger
                    get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] pending işlem id={row['id']} tutarı çözülemedi")
                    # Tutar çözülemiyorsa bakiyeye körlemesine dokunmaktansa
                    # kaydı pending bırak; kullanıcı veriyi düzeltebilir.
                    continue

                cursor.execute("SAVEPOINT settle_tx")
                try:
                    adjust_account_balance(
                        cursor, row["account_id"], row["type"], amount,
                        ref_id=row["id"],
                    )
                    cursor.execute(
                        "UPDATE transactions SET status = 'completed' WHERE id = ?",
                        (row["id"],),
                    )
                except (sqlite3.Error, ValueError, ArchlenceError):
                    # Gerçekçi küme: `adjust_account_balance` hesap bulunamazsa
                    # ValueError, veri bütünlüğü bozuksa ArchlenceError türevi
                    # (FinancialDataIntegrityError) fırlatır; UPDATE ise
                    # sqlite3.Error. Bir satırın yerleşememesi KALAN vadesi
                    # gelmiş işlemleri iptal etmemeli, o yüzden burada durup
                    # döngü sürüyor — ama artık SESSİZ değil: bu blok eskiden
                    # hiç loglamıyordu, yani kullanıcının kirası/maaşı hiç
                    # işlenmeden geçtiğinde ortada tek bir iz kalmıyordu.
                    from utils.logging_config import get_logger
                    get_logger().exception(
                        f"Vadesi gelen işlem yerleştirilemedi (id={row['id']}), "
                        "kalan işlemler sürdürülüyor"
                    )
                    cursor.execute("ROLLBACK TO SAVEPOINT settle_tx")
                else:
                    cursor.execute("RELEASE SAVEPOINT settle_tx")
                    settled += 1

            conn.commit()
        finally:
            conn.close()

        return settled

    @staticmethod
    def get_pending_transactions():
        """Henüz vadesi gelmemiş (bakiyeye işlenmemiş) işlemleri döndürür.

        "Bekleyen İşlemler" panelinin veri kaynağı. Tutar/açıklama şifreli
        olduğu için Python'da çözülür; sıralama düz kolon üzerinden SQL'de.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, account_id, amount, type, category, description,"
                " execution_date FROM transactions WHERE status = 'pending'"
                " ORDER BY date(execution_date), id"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        items = []
        for r in rows:
            try:
                amount = float(decrypt(str(r["amount"]), SECRET_KEY))
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] pending işlem id={r['id']} tutarı çözülemedi")
                amount = 0.0
            try:
                description = decrypt(str(r["description"]), SECRET_KEY) or ""
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] pending işlem id={r['id']} açıklaması çözülemedi")
                description = ""
            items.append({
                "id": r["id"],
                "account_id": r["account_id"],
                "amount": amount,
                "type": r["type"],
                "category": r["category"] or "",
                "description": description.strip() or (r["category"] or "İşlem"),
                "execution_date": (r["execution_date"] or "")[:10],
            })
        return items

    @staticmethod
    def cancel_pending_transaction(transaction_id):
        """Bekleyen bir işlemi siler.

        Yalnızca status='pending' satırları silinir; bakiyeye işlenmiş bir
        kaydın buradan sessizce yok edilmesi bakiye ile defteri ayrıştırırdı.
        Silindiyse True döner.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM transactions WHERE id = ? AND status = 'pending'",
                (int(transaction_id),),
            )
            deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
        return deleted > 0

    @staticmethod
    def reschedule_pending_transaction(transaction_id, new_date):
        """Bekleyen bir işlemin vadesini değiştirir.

        Yeni tarih bugüne çekilirse kayıt bir sonraki settle turunda
        kendiliğinden bakiyeye işlenir — burada ayrıca bakiye uygulanmaz ki
        işleme mantığı tek yerde (settle_due_transactions) kalsın.
        """
        day = str(new_date)[:10]
        datetime.strptime(day, "%Y-%m-%d")  # biçim doğrulaması
        # Saat bileşeni KORUNUR: transaction_date'i tarih-only yazmak
        # ui/charts.py'nin zaman kovalarını bozuyordu (tek bir tarih-only satır
        # tüm zaman grafiğini sessizce çizilmez hâle getiriyor). Projedeki
        # konvansiyon her zaman "%Y-%m-%d %H:%M:%S".
        stamp = f"{day} 09:00:00"

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET transaction_date = ?, execution_date = ?"
                " WHERE id = ? AND status = 'pending'",
                (stamp, stamp, int(transaction_id)),
            )
            updated = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
        return updated > 0

    @staticmethod
    def get_installment_plans(account_id):
        """Bir kartın devam eden taksit planlarını (kalan taksidi olanları) döndürür.

        'Gelecek Ödemeler' diyaloğunun veri kaynağı. Tutarlar şifreli TEXT
        olduğundan Python'da çözülür (get_recent_for_account ile aynı desen).
        Her eleman: description, total_amount, monthly_amount,
        total_installments, paid_installments, remaining_installments,
        remaining_amount, created_at.
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            _ensure_installments_table(cursor)
            cursor.execute(
                f"SELECT * FROM {_INSTALLMENTS_TABLE}"
                " WHERE account_id = ? AND paid_installments < total_installments"
                " ORDER BY created_at DESC, id DESC",
                (int(account_id),),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        plans = []
        for r in rows:
            try:
                # decimal_from ŞİFRE ÇÖZÜLMÜŞ METİN üzerinden çağrılıyor,
                # float üzerinden değil: araya bir float sokmak, kaçınmak
                # istediğimiz ikili yaklaşıklığı geri getirirdi.
                total = decimal_from(decrypt(str(r["total_amount"]), SECRET_KEY))
                monthly = decimal_from(
                    decrypt(str(r["monthly_amount"]), SECRET_KEY)
                )
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] taksit planı id={r['id']} tutarı çözülemedi")
                continue
            # Açıklama, transactions tablosundaki konvansiyonla aynı şekilde
            # şifreli durur; çözülemezse plan gizlenmez, ad boş bırakılmaz.
            try:
                plan_description = decrypt(str(r["description"]), SECRET_KEY) or "Taksitli İşlem"
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception(f"[VERİ BÜTÜNLÜĞÜ] taksit planı id={r['id']} açıklaması çözülemedi")
                plan_description = "Taksitli İşlem"
            paid_count = int(r["paid_installments"])
            remaining = int(r["total_installments"]) - paid_count
            # Kalan borç ANAPARADAN türetiliyor, `aylık x kalan`dan değil.
            # Eski formül eşit taksitler varsayıyordu; bölme tam bölünmüyorsa
            # taksitlerin toplamı anaparayı tutmaz. Anaparadan ödenen kısmı
            # düşmek, farkı doğal olarak SON taksite yüklüyor: 1000,00 / 3 ->
            # 333,33 + 333,33 + 333,34, toplam tam olarak 1000,00.
            remaining_amount = fiat(total - monthly * paid_count)
            plans.append({
                "id": r["id"],
                "description": plan_description,
                # Dış arayüz float kalıyor: kusur temsilde değil HESAPTAydı ve
                # bu değerler zaten 2 haneye yuvarlanmış durumda. Decimal
                # döndürmek her çağıranı değiştirmeyi gerektirirdi.
                "total_amount": float(total),
                "monthly_amount": float(monthly),
                "total_installments": int(r["total_installments"]),
                "paid_installments": paid_count,
                "remaining_installments": remaining,
                "remaining_amount": float(remaining_amount),
                "created_at": r["created_at"],
            })
        return plans

    @staticmethod
    def get_transactions_by_period(filter_type):
        date_cond = _period_date_cond(filter_type, "t.transaction_date")

        with managed_connection() as conn:
            cursor = conn.cursor()
            # status filtresi: ileri tarihli (pending) işlemler bakiyeye
            # işlenmediği için raporlanan gelir/gider/tasarruf metriklerine de
            # girmemeli — yoksa bakiye ile dashboard birbirini tutmaz.
            cursor.execute(f"""
                SELECT t.amount, t.type, t.category, t.transaction_date, c.importance
                FROM transactions t
                LEFT JOIN categories c ON t.category = c.name
                WHERE {date_cond}
                  AND {COMPLETED_TX_T}
            """)
            rows = cursor.fetchall()

        data = []
        for r in rows:
            try:
                decrypted_amount = float(decrypt(r[0], SECRET_KEY))
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError) as exc:
                # 0.0'A DÜŞÜLMÜYOR — bu satırlar TOPLANIYOR. Tek çağıranı
                # `ui/charts.py`, değerleri kategoriye göre toplayıp pasta ve
                # trend grafiğini çiziyor. Bozuk bir tutarı 0,00 saymak,
                # kullanıcıya sessizce YANLIŞ bir grafik göstermek olurdu;
                # oysa grafiğin hiç çizilmemesi görünür ve dürüsttür.
                # Çağıran zaten `except Exception` ile boş grafiğe düşüp
                # logluyor, yani bu bir çökme değil nazik bir bozulma.
                # Aynı politika `financial_summary_service.decrypt_decimal`
                # ve `main.py::_apply_dashboard_integrity_error` ile birebir.
                raise FinancialDataIntegrityError(
                    "transactions", None, "amount", reason=exc
                ) from exc

            data.append({
                'amount': decrypted_amount,
                'type': r[1],
                'category': r[2] if r[2] else 'Diğer',
                'transaction_date': r[3],
                'importance': r[4] if r[4] else 'extra'
            })
        return data

    @staticmethod
    def get_opening_baseline_by_period(filter_type):
        """Seçili dönemde açılan hesapların (pozitif) açılış bakiyeleri toplamı.

        NEDEN: Hesap açılış bakiyesi `transactions` tablosuna hiç yazılmaz
        (yalnızca accounts.balance + balance_events('account_opened') —
        bkz. AccountService.create_account). Bu yüzden Varlıklarım
        sekmesindeki pasta/çizgi grafiği tamamen `get_transactions_by_period`
        üzerinden besleniyordu ve YENİ açılan tek hesaplı bir kullanıcı
        (henüz hiç işlem girmemiş) grafikte "Veri Yok" görüyordu — bakiyesi
        dolu olsa bile.

        Açılış bakiyesini gerçek bir "Ana Gelir" işlemi olarak YAZMIYORUZ:
        bilerek `transactions`'a hiç dokunmaz, böylece tasarruf oranı, 50-30-20
        sağlık skoru ve ODE günlük gelir girdisi gibi nakit-akışı analizleri
        açılış bakiyesiyle şişmez (bkz. DashboardService.get_opening_baseline,
        aynı ilke). Yalnızca BU özet için ayrı, görünür bir "Açılış Bakiyesi"
        dilimi döndürülür.

        Kredi kartı açılış BORCU (negatif delta) hariç tutulur — bir borcun
        gelir pastasında görünmesi anlamsız olurdu.
        """
        return round(
            sum(
                event["amount"]
                for event in TransactionService.get_opening_events_by_period(
                    filter_type)
            ),
            2,
        )

    @staticmethod
    def get_opening_events_by_period(filter_type):
        """Açılış bakiyelerini ZAMAN DAMGASIYLA döndürür (grafik kovaları için).

        `get_opening_baseline_by_period` yalnız toplamı verir; zaman grafiği
        (CurvedTrendChart) ise her olayı kendi saat/gün/ay kovasına koymak
        zorunda olduğundan tarihe de ihtiyaç duyar. İşlem sözlükleriyle AYNI
        alan adları (`amount`, `transaction_date`) kullanılır ki
        `_build_time_buckets` iki kaynağı tek bir döngüde işleyebilsin.
        """
        conn = get_connection()
        try:
            date_cond = _period_date_cond(filter_type, "ts")
            rows = conn.execute(f"""
                SELECT ts, delta FROM balance_events
                WHERE entity_type = 'account' AND source = 'account_opened'
                  AND {date_cond}
                ORDER BY ts
            """).fetchall()
        finally:
            conn.close()
        return [
            {"amount": float(row[1]), "transaction_date": row[0]}
            for row in rows
            if row[1] and row[1] > 0
        ]

    @staticmethod
    def get_recent_for_account(account_id, limit=3):
        """Bir hesaba/karta ait son işlemleri (tarih, açıklama, tutar) döndürür.

        "Kart Kullanım Özeti" panelinin veri kaynağı. amount ve description
        şifreli TEXT olduğu için SQL'de toplanamaz/aranamaz; satırlar çekilip
        Python'da çözülür (main.py::update_metrics_and_goals ile aynı desen).
        Sıralama ve LIMIT düz sütunlar üzerinden yapıldığı için SQL'de kalır.
        """
        from database.db import get_connection, SECRET_KEY
        from utils.crypto import decrypt

        conn = get_connection()
        try:
            cursor = conn.cursor()
            sql = (
                "SELECT amount, type, category, description, transaction_date"
                " FROM transactions WHERE account_id = ?"
                f" AND {COMPLETED_TX}"
                " ORDER BY transaction_date DESC, id DESC"
            )
            params = [int(account_id)]
            if limit is not None:
                parsed_limit = int(limit)
                if parsed_limit < 0:
                    raise ValueError("limit negatif olamaz")
                sql += " LIMIT ?"
                params.append(parsed_limit)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        items = []
        for r in rows:
            try:
                amount = float(decrypt(str(r["amount"]), SECRET_KEY))
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception("[VERİ BÜTÜNLÜĞÜ] son işlem tutarı çözülemedi")
                amount = 0.0
            try:
                desc = decrypt(str(r["description"]), SECRET_KEY) or ""
            except KeyUnavailableError:
                raise
            except (DecryptionError, ValueError, TypeError):
                from utils.logging_config import get_logger
                get_logger().exception("[VERİ BÜTÜNLÜĞÜ] son işlem açıklaması çözülemedi")
                desc = ""
            items.append({
                "amount": amount,
                "type": r["type"],
                "category": r["category"] or "",
                # Açıklama boşsa kategori daha anlamlı bir etiket.
                "description": desc.strip() or (r["category"] or "İşlem"),
                "date": (r["transaction_date"] or "")[:10],
            })
        return items
