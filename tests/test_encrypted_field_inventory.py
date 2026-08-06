"""`ENCRYPTED_FIELDS` gerçek şemaya bağlı mı — kendine değil.

NEDEN BU TEST VAR: `ENCRYPTED_FIELDS` üç yerin tek kaynağı — yedekleme
(`backup_service`), eski formattan taşıma (`crypto_migration_service`) ve
anahtar doğrulama (`key_recovery_service`). Bir sütun bu haritada değilse
yedeğe girmez, taşınmaz ve anahtar doğrulamasında görünmez.

Mevcut kapı (`test_crypto_migration_coverage`) haritayı KENDİ KURDUĞU şemaya
karşı doğruluyor:

    self.assertEqual(set(inserts), set(ENCRYPTED_FIELDS))

Bu, haritaya ekleme yapıldığında uyarır — o yön korunuyor. Ama harita ile test
yalnızca BİRBİRİNİ tutuyor; ikisi de gerçek şemaya bağlı değil. Yani gerçek
şemaya şifreli bir sütun eklenip haritaya eklenmezse hiçbir şey yakalamaz ve o
sütun sessizce yedeğin dışında kalır.

Bu test farkı kapatıyor: uygulamanın KENDİ yazma yollarını çalıştırıp diskte
oluşan her tabloyu her sütunuyla tarar ve şifreli veri taşıyan her sütunun
haritada bulunduğunu doğrular. Şifreli değerler `AEADv1:` ile başladığı için
tespit tahmine değil, verinin kendisine dayanır.
"""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

AEAD_PREFIX = "AEADv1:"


class EncryptedFieldInventoryTest(unittest.TestCase):
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

    def _exercise_every_encrypting_write_path(self):
        """Şifreli veri üreten üretim yollarını gerçekten çalıştırır."""
        from database.db import insert_debt
        from services.account_service import AccountService
        from services.asset_purchase_service import AssetPurchaseService
        from services.recurring_service import (
            register_subscription_from_transaction,
        )
        from services.savings_service import SavingsService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=50_000.0
        )
        card_id = AccountService.create_account(
            "Kart", "credit_card", credit_limit=50_000.0
        )

        # transactions (amount, description)
        TransactionService.add_transaction(
            account_id, 250.0, "expense", "Market", "Haftalık alışveriş",
            transaction_date="2026-08-01 10:00:00",
        )
        # installment_plans (description, total_amount, monthly_amount)
        TransactionService.add_transaction(
            card_id, 1200.0, "expense", "Elektronik", "Telefon",
            transaction_date="2026-08-01 11:00:00", installments=6,
        )
        # active_assets (purchase_price, quantity)
        AssetPurchaseService.create_purchase(
            asset_name="Gram Altın", asset_code="GC=F", asset_type="Altın",
            purchase_price=2890.45, quantity=2.0, account_id=account_id,
        )
        # active_debts (debt_name, total_amount, monthly_payment)
        insert_debt("Araç Kredisi", 60_000.0, 5_000.0, 12)
        # recurring_payments (name, amount).
        # `is_credit_card=True` ZORUNLU: interceptor kart dışı harcamaları
        # bilerek atlar (kart dışı tekrarlayanları formun kendi akışı yazar,
        # ikisi birden çalışsa çift kayıt olurdu). Bayrak atlanınca fonksiyon
        # sessizce None döner ve bu tablo hiç kapsanmaz.
        register_subscription_from_transaction(
            card_id, 149.90, "Dijital Platformlar", "Streaming",
            transaction_date="2026-08-01 12:00:00", is_credit_card=True,
        )
        # savings_goals (goal_name)
        SavingsService.create_goal("Tatil", 10_000.0)

    def _columns_holding_encrypted_data(self):
        """Diskte gerçekten AEAD verisi taşıyan (tablo, sütun) çiftleri."""
        found = set()
        with closing(sqlite3.connect(self.db_path)) as conn:
            tables = [
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ]
            for table in tables:
                columns = [
                    row[1] for row in conn.execute(f"PRAGMA table_info({table})")
                ]
                for row in conn.execute(f"SELECT * FROM {table}"):
                    for column, value in zip(columns, row):
                        if isinstance(value, str) and value.startswith(AEAD_PREFIX):
                            found.add((table, column))
        return found

    def test_setup_covers_every_declared_table(self):
        """Kurulum, haritadaki HER tabloya gerçekten şifreli veri yazmalı.

        Bu koruma bir sayı eşiğiyle ("en az 10 sütun") başlamıştı ve İŞE
        YARAMADI: 11 sütun bulunup geçerken `recurring_payments` hiç
        yazılmamıştı, çünkü interceptor `is_credit_card` bayrağı olmadan
        sessizce None dönüyordu. Eşik, kapsamı ölçmüyordu.

        Artık kapsam haritanın kendisine bağlı: bir yazma yolu sessizce
        çalışmaz olursa asıl test o tabloyu boş tarayıp geçeceği için burada
        yakalanır.
        """
        from services.backup_service import ENCRYPTED_FIELDS

        self._exercise_every_encrypting_write_path()
        covered = {table for table, _ in self._columns_holding_encrypted_data()}
        missing = set(ENCRYPTED_FIELDS) - covered
        self.assertEqual(
            missing, set(),
            "Bu tablolara hiç şifreli veri yazılmadı; asıl test onları boş "
            f"tarayıp geçerdi: {sorted(missing)}",
        )

    def test_every_encrypted_column_on_disk_is_declared(self):
        """Diskte şifreli veri taşıyan her sütun ENCRYPTED_FIELDS'te olmalı.

        Değilse: o sütun yedeğe girmez, eski formattan taşınmaz ve anahtar
        doğrulamasında görünmez — üçü de sessizce.
        """
        from services.backup_service import ENCRYPTED_FIELDS

        self._exercise_every_encrypting_write_path()

        declared = {
            (table, field)
            for table, fields in ENCRYPTED_FIELDS.items()
            for field in fields
        }
        undeclared = self._columns_holding_encrypted_data() - declared

        self.assertEqual(
            undeclared, set(),
            "Bu sütunlar diskte şifreli veri tutuyor ama ENCRYPTED_FIELDS'te "
            "yok — yedeklemeden, migration'dan ve anahtar doğrulamasından "
            f"sessizce düşerler: {sorted(undeclared)}",
        )

    def test_declared_columns_exist_in_the_real_schema(self):
        """Haritadaki her sütun gerçekten şemada olmalı.

        Ters yön: yeniden adlandırılan ya da kaldırılan bir sütun haritada
        kalırsa, yedekleme onu sessizce atlar (`if field in columns`) ve
        harita gerçeği yansıtmayı bırakır.
        """
        from services.backup_service import ENCRYPTED_FIELDS

        # installment_plans tembel oluşturuluyor; önce yazma yollarını çalıştır.
        self._exercise_every_encrypting_write_path()

        with closing(sqlite3.connect(self.db_path)) as conn:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for table, fields in ENCRYPTED_FIELDS.items():
                self.assertIn(
                    table, tables, f"{table} haritada var ama şemada yok"
                )
                columns = {
                    row[1] for row in conn.execute(f"PRAGMA table_info({table})")
                }
                missing = [f for f in fields if f not in columns]
                self.assertEqual(
                    missing, [],
                    f"{table}: haritadaki sütun(lar) şemada yok: {missing}",
                )


if __name__ == "__main__":
    unittest.main()
