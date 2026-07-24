from database.db import get_connection, adjust_account_balance
from services.account_service import AccountService
from utils.crypto import encrypt, decrypt
from datetime import datetime

SECRET_KEY = "fi" + "nora_secure_2026"

# Taksit planları tablosu tembel (lazy) oluşturulur — asset_service'teki
# asset_price_cache ile aynı desen; init_db'ye dokunmadan şema genişler.
_INSTALLMENTS_TABLE = "installment_plans"


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
                        installments=None):
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
        if installments is not None:
            installments = int(installments)
            if not 1 <= installments <= 12:
                raise ValueError("Taksit sayısı 1 ile 12 arasında olmalıdır.")
            if installments == 1:
                installments = None  # 1 taksit = tek çekim; plan kaydı gereksiz.

        if enforce_credit_limit and transaction_type in ("expense", "Gider"):
            allowed, reason = AccountService.check_spending_allowed(account_id, amount)
            if not allowed:
                raise ValueError(reason)

        conn = get_connection()
        try:
            cursor = conn.cursor()

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

            cursor.execute("""
                INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (account_id, encrypted_amount, transaction_type, category, encrypted_description, date_now))

            # Hesaplar Kopuk düzeltmesi: accounts.balance işlemle aynı commit'te
            # senkron güncellenir (gelir artırır, gider azaltır).
            adjust_account_balance(cursor, account_id, transaction_type, amount)

            if installments:
                # Taksit planı işlemle AYNI commit'te yazılır (atomiklik).
                monthly = round(float(amount) / installments, 2)
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
                total = float(decrypt(str(r["total_amount"]), SECRET_KEY))
                monthly = float(decrypt(str(r["monthly_amount"]), SECRET_KEY))
            except Exception:
                continue
            # Açıklama, transactions tablosundaki konvansiyonla aynı şekilde
            # şifreli durur; çözülemezse plan gizlenmez, ad boş bırakılmaz.
            try:
                plan_description = decrypt(str(r["description"]), SECRET_KEY) or "Taksitli İşlem"
            except Exception:
                plan_description = "Taksitli İşlem"
            remaining = int(r["total_installments"]) - int(r["paid_installments"])
            plans.append({
                "id": r["id"],
                "description": plan_description,
                "total_amount": total,
                "monthly_amount": monthly,
                "total_installments": int(r["total_installments"]),
                "paid_installments": int(r["paid_installments"]),
                "remaining_installments": remaining,
                "remaining_amount": round(monthly * remaining, 2),
                "created_at": r["created_at"],
            })
        return plans

    @staticmethod
    def get_transactions_by_period(filter_type):
        conn = get_connection()
        cursor = conn.cursor()
        
        # date_cond f-string ile SQL'e gömülüyor ama güvenli: değerler yalnızca
        # buradaki sabit listeden gelir, kullanıcı girdisi asla doğrudan girmez.
        if filter_type == "1 Hafta":
            date_cond = ">= date('now', '-7 days', 'localtime')"
        elif filter_type == "1 Ay":
            date_cond = ">= date('now', '-1 month', 'localtime')"
        elif filter_type == "1 Yıl":
            date_cond = ">= date('now', '-1 year', 'localtime')"
        elif filter_type == "Hayat Boyu":
            date_cond = "IS NOT NULL"
        else:
            date_cond = "= date('now', 'localtime')"
            
        cursor.execute(f"""
            SELECT t.amount, t.type, t.category, t.transaction_date, c.importance 
            FROM transactions t 
            LEFT JOIN categories c ON t.category = c.name 
            WHERE date(t.transaction_date) {date_cond}
        """)
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for r in rows:
            try:
                decrypted_amount = float(decrypt(r[0], SECRET_KEY))
            except Exception:
                decrypted_amount = 0.0

            data.append({
                'amount': decrypted_amount,
                'type': r[1],
                'category': r[2] if r[2] else 'Diğer',
                'transaction_date': r[3],
                'importance': r[4] if r[4] else 'extra'
            })
        return data

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
            except Exception:
                amount = 0.0
            try:
                desc = decrypt(str(r["description"]), SECRET_KEY) or ""
            except Exception:
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
