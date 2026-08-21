"""Bir kullanıcının finansal yaşam döngüsü, uçtan uca, gerçek servislerle.

NEDEN VAR: 856 testin hepsi ya tek bir servisi ya da iki servis arasındaki tek
bir sınırı doğruluyordu. Hiçbiri "hesap aç, gelir gir, varlık al, sat, kartla
harca, borcu öde, aboneliği işlet, birikim yap" zincirinin BİRLİKTE çalıştığını
sınamıyordu. Parçaların her biri yeşilken zincirin kopuk olması mümkündü.

GERÇEKTEN KOŞAN ÜRETİM KODU: SQLite'ın kendisi, şema kurulumu, defter
(`balance_events`), `AccountService`, `TransactionService`,
`AssetPurchaseService`, `AssetSaleService`, `SavingsService`,
`process_due_recurring_payment`, `create_backup`/`restore_backup` ve şifreleme
yolu. Hiçbiri mock'lanmıyor.

SAHTE OLAN TEK SINIR: şifreleme anahtarı, `_TemporaryProfile`'ın enjekte ettiği
test anahtarı (OS keystore'a — DPAPI/Secret Service/KWallet — çıkılmıyor).
Fiyat sağlayıcısına hiç dokunulmuyor: alım ve satım fiyatı zaten parametre
olarak veriliyor, yani ağ da fiyat servisi de bu akışa hiç girmiyor.

BU TESTİN DOĞRULAMADIĞI ŞEY: gerçek fiyat çekme yolu ve gerçek OS keystore.
İkisi de kendi testlerinde ayrıca kapsanıyor.

Testler BİRBİRİNDEN BAĞIMSIZ: ortak durumu `_build_golden_financial_state`
kuruyor ve her test kendi geçici profilinde onu sıfırdan çağırıyor. Sıra
değişse, tek test koşulsa ya da paralel koşulsalar sonuç aynı.
"""

import sqlite3
import unittest
from contextlib import closing
from datetime import date
from decimal import Decimal

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile


def _money(value):
    """Snapshot'taki parasal alanları kuruşa normalize eder.

    Ham float gösterimi sözleşme yapılmıyor: `0.1 + 0.2` ile `0.3` aynı parayı
    ifade ediyor ve snapshot'ın bunları farklı görmesi testi kırılgan yapardı.
    """
    from utils.financial_decimal import fiat

    return str(fiat(value))


def _financial_snapshot(db_path):
    """Profilin finansal gerçeklerini kanonik ve karşılaştırılabilir hâlde verir.

    Kimlik SEMANTİK: hesap adı/türü, varlık kodu, kategori — otomatik artan
    id'ler ve zaman damgaları bilerek DIŞARIDA. Amaç, geri yüklemenin aynı
    finansal durumu döndürdüğünü göstermek; satır sırası ya da id sayacının
    aynı yerden devam ettiğini değil.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        accounts = [
            {
                "name": row["name"],
                "type": row["account_type"],
                "balance": _money(row["balance"] or 0),
                "credit_limit": _money(row["credit_limit"] or 0),
            }
            for row in conn.execute(
                "SELECT name, account_type, balance, credit_limit FROM accounts"
                " ORDER BY name"
            )
        ]

        assets = [
            {
                "code": row["asset_code"],
                "type": row["asset_type"],
                "quantity": _decrypted(row["quantity"]),
            }
            for row in conn.execute(
                "SELECT asset_code, asset_type, quantity FROM active_assets"
                " ORDER BY asset_code"
            )
        ]


        transactions = [
            {
                "type": row["type"],
                "category": row["category"],
                "amount": _decrypted_money(row["amount"]),
                "account": row["account_name"],
            }
            for row in conn.execute(
                "SELECT t.type, t.category, t.amount, a.name AS account_name"
                "  FROM transactions t LEFT JOIN accounts a ON a.id = t.account_id"
            )
        ]
        transactions.sort(key=lambda item: (
            item["account"] or "", item["category"] or "",
            item["type"] or "", item["amount"]))

        recurring = [
            {
                "category": row["category"],
                "amount": _decrypted_money(row["amount"]),
                "frequency": row["frequency"],
                "active": bool(row["is_active"]),
            }
            for row in conn.execute(
                "SELECT category, amount, frequency, is_active"
                "  FROM recurring_payments ORDER BY category"
            )
        ]

        savings = [
            {
                "name": row["goal_name"],
                "current": _money(row["current_amount"] or 0),
                "target": _money(row["target_amount"] or 0),
                "status": row["status"],
            }
            for row in conn.execute(
                "SELECT goal_name, current_amount, target_amount, status"
                "  FROM savings_goals ORDER BY goal_name"
            )
        ]

    return {
        "accounts": accounts,
        "assets": assets,
        "transactions": transactions,
        "transaction_count": len(transactions),
        "recurring": recurring,
        "savings": savings,
    }


def _decrypted(value):
    from database.db import SECRET_KEY
    from utils.crypto import decrypt

    return str(Decimal(decrypt(str(value), SECRET_KEY)))


def _decrypted_money(value):
    from database.db import SECRET_KEY
    from utils.crypto import decrypt

    return _money(decrypt(str(value), SECRET_KEY))


def _build_golden_financial_state(case):
    """Kanonik golden durumu kurar ve beklenen değerleri döndürür.

    `case` bir `_TemporaryProfile` örneği; her test bunu KENDİ temiz profilinde
    çağırır. Testler arasında paylaşılan hiçbir durum yok.

    Muhasebe burada tek yerde ve `Decimal` ile: beklenen değerleri ikili kayan
    noktada hesaplamak, testin kendisini sınadığımız hatanın içine sokardı.
    """
    from services.account_service import AccountService
    from services.asset_purchase_service import AssetPurchaseService
    from services.asset_sale_service import AssetSaleService
    from services.savings_service import SavingsService
    from services.transaction_service import TransactionService

    expected = {}

    # 1-2 · nakit hesap
    cash_id = AccountService.create_account(
        "Altın Kumbara", "checking", initial_balance=0.0)

    # 3 · gelir
    TransactionService.add_transaction(
        cash_id, 5000.00, "income", "Maaş", "Golden path geliri",
        detect_subscription=False)
    cash = Decimal("5000.00")


    AssetPurchaseService.create_purchase(
        asset_name="Külçe", asset_code="XAU-GOLD", asset_type="Altın",
        purchase_price=250.50, quantity=3, account_id=cash_id,
        deduct_from_balance=True)
    cash -= Decimal("751.50")


    asset_id = _asset_id_by_code(case.db_path, "XAU-GOLD")
    AssetSaleService.sell(asset_id, 300.25, cash_id, quantity=1)
    cash += Decimal("300.25")
    expected["asset_quantity"] = Decimal("2")


    card_id = AccountService.create_account(
        "Seyahat Kartı", "credit_card", credit_limit=10000.0)
    TransactionService.add_transaction(
        card_id, 1200.00, "expense", "Ulaşım", "Uçak bileti",
        detect_subscription=False)
    debt = Decimal("1200.00")


    AccountService.pay_credit_card_debt(card_id, cash_id, 400.00)
    debt -= Decimal("400.00")
    cash -= Decimal("400.00")


    from database.db import get_active_recurring_payments, insert_recurring_payment

    insert_recurring_payment(
        "Müzik aboneliği", 79.90, "Abonelik", "monthly",
        date.today().isoformat(), False, account_id=cash_id,
        recurrence_day=date.today().day)
    payment = next(
        item for item in get_active_recurring_payments()
        if item["category"] == "Abonelik"
    )

    # 9 · birikim hedefi
    goal_id = SavingsService.create_goal("Tatil", 1000.00)
    SavingsService.deposit_to_goal(goal_id, 250.00, cash_id)
    cash -= Decimal("250.00")

    expected.update({
        "cash_account_id": cash_id,
        "card_account_id": card_id,
        "goal_id": goal_id,
        "recurring_payment": payment,
        "cash_before_recurring": cash,
        "debt": debt,
        "recurring_amount": Decimal("79.90"),
    })
    return expected


def _asset_id_by_code(db_path, code):
    """Varlığı KODUNDAN bulur — otomatik artan id sırasına güvenmeden."""
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT id FROM active_assets WHERE asset_code = ?", (code,)
        ).fetchone()
    assert row is not None, f"{code} portföyde bulunamadı"
    return row[0]


class FinancialLifecycleGoldenPath(_TemporaryProfile):
    """Zincirin tamamı, her adımda beklenen PARA değeriyle birlikte."""

    def _balance_of(self, account_id):
        from services.account_service import AccountService
        return AccountService.get_account(account_id)

    def test_financial_lifecycle_golden_path(self):
        from database.db import process_due_recurring_payment

        expected = _build_golden_financial_state(self)
        cash_id = expected["cash_account_id"]
        card_id = expected["card_account_id"]


        cash_account = self._balance_of(cash_id)
        self.assertEqual(
            _money(cash_account["balance"]),
            _money(expected["cash_before_recurring"]),
            "nakit bakiyesi zincirin beklediği değerde değil",
        )

        # --- Kart borcu
        card_account = self._balance_of(card_id)
        self.assertEqual(_money(card_account["debt"]), _money(expected["debt"]))


        snapshot = _financial_snapshot(self.db_path)
        self.assertEqual(len(snapshot["assets"]), 1)
        self.assertEqual(snapshot["assets"][0]["code"], "XAU-GOLD")
        self.assertEqual(
            Decimal(snapshot["assets"][0]["quantity"]),
            expected["asset_quantity"],
            "kısmi satıştan sonra kalan miktar yanlış",
        )

        # --- Birikim hedefi
        self.assertEqual(len(snapshot["savings"]), 1)
        self.assertEqual(snapshot["savings"][0]["current"], _money(250.00))
        self.assertEqual(snapshot["savings"][0]["target"], _money(1000.00))


        before = _financial_snapshot(self.db_path)
        process_due_recurring_payment(expected["recurring_payment"])
        after_first = _financial_snapshot(self.db_path)

        self.assertEqual(
            after_first["transaction_count"], before["transaction_count"] + 1,
            "vadesi gelen abonelik tek bir işlem yazmalıydı",
        )
        cash_after_charge = expected["cash_before_recurring"] - expected["recurring_amount"]
        self.assertEqual(
            _money(self._balance_of(cash_id)["balance"]),
            _money(cash_after_charge),
        )


        process_due_recurring_payment(expected["recurring_payment"])
        after_second = _financial_snapshot(self.db_path)

        self.assertEqual(
            after_second, after_first,
            "aynı dönem ikinci kez işlendiğinde finansal durum değişti",
        )
        self.assertEqual(
            _money(self._balance_of(cash_id)["balance"]),
            _money(cash_after_charge),
            "ikinci çağrı bakiyeyi tekrar düşürdü",
        )


class GoldenBackupRestoreRoundTrip(_TemporaryProfile):
    """Aynı hikâyenin kalıcılık ucu — kendi golden durumunu kendisi kurar."""

    def test_golden_backup_restore_round_trip(self):
        from services.backup_service import create_backup, restore_backup
        from services.transaction_service import TransactionService

        expected = _build_golden_financial_state(self)
        snapshot_a = _financial_snapshot(self.db_path)

        package = self.root / "golden.arcbak"
        create_backup(
            package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
        )
        self.assertTrue(package.is_file())


        from services.savings_service import SavingsService

        TransactionService.add_transaction(
            expected["cash_account_id"], 999.00, "expense", "Sonradan",
            "Yedekten sonra eklendi", detect_subscription=False)
        SavingsService.deposit_to_goal(
            expected["goal_id"], 100.00, expected["cash_account_id"])

        snapshot_b = _financial_snapshot(self.db_path)
        self.assertNotEqual(
            snapshot_a, snapshot_b,
            "yedek sonrası değişiklik snapshot'a yansımadı; test bir şey ölçmüyor",
        )


        result = restore_backup(
            package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            safety_backup_path=self.root / "safety.arcbak",
        )
        self.assertTrue(result["restored"])

        snapshot_restored = _financial_snapshot(self.db_path)
        self.assertEqual(
            snapshot_restored, snapshot_a,
            "geri yükleme aynı finansal durumu döndürmedi",
        )


        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


            from database.init_db import SCHEMA_VERSION

            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
                "geri yüklenen veritabanı şema kuşağı işaretini taşımıyor",
            )

    def test_restored_state_survives_reopening_the_profile(self):
        """Geri yükleme, YENİ bağlantılarla yeniden okunduğunda da doğru olmalı.

        Aynı açık bağlantılar ve süreç-içi önbelleklerle okumak yeterli değil:
        geri yükleme yalnızca bellekteki eski durum sayesinde doğru görünüyor
        olabilirdi. Burada profil, üretimin açılış yolundan yeniden açılıyor.
        """
        from database.init_db import initialize_database
        from services.backup_service import create_backup, restore_backup
        from services.transaction_service import TransactionService

        expected = _build_golden_financial_state(self)
        snapshot_a = _financial_snapshot(self.db_path)

        package = self.root / "golden.arcbak"
        create_backup(
            package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
        )
        TransactionService.add_transaction(
            expected["cash_account_id"], 42.00, "expense", "Sonradan",
            "Yedekten sonra", detect_subscription=False)
        self.assertNotEqual(_financial_snapshot(self.db_path), snapshot_a)

        restore_backup(
            package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            safety_backup_path=self.root / "safety.arcbak",
        )


        initialize_database()
        self.assertEqual(
            _financial_snapshot(self.db_path), snapshot_a,
            "profil yeniden açıldığında geri yüklenen durum korunmadı",
        )


if __name__ == "__main__":
    unittest.main()
