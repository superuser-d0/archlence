"""Varlık SATIŞINDA cüzdana giren tutar kuruşa yuvarlanmış olmalı.

Alım tarafının (`asset_purchase_service.create_purchase`) simetriği.

v0.0.8'de bu testler `AssetMixin._execute_sell` içindeki closure'ı mock'layarak
`database.db.insert_asset_transaction` çağrısını yakalıyordu. v0.0.9'un
atomiklik düzeltmesi (`96049ee`) satışı `services/asset_sale_service` altında
tek bir SQLite transaction'ına taşıdı; eski mock artık hiç tetiklenmiyor ve
testler `KeyError: 'amount'` ile HATA veriyordu — yani kuruş yuvarlama koruması
sessizce devre dışı kalmıştı.

Testler artık gerçek sınırı, `AssetSaleService.sell`'i çağırıyor ve deftere
YAZILAN değeri okuyor. Mock yok: hem servis dönüşü hem şifreli satır
doğrulanıyor, böylece araya giren bir katman korumayı bir daha sessizce
düşüremez.
"""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from unittest import mock


class AssetSaleCashAmountTest(unittest.TestCase):
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

    def _sell(self, purchase_price, quantity, sell_price):
        """Gerçek alım + gerçek satış; deftere yazılan tutarı döner."""
        from database.db import SECRET_KEY
        from services.account_service import AccountService
        from services.asset_purchase_service import AssetPurchaseService
        from services.asset_sale_service import AssetSaleService
        from utils.crypto import decrypt

        account_id = AccountService.create_account(
            f"Cüzdan {sell_price}-{quantity}", "checking",
            initial_balance=10_000_000.0,
        )
        AssetPurchaseService.create_purchase(
            asset_name="Test", asset_code="TST", asset_type="Kripto",
            purchase_price=purchase_price, quantity=quantity,
            account_id=account_id,
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            asset_id = conn.execute(
                "SELECT id FROM active_assets"
            ).fetchone()[0]
            # Bakiye SATIŞTAN HEMEN ÖNCE ölçülüyor: alım da bakiyeden
            # düştüğü için açılış bakiyesinden ölçmek net K/Z verirdi.
            before_sale = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]

        returned = AssetSaleService.sell(
            asset_id, sell_price, account_id, quantity=quantity
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            amount, description = conn.execute(
                "SELECT amount, description FROM transactions "
                "WHERE category='Varlık Satışı'"
            ).fetchone()
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
        return {
            "before_sale": Decimal(str(before_sale)),
            "returned": returned,
            "stored": Decimal(decrypt(str(amount), SECRET_KEY)),
            "description": decrypt(str(description), SECRET_KEY),
            "balance": balance,
        }

    def test_proceeds_are_quantised_to_kurus(self):
        # 2.456,78 x 0,12345678 = 303.3061479684 ham float olarak — on
        # ondalıklı bir LİRA tutarı deftere yazılıyordu.
        result = self._sell(2000.0, 0.12345678, 2456.78)
        self.assertEqual(result["stored"], Decimal("303.31"))
        self.assertEqual(Decimal(str(result["returned"])), Decimal("303.31"))

    def test_binary_artefact_never_reaches_the_ledger(self):
        # 142,30 x 17 float'ta 2419.1000000000004 üretir.
        result = self._sell(100.0, 17.0, 142.30)
        self.assertEqual(result["stored"], Decimal("2419.10"))

    def test_credited_balance_matches_the_stored_amount(self):
        """Bakiyeye eklenen tutar deftere yazılanla birebir aynı olmalı.

        v0.0.8'de bu, açıklamadaki K/Z üzerinden dolaylı doğrulanıyordu.
        Açıklama artık satış ayrıntısı taşımadığı için (bkz. modül notu ve
        denetim bulgusu) doğrulama nakit hareketinin kendisine bağlandı —
        zaten korunması gereken değişmez budur.
        """
        result = self._sell(2000.0, 0.12345678, 2456.78)
        self.assertEqual(
            Decimal(str(result["balance"])) - result["before_sale"],
            result["stored"],
            "bakiyeye eklenen tutar deftere yazılandan farklı",
        )

    def test_a_sale_writes_exactly_one_ledger_row(self):
        """Atomiklik düzeltmesi çift kayıt üretmemeli."""
        self._sell(2000.0, 0.12345678, 2456.78)
        with closing(sqlite3.connect(self.db_path)) as conn:
            sales = conn.execute(
                "SELECT COUNT(*) FROM transactions "
                "WHERE category='Varlık Satışı'"
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM balance_events WHERE source='asset_sale'"
            ).fetchone()[0]
        self.assertEqual(sales, 1)
        self.assertEqual(events, 1)


if __name__ == "__main__":
    unittest.main()
