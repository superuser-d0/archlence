"""Varlık alımının hangi hesaptan düşüleceği.

KULLANICI RAPORU (Windows): "ne altın fiyatı yükleniyor, ne de
ekleniyor". Gönderilen log'da gerçek sebep çıktı:

    ValueError: Yetersiz Bakiye! Bu hesap eksiye düşemez.

Yani ağ/fiyat sorunu değil. `create_purchase` alımı koşulsuz
`DEFAULT_ACCOUNT_ID` (=1) hesabından düşmeye çalışıyordu. Uygulama artık
açılışta varsayılan hesap SEED ETMEDİĞİ için o satır hiç olmayabiliyor ya da
kullanıcının parası başka hesapta olabiliyordu — her iki durumda da alım
kalıcı olarak reddediliyor, kullanıcı ekranda dolu bakiye görüyordu.
"""
import os
import tempfile
import unittest
from unittest import mock

from tests.fixtures import AccountFixtureMixin


class AssetPurchaseFundingTest(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    # `with sqlite3_connection` bağlantıyı KAPATMAZ — yalnızca bir transaction
    # context manager'ıdır. Linux'ta açık bir dosya silinebildiği için bu fark
    # görünmezdi; Windows'ta dosya kilitli kalıyor ve tearDown'daki
    # `os.unlink` "WinError 32: process cannot access the file" ile patlıyordu.
    # (Windows CI eklendiğinde ampirik olarak yakalandı.) Bu yüzden bağlantı
    # burada açıkça kapatılıyor.
    def _exec(self, sql, params=()):
        from database.db import get_connection
        conn = get_connection()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def _fetchone(self, sql, params=()):
        from database.db import get_connection
        conn = get_connection()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def _buy(self, amount=100.0):
        from services.asset_purchase_service import AssetPurchaseService
        return AssetPurchaseService.create_purchase(
            asset_name="Gram Altın", asset_code="GC=F", asset_type="Altın",
            purchase_price=amount, quantity=1.0,
        )

    def test_purchase_uses_an_account_that_can_actually_afford_it(self):
        """Para 1 numaralı hesapta DEĞİLSE bile alım başarılı olmalı.

        Asıl regresyon: boş bir hesap önce, dolu hesap sonra gelir. Eski kod
        koşulsuz ilk/varsayılan hesabı seçtiği için burada patlıyordu.
        """
        self.create_test_account(name="Boş Hesap", balance=0.0)
        rich = self.create_test_account(name="Dolu Hesap", balance=5000.0)

        self._buy(100.0)

        from services.account_service import AccountService
        self.assertEqual(
            float(AccountService.get_account(rich)["balance"]), 4900.0,
            "Alım, tutarı karşılayabilen hesaptan düşülmeli.",
        )

    def test_missing_default_account_does_not_break_purchases(self):
        """Taze kurulumda id=1 hiç olmayabilir; alım yine de çalışmalı."""
        # AUTOINCREMENT ilk satıra 1 verir; onu silerek "id=1 yok" durumunu
        # kurup gerçek hesabı 2. id ile oluşturuyoruz.
        throwaway = self.create_test_account(name="Silinecek", balance=0.0)
        self._exec("DELETE FROM accounts WHERE id = ?", (throwaway,))
        account_id = self.create_test_account(name="Tek Hesap", balance=900.0)
        self.assertNotEqual(account_id, 1, "Bu test id!=1 durumunu sınıyor.")
        self.assertIsNone(
            self._fetchone("SELECT 1 FROM accounts WHERE id = 1"))

        self._buy(50.0)  # patlamamalı

    def test_no_account_affords_it_picks_richest_and_goes_negative(self):
        """Yetersiz bakiye koruması kaldırıldı: hiçbir hesap yetmese bile
        en yüksek bakiyeli vadesiz hesap seçilir ve eksiye düşürülür."""
        account_id = self.create_test_account(name="Az Para", balance=10.0)

        self._buy(5000.0)

        from services.account_service import AccountService
        self.assertAlmostEqual(
            float(AccountService.get_account(account_id)["balance"]),
            10.0 - 5000.0,
            places=2,
            msg="Tek/en zengin hesap, yetmese bile alım için eksiye düşürülmeli.",
        )

    def test_no_account_affords_it_picks_the_richest_among_several(self):
        """Birden fazla yetersiz hesap varken en yüksek bakiyeli seçilmeli."""
        poor = self.create_test_account(name="Az Para", balance=10.0)
        richer = self.create_test_account(name="Biraz Daha Fazla", balance=200.0)

        self._buy(5000.0)

        from services.account_service import AccountService
        self.assertAlmostEqual(
            float(AccountService.get_account(richer)["balance"]),
            200.0 - 5000.0,
            places=2,
        )
        self.assertAlmostEqual(
            float(AccountService.get_account(poor)["balance"]), 10.0, places=2,
            msg="Seçilmeyen hesaba dokunulmamalı.",
        )

    def test_no_checking_account_gives_actionable_message(self):
        with self.assertRaises(ValueError) as ctx:
            self._buy(100.0)
        self.assertIn("hesap", str(ctx.exception).lower())

    def test_credit_cards_are_never_silently_used_to_fund_a_purchase(self):
        """Karta borç yazmak ayrı bir ürün kararı; sessizce yapılmamalı."""
        self.create_test_account(
            name="Kart", balance=0.0, account_type="credit_card",
            credit_limit=50000,
        )
        with self.assertRaises(ValueError):
            self._buy(100.0)


if __name__ == "__main__":
    unittest.main()
