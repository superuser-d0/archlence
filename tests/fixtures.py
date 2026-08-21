"""Testlerin kendi hesaplarını kurması için paylaşılan fixture yardımcıları.

NEDEN: Testler uzun süre `initialize_database()`'in açtığı üç varsayılan hesaba
(Nakit 2500 / Banka 15000 / Kredi Kartı -3500) bel bağlıyordu. Bu "dummy" seed
veriler üretimden kaldırıldığında (kullanıcı kendi eklemediği 2500 TL'yi
görüyordu) 14 test bir anda çöktü — testler üretim seed'ine bağlıydı.

Buradaki yardımcılar test dünyasının hesaplarını AÇIKÇA kurar. Böylece
`database/init_db.py`'nin varsayılan verisi bir daha değişse bile test paketi
kırılmaz: her test neye ihtiyaç duyduğunu kendisi söyler.

Hesaplar bilerek doğrudan SQL ile yazılır (AccountService.create_account
yerine): fixture'ın amacı servis katmanının doğrulama kurallarını sınamak değil,
bilinen bir başlangıç durumu kurmaktır — örneğin negatif bakiyeli bir kart ya da
limitsiz eski bir migration kaydı, servis katmanının reddedeceği durumlar dahil.
"""

from database.db import ACCOUNT, get_connection, record_balance_event


LEGACY_SEED_ACCOUNTS = [
    ("Nakit", "cash", 2500.0, "checking", 0, None),
    ("Banka", "bank", 15000.0, "checking", 0, None),
    ("Kredi Kartı", "credit", -3500.0, "credit_card", 20000, 15),
]


LEGACY_SEED_TOTAL = 14000.0


class AccountFixtureMixin:
    """`create_test_account` sağlayan test karışımı (unittest.TestCase ile birlikte).

    Kullanan sınıfın `database.db.DB_NAME` patch'lenmiş ve
    `initialize_database()` çağrılmış olması beklenir; bu karışım yalnızca satır
    ekler, şema kurmaz.
    """

    def create_test_account(self, name="Test Hesabı", balance=0.0,
                            account_type="checking", account_kind=None,
                            credit_limit=0, statement_date=None):
        """Bilinen bakiyeli bir hesap oluşturur ve id'sini döndürür.

        `account_type` mantıksal tür ('checking' | 'credit_card'),
        `account_kind` ise eski `type` kolonu ('cash'/'bank'/'credit');
        verilmezse hesap türünden makul bir değer türetilir.
        """
        if account_kind is None:
            account_kind = "credit" if account_type == "credit_card" else "cash"

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO accounts(name, type, balance, account_type,"
                " credit_limit, statement_date) VALUES(?,?,?,?,?,?)",
                (name, account_kind, float(balance), account_type,
                 credit_limit, statement_date),
            )
            account_id = cursor.lastrowid


            record_balance_event(
                cursor, ACCOUNT, account_id, float(balance), float(balance),
                "account_opened",
            )
            conn.commit()
        finally:
            conn.close()
        return account_id

    def create_legacy_seed_accounts(self):
        """Eskiden `initialize_database()`'in açtığı üç hesabı kurar.

        Net toplamı `LEGACY_SEED_TOTAL` (14000.0) olan bu üçlüye dayanan
        testler için; id'leri ekleme sırasına göre döndürür.
        """
        return [
            self.create_test_account(
                name=name, account_kind=kind, balance=balance,
                account_type=acc_type, credit_limit=limit,
                statement_date=statement_day,
            )
            for name, kind, balance, acc_type, limit, statement_day
            in LEGACY_SEED_ACCOUNTS
        ]
