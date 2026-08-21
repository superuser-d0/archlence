"""Para hakkındaki KARARLAR kuruş hassasiyetinde verilmeli.

`accounts.balance` ve `savings_goals.current_amount` birer SQLite REAL sütunu
ve `sütun + ?` ile birikiyorlar, yani ikili kayan nokta artığı taşıyabiliyorlar.
Ölçüldü: gerçekçi kullanımda bu artık EKRANDA görünmüyor (12 x 500,00 ya da
1000 x 1,00 tam çıkıyor), o yüzden sütunları TEXT'e taşımak — ve migrasyon
riskini almak — ölçümle gerekçelenmiyor.

Görünmeyen artığın zarar verdiği yer SAKLAMA değil, üzerine verilen KARAR:
bir eşik karşılaştırması artığı görünür hale getirir. Bu testler o kararları
sabitliyor.
"""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock


class MoneyDecisionPrecisionTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._patch.start()
        from database.init_db import initialize_database

        initialize_database()

    def tearDown(self):
        self._patch.stop()
        os.unlink(self.db_path)

    def _drift_goal_to(self, goal_id, deposits, amount):
        """Hedefi doğrudan SQL ile biriktirip gerçek float artığını üretir."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            for _ in range(deposits):
                conn.execute(
                    "UPDATE savings_goals SET current_amount = "
                    "current_amount + ? WHERE id = ?",
                    (amount, goal_id),
                )
            conn.commit()
            return conn.execute(
                "SELECT current_amount FROM savings_goals WHERE id = ?",
                (goal_id,),
            ).fetchone()[0]

    def test_user_can_withdraw_the_balance_the_screen_shows_them(self):
        """Ekranda 300,00 TL yazarken 300,00 TL çekilebilmeli.

        Bu, bulunan en keskin vaka: 3000 x 0,10 TL yatıran birinin birikimi
        REAL sütunda 299.9999999999997 durur, ekranda "300,00 TL" görünür,
        ama `current_amount >= ?` sağlanmadığı için çekim "Hedefte bu kadar
        birikim yok" ile REDDEDİLİRDİ. Uygulama kendi gösterdiği parayı
        vermiyordu.
        """
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Tatil", 1000.0)
        stored = self._drift_goal_to(goal_id, 3000, 0.10)


        self.assertNotEqual(
            stored, 300.0, "Test kurulumu artığı üretemedi; vaka geçersiz"
        )
        self.assertEqual(f"{stored:.2f}", "300.00", "Ekranda 300,00 görünmeli")

        account_id = self._make_account(balance=0.0)
        SavingsService.withdraw_from_goal(goal_id, 300.0, account_id)

        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()[0]
        self.assertEqual(round(balance, 2), 300.0)

    def test_goal_completes_when_the_target_is_actually_reached(self):
        """Hedefe kuruş hassasiyetinde ulaşıldığında 'tamamlandı' olmalı.

        Hedef 300,01 seçildi ki son yatırmadan SONRA ham toplam eşiğin hemen
        ALTINDA kalsın: 299.9999999999997 + 0,01 = 300.00999999999... yani
        `current_amount >= target_amount` sağlanmaz, ama kuruşa yuvarlanınca
        300,01 >= 300,01 sağlanır.

        İlk yazdığım hâli 300,00 hedefiyleydi ve ESKİ KODDA DA GEÇİYORDU —
        yatırma eşiği zaten aşıyordu, yani test hiçbir şeyi ayırt etmiyordu.
        """
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Bisiklet", 300.01)
        stored = self._drift_goal_to(goal_id, 3000, 0.10)
        self.assertNotEqual(stored, 300.0, "Test kurulumu artığı üretemedi")

        account_id = self._make_account(balance=10.0)
        SavingsService.deposit_to_goal(goal_id, 0.01, account_id)

        with closing(sqlite3.connect(self.db_path)) as conn:
            current, status = conn.execute(
                "SELECT current_amount, status FROM savings_goals "
                "WHERE id = ?", (goal_id,)
            ).fetchone()


        self.assertLess(
            current, 300.01,
            "Ham toplam eşiği aşıyorsa test eski kodda da geçer; vaka geçersiz",
        )
        self.assertEqual(f"{current:.2f}", "300.01")
        self.assertEqual(status, "tamamlandi")

    def test_spending_a_kurus_under_the_limit_is_allowed(self):
        """Limitin milyonda biri kadar altındaki harcama reddedilmemeli.

        Reddedilseydi hata mesajı AYNI iki tutarı gösterirdi — "kullanılabilir
        limit 1.000,00 ₺, harcama 1.000,00 ₺" — yani kullanıcının çözemeyeceği
        bir ret.
        """
        from services.account_service import AccountService

        card_id = AccountService.create_account(
            "Limit kart", "credit_card", credit_limit=1000.0
        )
        allowed, reason = AccountService.check_spending_allowed(
            card_id, 1000.0 + 1e-9, "expense"
        )
        self.assertTrue(allowed, reason)

    def _make_account(self, balance):
        from services.account_service import AccountService

        return AccountService.create_account(
            f"Hesap {balance}", "checking", initial_balance=balance
        )


if __name__ == "__main__":
    unittest.main()
