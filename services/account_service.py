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
                       credit_limit=0.0, statement_date=None):
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

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (name, type, balance, account_type, credit_limit, statement_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, legacy_type, balance, account_type, credit_limit, statement_date))
            account_id = cursor.lastrowid
            # [Faz 2 · defter 7/8] Hesap açılışı da bir bakiye hareketidir.
            # UPDATE değil INSERT olduğu için ilk taramada gözden kaçmıştı:
            # açılış bakiyesi deftere yazılmazsa replay toplamı hiçbir zaman
            # gerçek SUM(balance) ile tutmaz (açılış kadar eksik kalır).
            record_balance_event(cursor, ACCOUNT, account_id, balance, balance,
                                 "account_opened")
            conn.commit()
            return account_id
        finally:
            conn.close()

    @staticmethod
    def _to_dict(row):
        """accounts satırını türetilmiş alanlarla birlikte dict'e çevirir.

        Eski satırlarda account_type NULL olabilir (migration öncesi yazılmışsa);
        o durumda legacy `type` sütunundan türetilir ki UI hiçbir zaman türsüz
        hesap görmesin.
        """
        account_type = row["account_type"]
        if not account_type:
            account_type = CREDIT_CARD if row["type"] == "credit" else CHECKING

        balance = float(row["balance"] or 0)
        credit_limit = float(row["credit_limit"] or 0)

        if account_type == CREDIT_CARD:
            # balance negatif tutulur; borç onun mutlak değeridir. Kart artıya
            # geçmişse (fazla ödeme) borç 0'dır, negatif borç göstermeyiz.
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
        if acc["credit_limit"] <= 0:
            return True, ""
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return False, "Geçersiz tutar."
        if amount > acc["available_limit"]:
            return False, (
                f"Limit yetersiz: kullanılabilir limit "
                f"{_fmt_try(acc['available_limit'])}, harcama {_fmt_try(amount)}."
            )
        return True, ""
