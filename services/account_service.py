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
                       card_number_full=None):
        """Yeni hesap/kart oluşturur ve eklenen satırın id'sini döndürür.

        Kredi kartı için `initial_balance` MEVCUT BORÇ olarak (pozitif sayı)
        beklenir ve DB'ye negatif bakiye olarak yazılır — çağıranın işaret
        çevirmesi gerekmez, kullanıcı "5000 TL borcum var" der, biz -5000 yazarız.

        `card_number_full` YALNIZCA bu fonksiyonun ömrü boyunca ham hâliyle
        var olur — son-4-hane + kart ağını türetmek için burada kullanılır
        ve diske hiçbir zaman şifrelenip yazılmaz (bkz. docs/ROADMAP.md
        Faz 1 madde 1). Eskiden tam kart numarası, son kullanma tarihi ve
        CVC şifrelenip kalıcı sütunlarda saklanıyordu — arayüz zaten yalnızca
        son-4-hane + kart ağı gösteriyordu, saklamanın ürünsel bir karşılığı
        yoktu. `expiry_date`/`cvc_code` parametreleri tamamen kaldırıldı;
        hiçbir tüketicileri yoktu.

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
            
        # Ham numara YALNIZCA türetim için tutulur, hiçbir zaman şifrelenip
        # INSERT'e geçmez. Boş bırakılan/tanınmayan bir numara sessizce
        # None'a düşer — arayüz zaten "**** **** **** 0000" göstermeye
        # hazırdı, bu davranış değişmedi.
        masked_number = None
        network_logo = None
        if card_number_full:
            network_logo = AccountService.check_card_network(card_number_full)
            last4 = card_number_full[-4:] if len(card_number_full) >= 4 else card_number_full
            masked_number = f"**** **** **** {last4}"

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (name, type, balance, account_type, credit_limit, statement_date, masked_number, network_logo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, legacy_type, balance, account_type, credit_limit, statement_date, masked_number, network_logo))
            account_id = cursor.lastrowid
            record_balance_event(cursor, ACCOUNT, account_id, balance, balance,
                                 "account_opened")
            conn.commit()
            return account_id
        finally:
            conn.close()

    @staticmethod
    def check_card_network(card_number):
        """Kart numarasının ilk hanelerinden (IIN/BIN) ağı belirler.

        Logo yolları database/db.py::NETWORK_LOGOS'ta tek noktada tutulur;
        burada tekrar yazılmaz ki asset yolu değiştiğinde iki yer ayrışmasın.

        Sıra ÖNEMLİ: Troy kartları 9792 ile başlar, Mastercard 5 ile — önek
        kontrolü en uzun/en özel olandan başlamalı, yoksa 9792... numarası
        hiçbir kurala takılmadan boş dönerdi.
        """
        from database.db import NETWORK_LOGOS

        if not card_number:
            return ""
        num = "".join(ch for ch in str(card_number) if ch.isdigit())
        if not num:
            return ""
        if num.startswith("9792"):
            return NETWORK_LOGOS.get("Troy", "")
        if num.startswith("4"):
            return NETWORK_LOGOS.get("Visa", "")
        if num[0] in ("5", "2"):   # Mastercard 51-55 ve 2221-2720 aralıkları
            return NETWORK_LOGOS.get("Mastercard", "")
        return ""

    @staticmethod
    def _to_dict(row):
        account_type = row["account_type"]
        if not account_type:
            account_type = CREDIT_CARD if row["type"] == "credit" else CHECKING

        balance = float(row["balance"] or 0)
        credit_limit = float(row["credit_limit"] or 0)

        # masked_number/network_logo hesap oluşturulduğu ANDA türetilip
        # saklanır (bkz. create_account) — burada artık şifre çözme YOK,
        # ham kart numarası zaten diskte hiç yok.
        has_masked_number = bool(
            "masked_number" in row.keys() and row["masked_number"]
        )
        masked_number = row["masked_number"] if has_masked_number else "**** **** **** 0000"
        network_logo = (row["network_logo"] or "") if "network_logo" in row.keys() else ""

        if account_type == CREDIT_CARD:
            if balance > 0:
                debt = 0.0
                available_limit = credit_limit + balance
            else:
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
            "network_logo": network_logo,
            # Arayüz hangi kart widget'ını çizeceğine buna bakarak karar verir.
            # Maskelenmiş metni ("**** **** **** 0000") karşılaştırmak kırılgandı:
            # numarası gerçekten 0000 ile biten bir kart kartsız sanılırdı.
            "has_card_number": has_masked_number,
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
    def account_exists(account_id):
        """Hesap var mı? (Tüm satırı çözmeye gerek olmayan hızlı kontrol.)

        İşlem yazan akışlar bunu ön koşul olarak kullanır: varsayılan hesap
        seed'i kaldırıldığından DEFAULT_ACCOUNT_ID taze kurulumda hiçbir satıra
        denk gelmiyor ve kontrol edilmezse sahipsiz kayıt oluşuyordu.
        """
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    @staticmethod
    def has_any_account():
        """Kullanıcı hiç hesap oluşturmuş mu? Onboarding kapısının koşulu."""
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone()
        finally:
            conn.close()
        return row is not None

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
            try:
                amount_f = float(amount)
            except (TypeError, ValueError):
                return False, "Geçersiz tutar."
            if amount_f > float(acc["balance"]):
                return False, "Yetersiz Bakiye! Bu hesap eksiye düşemez."
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

    @staticmethod
    def pay_credit_card_debt(credit_card_id, source_account_id, amount):
        """Kredi kartı borcunu vadesiz hesaptan öder."""
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Ödenecek tutar sıfırdan büyük olmalıdır.")

        card = AccountService.get_account(credit_card_id)
        if not card or card["account_type"] != CREDIT_CARD:
            raise ValueError("Geçersiz kredi kartı.")

        debt = float(card["debt"])
        if debt <= 0:
            raise ValueError("Bu kredi kartında ödenecek borç bulunmuyor.")
        if amount > debt:
            raise ValueError(
                f"Ödeme mevcut borcu aşamaz. Güncel borç: {_fmt_try(debt)}."
            )

        source = AccountService.get_account(source_account_id)
        if not source or source["account_type"] != CHECKING:
            raise ValueError("Ödeme yapılacak hesap vadesiz hesap olmalıdır.")
            
        if float(source["balance"]) < amount:
            raise ValueError("Yetersiz Bakiye! Bu hesap eksiye düşemez.")

        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Bakiyeler doğrulamadan sonra değişmiş olabilir. UPDATE koşulları
            # işlemi atomik tutar ve kartı pozitif bakiyeye geçiren fazla ödemeyi
            # engeller.
            cursor.execute(
                "UPDATE accounts SET balance = balance - ?"
                " WHERE id = ? AND account_type = ? AND balance >= ?",
                (amount, source_account_id, CHECKING, amount),
            )
            if cursor.rowcount != 1:
                raise ValueError("Yetersiz Bakiye! Bu hesap eksiye düşemez.")

            cursor.execute(
                "UPDATE accounts SET balance = balance + ?"
                " WHERE id = ? AND account_type = ? AND balance <= ?",
                (amount, credit_card_id, CREDIT_CARD, -amount),
            )
            if cursor.rowcount != 1:
                raise ValueError("Ödeme mevcut kart borcunu aşamaz.")
            
            # balance_events için history tetikle
            from database.db import record_balance_event, ACCOUNT
            cursor.execute("SELECT balance FROM accounts WHERE id = ?", (source_account_id,))
            new_source_balance = cursor.fetchone()["balance"]
            record_balance_event(cursor, ACCOUNT, source_account_id, -amount, new_source_balance, "card_payment")
            
            cursor.execute("SELECT balance FROM accounts WHERE id = ?", (credit_card_id,))
            new_card_balance = cursor.fetchone()["balance"]
            record_balance_event(cursor, ACCOUNT, credit_card_id, amount, new_card_balance, "card_payment")

            # İşlemi transactions tablosuna yaz
            from services.transaction_service import SECRET_KEY
            from utils.crypto import encrypt
            import datetime
            date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            enc_amount = encrypt(str(amount), SECRET_KEY)
            desc = f"{card['name']} Borç Ödemesi"
            enc_desc = encrypt(desc, SECRET_KEY)
            
            cursor.execute("""
                INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source_account_id, enc_amount, "expense", "Borç Ödeme", enc_desc, date_now))

            # Kartın kendi ekstresinde ödeme görünsün. "payment" tipi genel
            # gelir metriklerine katılmaz; yalnızca kart hareketinde yeşil artı
            # olarak sunulur.
            cursor.execute("""
                INSERT INTO transactions (account_id, amount, type, category, description, transaction_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (credit_card_id, enc_amount, "payment", "Borç Ödeme", enc_desc, date_now))

            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete_credit_card(credit_card_id):
        """Kartı ve karta ait bütün bağımlı kayıtları tek transaction'da siler."""
        credit_card_id = int(credit_card_id)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            card = cursor.execute(
                "SELECT id FROM accounts WHERE id = ? AND account_type = ?",
                (credit_card_id, CREDIT_CARD),
            ).fetchone()
            if card is None:
                raise ValueError("Kredi kartı bulunamadı.")

            # Eski/minimal veritabanı şemalarında tablo bulunmayabilir. Güncel
            # şemada mevcutsa silme aynı transaction'ın zorunlu parçasıdır.
            has_installment_table = cursor.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type = 'table' AND name = 'installment_plans'"""
            ).fetchone()
            if has_installment_table:
                cursor.execute(
                    "DELETE FROM installment_plans WHERE account_id = ?",
                    (credit_card_id,),
                )
            cursor.execute(
                "DELETE FROM recurring_payments WHERE account_id = ?",
                (credit_card_id,),
            )
            cursor.execute(
                "DELETE FROM transactions WHERE account_id = ?",
                (credit_card_id,),
            )
            cursor.execute(
                "DELETE FROM balance_events WHERE entity_type = ? AND entity_id = ?",
                (ACCOUNT, credit_card_id),
            )
            cursor.execute(
                "DELETE FROM accounts WHERE id = ? AND account_type = ?",
                (credit_card_id, CREDIT_CARD),
            )
            if cursor.rowcount != 1:
                raise ValueError("Kredi kartı bulunamadı.")
            conn.commit()
            # UI dışından yapılan servis çağrıları da mümkündür. Silme yolu
            # balance_events'i bilinçli olarak kaldırdığı için normal
            # record_balance_event choke point'inden geçmez; cache'i burada
            # açıkça bayatlatmak zorundayız.
            from services.asset_service import mark_account_cache_stale
            mark_account_cache_stale()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_active_installment_plan_count(credit_card_id):
        """Kartın tamamlanmamış taksit planı sayısını döndürür."""
        conn = get_connection()
        try:
            table_exists = conn.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type = 'table' AND name = 'installment_plans'"""
            ).fetchone()
            if not table_exists:
                return 0
            row = conn.execute(
                """SELECT COUNT(*) AS plan_count
                   FROM installment_plans
                   WHERE account_id = ?
                     AND paid_installments < total_installments""",
                (int(credit_card_id),),
            ).fetchone()
            return int(row["plan_count"] if row else 0)
        finally:
            conn.close()
