"""`REAL` sütununda biriken sapmanın İŞ KARARINI bozmadığını sabitler.

NEDEN VAR: `adjust_account_balance` bakiyeyi `UPDATE accounts SET balance =
balance + ?` ile günceller — toplama Python'da değil SQLite'ın `REAL`
sütununda yapılıyor, dolayısıyla Python tarafı tamamen `Decimal`'a geçse bile
birikim ikili kayan noktada kalır. 100.000 kez 0,01 eklendiğinde ham değer
999.9999999992356 oluyor (ölçüm: `scripts/audit/measure_real_column_drift.py`).

BURADAKİ TESTLER "ham bakiye Decimal'a eşit olmalı" DEMİYOR. Mevcut şema
altında bu yanlış bir beklenti olurdu ve kapıyı kalıcı kırmızıya çevirirdi.
Uygulamanın gerçekten garanti ettiği şey şu: **kullanıcıya gösterilen tutar
doğrudur ve verilen karar gösterilen tutarla tutarlıdır.** Sapmayı iş
kararından uzak tutan mekanizma da belli: karşılaştırmalar yuvarlanmış değer
üzerinde yapılıyor (`fiat()`, ya da SQL tarafında `ROUND(...)`).

Bu testler o mekanizmanın kaldırılmasına karşı koruma. Biri `fiat()`'i
karşılaştırmadan çıkarırsa ya da `ROUND(...)`'ı silerse burası kırmızıya döner
— çünkü o an kullanıcı ekranda 100,00 TL görüp 100,00 TL harcayamaz hâle
gelir. Bu, gösterim kusurundan çok daha ciddi bir sınıftır.
"""

import os
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest import mock

_MUTATIONS = 10_000          # 10.000 x 0,01 = 100,00 TL; ölçülen sapma ~1.4e-11


class RealColumnDriftInvariants(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="archlence-realinv-")
        root = Path(self.tempdir.name)
        self.db_patch = mock.patch("database.db.DB_NAME", str(root / "finance.db"))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=os.urandom(32)
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database
        initialize_database()

    def _drift(self, sql, ident, times=_MUTATIONS, step=0.01):
        """Uygulamanın kendi SQL kalıbıyla sapma üretir."""
        from database.db import get_connection
        with closing(get_connection()) as conn, conn:
            for _ in range(times):
                conn.execute(sql, (step, ident))

    def _raw(self, table, column, ident):
        from database.db import get_connection
        with closing(get_connection()) as conn, conn:
            return conn.execute(
                f"SELECT {column} FROM {table} WHERE id=?", (ident,)
            ).fetchone()[0]

    def test_displayed_balance_is_the_exact_amount(self):
        """Ham değer sapsa da kullanıcıya gösterilen tutar doğru olmalı."""
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            "Drift", "checking", initial_balance=0.0)
        self._drift(
            "UPDATE accounts SET balance = balance + ? WHERE id=?", account_id)

        raw = self._raw("accounts", "balance", account_id)
        self.assertNotEqual(
            Decimal(repr(raw)), Decimal("100.00"),
            "Sapma üretilemedi; bu test artık ölçmek istediği şeyi ölçmüyor.",
        )
        self.assertEqual(AccountService.get_account(account_id)["balance"], 100.00)

    def test_spending_the_whole_displayed_balance_is_allowed(self):
        """Ekranda 100,00 TL yazıyorsa 100,00 TL harcanabilmeli."""
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            "Drift", "checking", initial_balance=0.0)
        self._drift(
            "UPDATE accounts SET balance = balance + ? WHERE id=?", account_id)

        allowed, reason = AccountService.check_spending_allowed(
            account_id, 100.00, "expense")
        self.assertTrue(allowed, f"gösterilen tutarın tamamı reddedildi: {reason}")

    def test_credit_card_limit_decision_matches_what_is_shown(self):
        """Kalan limitin tamamı harcanabilmeli, bir kuruş fazlası reddedilmeli."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Drift card", "credit_card", credit_limit=100.0)
        # 5.000 x 0,01 = 50,00 TL borç (kartta gider bakiyeyi negatife iter)
        self._drift(
            "UPDATE accounts SET balance = balance - ? WHERE id=?",
            card_id, times=5_000)

        card = AccountService.get_account(card_id)
        self.assertEqual(card["debt"], 50.00)
        self.assertEqual(card["available_limit"], 50.00)

        allowed, reason = AccountService.check_spending_allowed(
            card_id, 50.00, "expense")
        self.assertTrue(allowed, f"kalan limitin tamamı reddedildi: {reason}")

        refused, _ = AccountService.check_spending_allowed(
            card_id, 50.01, "expense")
        self.assertFalse(refused, "limitin bir kuruş üstü kabul edildi")

        # Karar yalnız ön-kontrolde değil, gerçek yazma yolunda da tutmalı.
        TransactionService.add_transaction(
            card_id, 50.00, "expense", "Audit", "sınır",
            detect_subscription=False)
        self.assertEqual(AccountService.get_account(card_id)["debt"], 100.00)

    def test_spending_the_whole_displayed_available_limit_is_allowed(self):
        """Sapmanın YUKARI yönde olduğu vaka — asıl tehlikeli olan bu.

        Önceki testte borç, tam değerin bir tık ALTINDA kalıyor; o yönde
        `fiat()` kaldırılsa bile kararlar tesadüfen doğru çıkıyor (ölçüldü:
        koruma kaldırıldığında o test yeşil kalıyordu). Tehlike ters yönde:
        ham borç tam değerin bir tık ÜSTÜNDE kalırsa, kullanıcı ekranda
        "kullanılabilir limit 100,00" görüp 100,00 harcayamaz.

        10.000 x 0,01 birikimi tam da bu yönde sapıyor (100.00000000001425).

        KORUMA İKİ KATMANLI ve mutation ile ölçüldü: borç çıkarılırken
        (`assert_spending_allowed`, `debt = fiat(...)`) ve karşılaştırma
        yapılırken (`fiat(debt + amount) > limit`). Katmanlardan YALNIZCA
        BİRİNİ kaldırmak bu testi kırmıyor — diğeri sapmayı yutuyor. İkisi
        birden kaldırıldığında ise tam olarak korkulan arıza çıkıyor:

            "Limit yetersiz: kullanılabilir limit ₺100,00, harcama ₺100,00."

        Yani kullanıcı aynı iki tutarı görüp reddediliyor. Testin ölçtüğü şey
        budur; tek noktalı bir mutation'ın kırmaması kapının zayıflığı değil,
        korumanın yedekli olması demek.
        """
        from services.account_service import AccountService

        card_id = AccountService.create_account(
            "Drift card", "credit_card", credit_limit=200.0)
        self._drift(
            "UPDATE accounts SET balance = balance - ? WHERE id=?",
            card_id, times=10_000)

        card = AccountService.get_account(card_id)
        self.assertEqual(card["debt"], 100.00)
        self.assertEqual(card["available_limit"], 100.00)

        allowed, reason = AccountService.check_spending_allowed(
            card_id, 100.00, "expense")
        self.assertTrue(
            allowed,
            f"ekranda gösterilen kullanılabilir limitin tamamı reddedildi: {reason}",
        )

    def test_withdrawing_the_whole_displayed_savings_is_allowed(self):
        """Hedefte 300,00 TL görünüyorsa 300,00 TL çekilebilmeli.

        Bu, bir kez gerçekten yaşanmış hata: `savings_service` içindeki
        `ROUND(current_amount, 2) >= ROUND(?, 2)` koruması tam da bunun için
        var ve yorumu olayı anlatıyor. Test o korumanın kaldırılmasını
        engelliyor.
        """
        from services.account_service import AccountService
        from services.savings_service import SavingsService

        account_id = AccountService.create_account(
            "A", "checking", initial_balance=1000.0)
        goal_id = SavingsService.create_goal("Drift goal", 1000.0)
        self._drift(
            "UPDATE savings_goals SET current_amount = current_amount + ? "
            "WHERE id=?", goal_id, times=30_000)

        raw = self._raw("savings_goals", "current_amount", goal_id)
        self.assertNotEqual(
            Decimal(repr(raw)), Decimal("300.00"),
            "Sapma üretilemedi; bu test artık ölçmek istediği şeyi ölçmüyor.",
        )
        SavingsService.withdraw_from_goal(goal_id, 300.00, account_id)


if __name__ == "__main__":
    unittest.main()
