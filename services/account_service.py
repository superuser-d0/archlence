"""Çoklu hesap ve kredi kartı servisi.

accounts tablosunu okuyan/yazan tek nokta. Buradaki asıl iş, ham `balance`
sütunundaki İŞARETLİ değeri (bkz. database/db.py::adjust_account_balance) UI'ın
beklediği alanlara çevirmek: kredi kartları için pozitif `debt` ve
`available_limit`, vadesizler için düz `balance`.

Not: Hesap adı şifrelenmez. Diğer tablolarda (active_debts, recurring_payments)
isim AES ile şifreli tutuluyor ama accounts.name zaten uygulama açılışında
şifresiz seed ediliyor ("Nakit", "Banka", "Kredi Kartı") ve SUM/JOIN sorgularında
düz metin olarak kullanılıyor; sonradan şifrelemek mevcut satırları okunamaz
hale getirirdi.
"""
from database.db import ACCOUNT, get_connection, record_balance_event

CHECKING = "checking"
CREDIT_CARD = "credit_card"

# UI'daki tür seçici bu iki değeri gösterir; anahtarlar DB'ye yazılan
# account_type değerleridir, değerler kullanıcıya gösterilen Türkçe etiketlerdir.
ACCOUNT_TYPE_LABELS = {
    CHECKING: "Nakit / Vadesiz",
    CREDIT_CARD: "Kredi Kartı",
}


def _fmt_try(value):
    """Tutarı Türkçe biçimde (₺1.234,56) yazar — kullanıcıya gösterilen hata
    mesajları uygulamanın geri kalanıyla aynı biçimi kullansın diye."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class AccountService:

    @staticmethod
    def create_account(name, account_type, initial_balance=0.0,
                       credit_limit=0.0, statement_date=None,
                       card_number_full=None, expiry_date=None, cvc_code=None):
        """Yeni hesap/kart oluşturur ve eklenen satırın id'sini döndürür.

        Kredi kartı için `initial_balance` MEVCUT BORÇ olarak (pozitif sayı)
        beklenir ve DB'ye negatif bakiye olarak yazılır — çağıranın işaret
        çevirmesi gerekmez, kullanıcı "5000 TL borcum var" der, biz -5000 yazarız.

        ValueError fırlatır: boş ad, negatif tutar, kredi kartında limitsiz veya
        limitten büyük başlangıç borcu, geçersiz kesim günü.
        """
        name = (name or "").strip()
        if not name:
            raise ValueError("Hesap adı boş olamaz.")
        if account_type not in (CHECKING, CREDIT_CARD):
            raise ValueError(f"Bilinmeyen hesap türü: {account_type}")

        try:
            initial_balance = float(initial_balance or 0)
            credit_limit = float(credit_limit or 0)
        except (TypeError, ValueError):
            raise ValueError("Tutar ve limit sayısal olmalıdır.")

        if statement_date not in (None, ""):
            try:
                statement_date = int(statement_date)
            except (TypeError, ValueError):
                raise ValueError("Hesap kesim günü 1-31 arası bir sayı olmalıdır.")
            if not 1 <= statement_date <= 31:
                raise ValueError("Hesap kesim günü 1-31 arası olmalıdır.")
        else:
            statement_date = None

        if account_type == CREDIT_CARD:
            if credit_limit <= 0:
                raise ValueError("Kredi kartı için 0'dan büyük bir limit girilmelidir.")
            if initial_balance < 0:
                raise ValueError("Mevcut borç negatif olamaz.")
            if initial_balance > credit_limit:
                raise ValueError("Mevcut borç, kart limitini aşamaz.")
            # İşaretli konvansiyon: borç negatif bakiyedir.
            balance = -initial_balance
            legacy_type = "credit"
        else:
            balance = initial_balance
            credit_limit = 0.0
            statement_date = None
            legacy_type = "bank"
            
        from utils.crypto import encrypt
        from database.db import SECRET_KEY
        enc_card_number = encrypt(card_number_full, SECRET_KEY) if card_number_full else None
        enc_expiry = encrypt(expiry_date, SECRET_KEY) if expiry_date else None
        enc_cvc = encrypt(cvc_code, SECRET_KEY) if cvc_code else None

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (name, type, balance, account_type, credit_limit, statement_date, card_number_full, expiry_date, cvc_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, legacy_type, balance, account_type, credit_limit, statement_date, enc_card_number, enc_expiry, enc_cvc))
            account_id = cursor.lastrowid
            record_balance_event(cursor, ACCOUNT, account_id, balance, balance,
                                 "account_opened")
            conn.commit()
            return account_id
        finally:
            conn.close()

    @staticmethod
    def check_card_network(card_number):
        if not card_number: return ""
        num = str(card_number).replace(" ", "").replace("-", "")
        if num.startswith("4"): return "assets/visa.png"
        if num.startswith("5"): return "assets/mastercard.png"
        if num.startswith("9792"): return "assets/troy.png"
        return ""

    @staticmethod
    def _to_dict(row):
        account_type = row["account_type"]
        if not account_type:
            account_type = CREDIT_CARD if row["type"] == "credit" else CHECKING

        balance = float(row["balance"] or 0)
        credit_limit = float(row["credit_limit"] or 0)
        
        from utils.crypto import decrypt
        from database.db import SECRET_KEY
        
        # Determine masked number and network logo
        masked_number = "**** **** **** 0000"
        network_logo = ""
        if "card_number_full" in row.keys() and row["card_number_full"]:
            try:
                dec_num = decrypt(row["card_number_full"], SECRET_KEY)
                network_logo = AccountService.check_card_network(dec_num)
                # Keep only the last 4 digits
                last4 = dec_num[-4:] if len(dec_num) >= 4 else dec_num
                masked_number = f"**** **** **** {last4}"
            except Exception:
                pass

        if account_type == CREDIT_CARD:
            debt = max(0.0, -balance)
            available_limit = max(0.0, credit_limit - debt)
        else:
            debt = 0.0
            available_limit = 0.0

        return {
            "id": row["id"],
            "name": row["name"],
            "account_type": account_type,
            "type_label": ACCOUNT_TYPE_LABELS.get(account_type, account_type),
            "balance": round(balance, 2),
            "credit_limit": round(credit_limit, 2),
            "statement_date": row["statement_date"],
            "debt": round(debt, 2),
            "available_limit": round(available_limit, 2),
            "masked_number": masked_number,
            "network_logo": network_logo
        }

    @staticmethod
    def get_accounts():
        """Tüm hesapları türetilmiş alanlarıyla döndürür (vadesizler önce)."""
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT * FROM accounts
                ORDER BY CASE WHEN account_type = 'credit_card' THEN 1 ELSE 0 END, id
            """).fetchall()
        finally:
            conn.close()
        return [AccountService._to_dict(r) for r in rows]

    @staticmethod
    def get_account(account_id):
        """Tek hesabı döndürür; yoksa None."""
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        finally:
            conn.close()
        return AccountService._to_dict(row) if row else None

    @staticmethod
    def get_net_worth():
        """Net serveti bileşenleriyle birlikte döndürür.

        net = nakit toplamı - toplam kart borcu. İşaretli konvansiyon sayesinde
        bu, düz SUM(balance) ile birebir aynı sayıdır; burada ayrı ayrı
        hesaplanmasının sebebi UI'ın "Nakit ₺17.300 / Kart borcu ₺3.500" gibi
        dökümü gösterebilmesi.
        """
        cash = 0.0
        card_debt = 0.0
        for acc in AccountService.get_accounts():
            if acc["account_type"] == CREDIT_CARD:
                card_debt += acc["debt"]
            else:
                cash += acc["balance"]
        return {
            "cash": round(cash, 2),
            "card_debt": round(card_debt, 2),
            "net": round(cash - card_debt, 2),
        }

    @staticmethod
    def check_spending_allowed(account_id, amount):
        """Karttan yapılacak harcamanın limiti aşıp aşmadığını kontrol eder.

        (izin_var, hata_mesajı) döndürür. Vadesiz hesaplar için her zaman izin
        verilir — eksi bakiye uygulamada zaten kırmızı uyarıyla gösteriliyor,
        işlemi engellemiyoruz. Kredi kartında ise limit aşımı gerçek hayatta da
        bankaca reddedilir, o yüzden burada engelliyoruz.
        """
        acc = AccountService.get_account(account_id)
        if not acc:
            return False, "Hesap bulunamadı."
        if acc["account_type"] != CREDIT_CARD:
            return True, ""
        # Limit 0 = "belirlenmemiş", yasak değil. Migration'dan gelen eski kartlar
        # credit_limit=0 ile geliyor; bunları limitsiz saymazsak kullanıcının
        # mevcut kartından yapacağı HER harcama reddedilirdi.
        limit = float(acc["credit_limit"])
        if limit <= 0:
            return True, ""
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return False, "Geçersiz tutar."
        
        avail = float(acc["available_limit"])
        if amount > avail:
            return False, (
                f"Limit yetersiz: kullanılabilir limit "
                f"{_fmt_try(avail)}, harcama {_fmt_try(amount)}."
            )
        return True, ""
