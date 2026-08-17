"""Tekrarlanan tahsilatın kayıt bütünlüğü ve tutar sınırı sözleşmeleri.

Buradaki testler `process_due_recurring_payment` ve onu besleyen yazma
yollarının ÜÇ ayrı sözleşmesini ölçer:

  1. Marker İZ SÜRÜLEBİLİR olmalı: `recurring_operation_markers.transaction_id`
     gerçekten o tahsilatın `transactions.id`'sini göstermeli. Sütun bugün
     hiçbir yerden OKUNMUYOR, yani yanlış değer kullanıcıya bir şey
     göstermiyor — ama bu sütunun tek işi kaynak göstermek, ve yanlış bir
     kaynak ilk okuyan tarafı (destek, dışa aktarma, ileride bir "bu tahsilatı
     iptal et" akışı) yanlış satıra götürür. Sessiz yanlışın en kötü türü.
  2. TUTAR SINIRI: sonlu olmayan/pozitif olmayan tutar hiçbir yazma yolundan
     KALICI olarak giremez. Arayüz bunları zaten üretemiyor; ölçtüğümüz şey
     servis sınırının kendisi.
  3. KARAR VE YAZMA AYNI TRANSACTION'DA: harcama izni, yazmanın tuttuğu
     cursor'dan sorulmalı — ayrı bir bağlantı açan `check_spending_allowed`
     ile değil (o fonksiyonun kendi sözleşmesi bunu yasaklıyor).
"""
import math
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest import mock

from tests.fixtures import AccountFixtureMixin
from tests.test_connection_ownership_contract import connection_ledger


class RecurringChargeIntegrityTest(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account("Vadesiz", balance=10000.0)

    # ─── Yardımcılar ─────────────────────────────────────────────────────────

    def _add(self, name="Netflix", amount=149.99, **kwargs):
        from database.db import (
            get_active_recurring_payments, insert_recurring_payment,
        )
        insert_recurring_payment(
            name, amount, "Dijital Platformlar", "monthly",
            date.today().isoformat(), auto_deduct=0,
            account_id=self.account_id, recurrence_day=date.today().day,
            **kwargs,
        )
        return next(
            p for p in get_active_recurring_payments() if p["name"] == name
        )

    def _rows(self, sql, *params):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()

    def _counts(self):
        return {
            table: self._rows(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]
            for table in ("transactions", "balance_events",
                          "recurring_payments", "recurring_operation_markers")
        }

    # ─── 1. Marker izlenebilirliği ───────────────────────────────────────────

    def test_marker_records_the_transaction_it_charged(self):
        """Marker'ın işaret ettiği satır GERÇEKTEN o tahsilatın işlemi olmalı.

        Düzeltmeden önce buraya `balance_events.id` yazılıyordu: `lastrowid`
        cursor'a ait ve `adjust_account_balance` aynı cursor'la defter satırını
        INSERT ediyor, yani marker'a ulaşana kadar değer çoktan değişmiş
        oluyordu.
        """
        from database.db import process_due_recurring_payment

        payment = self._add()
        self.assertTrue(process_due_recurring_payment(payment))

        transactions = self._rows("SELECT id FROM transactions ORDER BY id")
        markers = self._rows("SELECT * FROM recurring_operation_markers")
        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(markers), 1)
        self.assertEqual(
            markers[0]["transaction_id"], transactions[0]["id"],
            "marker gerçek transactions.id'yi göstermiyor",
        )

    def test_balance_event_and_marker_point_at_the_same_transaction(self):
        """Defter satırı ile marker AYNI işlemi göstermeli — tek gerçeklik."""
        from database.db import process_due_recurring_payment

        payment = self._add()
        process_due_recurring_payment(payment)

        transaction_id = self._rows("SELECT id FROM transactions")[0]["id"]
        event = self._rows(
            "SELECT ref_id FROM balance_events WHERE source='recurring_payment'"
        )[0]
        marker = self._rows("SELECT * FROM recurring_operation_markers")[0]
        self.assertEqual(event["ref_id"], transaction_id)
        self.assertEqual(marker["transaction_id"], transaction_id)

    def test_second_pass_over_the_same_due_date_changes_nothing(self):
        """Idempotency: aynı vade ikinci kez işlenirse ne tahsilat ne marker değişir."""
        from database.db import process_due_recurring_payment

        payment = self._add()
        self.assertTrue(process_due_recurring_payment(payment))
        after_first = (self._counts(),
                       self._rows("SELECT * FROM recurring_operation_markers"))

        # Bayat UI nesnesi eski vadeyi taşımaya devam eder — gerçek tekrar
        # denemesi tam olarak böyle görünür.
        self.assertFalse(process_due_recurring_payment(payment))
        self.assertEqual(
            (self._counts(),
             self._rows("SELECT * FROM recurring_operation_markers")),
            after_first,
            "ikinci geçiş kalıcı durumu değiştirdi",
        )

    # ─── 2. Tutar sınırı ─────────────────────────────────────────────────────

    def test_insert_rejects_non_finite_and_non_positive_amounts(self):
        from database.db import insert_recurring_payment

        before = self._counts()
        for amount in (float("nan"), float("inf"), float("-inf"),
                       "nan", "inf", "-inf", 0, -5.0, "abc"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    insert_recurring_payment(
                        f"Kötü {amount!r}", amount, "Dijital", "monthly",
                        date.today().isoformat(), auto_deduct=0,
                        account_id=self.account_id,
                        recurrence_day=date.today().day,
                    )
        self.assertEqual(self._counts(), before, "geçersiz tutar satır yazdı")

    def test_subscription_amount_update_rejects_non_finite_amounts(self):
        from services.recurring_service import update_subscription_amount

        payment = self._add(amount=100.0)
        for amount in (float("nan"), float("inf"), float("-inf"),
                       "nan", "inf", 0, -1.0):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    update_subscription_amount(payment["id"], amount)

        from database.db import get_active_recurring_payments
        current = get_active_recurring_payments()[0]
        self.assertEqual(current["amount"], 100.0,
                         "reddedilen güncelleme yine de tutarı değiştirdi")

    def test_stored_amount_is_the_amount_that_will_be_charged(self):
        """Saklanan tutar tahsil edilecek tutardır — ikisi ayrı yuvarlanmaz."""
        from database.db import (
            get_active_recurring_payments, process_due_recurring_payment,
        )

        payment = self._add(name="Kuruşlu", amount=149.994)
        self.assertEqual(get_active_recurring_payments()[0]["amount"], 149.99)

        process_due_recurring_payment(payment)
        from services.account_service import AccountService
        self.assertEqual(
            AccountService.get_account(self.account_id)["balance"],
            10000.0 - 149.99,
        )

    def test_a_pre_existing_non_finite_row_is_reported_as_invalid(self):
        """Eski bir yapının bıraktığı `nan`, okuma yolunda GEÇERLİ sayılmamalı.

        Bayrak tam da toplam alan tarafı (bütçe rezervi) korumak için var;
        `float("nan")` istisna üretmediği için eskiden `True` dönüyordu ve
        aylık bütçe genel bir `ValueError` ile kırılıyordu.
        """
        from database.db import SECRET_KEY, get_active_recurring_payments
        from utils.crypto import encrypt
        from utils.errors import FinancialDataIntegrityError

        self._add(name="Bozuk", amount=10.0)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE recurring_payments SET amount = ?",
                (encrypt("nan", SECRET_KEY),),
            )
            conn.commit()
        finally:
            conn.close()

        payment = get_active_recurring_payments()[0]
        self.assertFalse(payment["amount_is_valid"])
        self.assertTrue(math.isfinite(payment["amount"]))

        from services.budget_service import get_reserved_recurring_items
        with self.assertRaises(FinancialDataIntegrityError):
            get_reserved_recurring_items(date.today().month, date.today().year)

    def test_a_pre_existing_non_positive_row_is_reported_as_invalid(self):
        """Sıfır ve negatif eski kayıtlar da GEÇERSİZ — ve sessiz olan buydu.

        `recurring_payments.amount` bir BÜYÜKLÜK; yön `transaction_type`
        sütununda taşınır. Negatif bir tutar bu yüzden "ters yönlü ödeme"
        değil, geçersiz kayıttır ve üç yazma yolunun üçü de onu reddeder.
        Okuma yolu ise sonlu olmayanı yakalarken negatifi geçiriyordu:
        -10,00'lık bir satır aylık bütçeye -10,00 rezerv olarak giriyor ve
        harcanabilir tutarı 10 TL FAZLA gösteriyordu (ölçüldü). Sonlu
        olmama gürültülü kırılıyordu, negatif SESSİZ yanlış toplam
        üretiyordu.

        Veri düzeltilmiyor: `abs()` alınmıyor, satır güncellenmiyor.
        """
        from database.db import SECRET_KEY, get_active_recurring_payments
        from utils.crypto import decrypt, encrypt
        from utils.errors import FinancialDataIntegrityError
        from services.budget_service import calculate_monthly_budget

        for stored in ("-10", "0", "0.0", "-0.004"):
            with self.subTest(stored=stored):
                self._add(name=f"Legacy {stored}", amount=10.0)
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute(
                        "UPDATE recurring_payments SET amount = ?"
                        " WHERE id = (SELECT MAX(id) FROM recurring_payments)",
                        (encrypt(stored, SECRET_KEY),),
                    )
                    conn.commit()
                finally:
                    conn.close()

                payments = get_active_recurring_payments()
                self.assertFalse(
                    payments[-1]["amount_is_valid"],
                    f"{stored!r} geçerli tutar sayıldı",
                )
                with self.assertRaises(FinancialDataIntegrityError):
                    calculate_monthly_budget(
                        date.today().month, date.today().year)

                # Kayıt OLDUĞU GİBİ duruyor — sessiz normalizasyon yok.
                conn = sqlite3.connect(self.db_path)
                try:
                    raw = conn.execute(
                        "SELECT amount FROM recurring_payments"
                        " WHERE id = (SELECT MAX(id) FROM recurring_payments)"
                    ).fetchone()[0]
                    conn.execute(
                        "DELETE FROM recurring_payments"
                        " WHERE id = (SELECT MAX(id) FROM recurring_payments)")
                    conn.commit()
                finally:
                    conn.close()
                self.assertEqual(decrypt(raw, SECRET_KEY), stored)

    # ─── İade sınırı ─────────────────────────────────────────────────────────

    def test_refund_rejects_a_corrupted_charge_without_touching_money(self):
        """İade edilecek tahsilatın SAKLANMIŞ tutarı bozuksa hiçbir şey yazılmaz.

        `inf` ölçülen sonuç: iade COMMIT ediliyordu ve hesap bakiyesi kalıcı
        olarak `inf` oluyordu (işlem satırı + defter satırı + marker dahil).
        `nan` ise `balance_events.delta` NOT NULL kısıtına takılıp ham bir
        `sqlite3.IntegrityError` olarak dışarı çıkıyordu. Negatif/sıfır tutar
        ise sessizce "bu ay tahsilat yok" sayılıyordu.
        """
        from database.db import SECRET_KEY, process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge
        from utils.crypto import encrypt
        from utils.errors import FinancialDataIntegrityError

        for stored in ("nan", "inf", "-inf", "-50.0", "0.0"):
            with self.subTest(stored=stored):
                self.setUp()
                payment = self._add(amount=100.0)
                process_due_recurring_payment(payment)

                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute(
                        "UPDATE transactions SET amount = ? WHERE type='expense'",
                        (encrypt(stored, SECRET_KEY),),
                    )
                    conn.commit()
                finally:
                    conn.close()

                before = self._counts()
                balance_before = self._rows(
                    "SELECT balance FROM accounts WHERE id=?",
                    self.account_id)[0]["balance"]

                with self.assertRaises(FinancialDataIntegrityError):
                    refund_current_period_charge(payment["id"])

                self.assertEqual(self._counts(), before,
                                 "bozuk tahsilat için iade satırı yazıldı")
                self.assertEqual(
                    self._rows("SELECT balance FROM accounts WHERE id=?",
                               self.account_id)[0]["balance"],
                    balance_before,
                    "bozuk tahsilat bakiyeyi değiştirdi",
                )

    def test_healthy_refund_still_works_and_stays_idempotent(self):
        from database.db import process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge
        from services.account_service import AccountService

        payment = self._add(amount=100.0)
        process_due_recurring_payment(payment)
        self.assertEqual(
            AccountService.get_account(self.account_id)["balance"],
            10000.0 - 100.0)

        self.assertEqual(refund_current_period_charge(payment["id"]), 100.0)
        after_first = self._counts()
        self.assertEqual(
            AccountService.get_account(self.account_id)["balance"], 10000.0)

        # İkinci çağrı marker yüzünden hiçbir şey yapmaz.
        self.assertEqual(refund_current_period_charge(payment["id"]), 0.0)
        self.assertEqual(self._counts(), after_first)
        self.assertEqual(
            AccountService.get_account(self.account_id)["balance"], 10000.0)

    # ─── 3. Karar ve yazma aynı transaction'da ───────────────────────────────

    def test_charge_decides_and_writes_on_a_single_connection(self):
        """Harcama izni ayrı bir bağlantıdan SORULMAMALI.

        `check_spending_allowed` kendi bağlantısını açar ve docstring'i onu
        yazma yolunda kullanmayı açıkça yasaklar; `transaction_service` ve
        `asset_purchase_service` kararı çoktan çağıranın cursor'ına taşımıştı.
        Bu test o sözleşmeyi ölçülebilir kılıyor: tahsilat TEK bağlantı açar.
        """
        from database.db import process_due_recurring_payment

        payment = self._add()
        with connection_ledger() as ledger:
            process_due_recurring_payment(payment)
        self.assertEqual(
            len(ledger.opened), 1,
            "tahsilat yazma kilidini tutarken ikinci bir bağlantı açtı",
        )
        self.assertEqual(ledger.leaked, [])

    def test_credit_limit_is_enforced_from_inside_the_write_lock(self):
        from database.db import process_due_recurring_payment
        from services.account_service import AccountService

        card_id = AccountService.create_account(
            "Kart", "credit_card", initial_balance=0, credit_limit=100.0,
        )
        payment = self._add(name="Pahalı abonelik", amount=150.0)
        payment = dict(payment, account_id=card_id)

        before = self._counts()
        with self.assertRaisesRegex(ValueError, "Limit yetersiz"):
            process_due_recurring_payment(payment)
        self.assertEqual(self._counts(), before,
                         "reddedilen tahsilattan parçalı kayıt kaldı")
        self.assertEqual(AccountService.get_account(card_id)["debt"], 0.0)

    def test_frozen_account_still_blocks_the_charge(self):
        from database.db import process_due_recurring_payment

        payment = self._add()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE accounts SET is_frozen = 1 WHERE id = ?",
                         (self.account_id,))
            conn.commit()
        finally:
            conn.close()

        before = self._counts()
        with self.assertRaises(ValueError):
            process_due_recurring_payment(payment)
        self.assertEqual(self._counts(), before)


if __name__ == "__main__":
    unittest.main()
