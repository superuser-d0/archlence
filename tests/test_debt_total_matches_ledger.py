"""Kayıtlı borç toplamı, defterin gerçekten ödeyeceği tutar olmalı.

Otomatik taksit döngüsü (`mixins/recurring_mixin`) ayda bir `monthly_payment`
tutarında işlem yazar ve borcu taksit SAYISI dolunca kapatır. Kayıtlı toplam
`taksit x vade`den büyükse, borç "kapandı" işaretlendiğinde o toplama hiç
ulaşılmamış olur.

Hesaplayıcı eskiden ek masrafları da borcun toplamına koyuyordu. O masraflar
bu deftere hiç uğramaz — kendi vadeleri vardır ve ödeme tablosunda
`amount / term` olarak ayrıca gösterilirler — dolayısıyla aylık ödemenin asla
kapatamayacağı bir bakiye yaratıyorlardı.

GÖSTERİLEN toplam ("Toplam Geri Ödeme") ek masraflarla kalır; o gerçekten
kredinin maliyetidir. Ayrılan şey yalnızca borç KAYDIdır.
"""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from unittest import mock

from utils.financial_decimal import fiat


class _FakeField:
    def __init__(self, text=""):
        self.text = text
        self.disabled = False


class DebtTotalMatchesLedgerTest(unittest.TestCase):
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

    def _calculate(self, principal, rate, months, custom_expenses=()):
        """`calculate_loan`u gerçek widget'lar olmadan çalıştırır."""
        from mixins.calculator_mixin import CalculatorMixin

        screen = CalculatorMixin.__new__(CalculatorMixin)
        screen.loan_amount = _FakeField(str(principal))
        screen.loan_rate = _FakeField(str(rate))
        screen.loan_term = _FakeField(str(months))
        screen.loan_type = _FakeField()


        screen.loan_type.disabled = False
        screen.loan_type_selected = "İhtiyaç"
        screen.custom_expenses = list(custom_expenses)
        screen.loan_custom_name = _FakeField("Test Kredisi")
        screen.loan_result_label = _FakeField()
        screen.loan_table_btn = _FakeField()
        screen.add_debt_btn = _FakeField()
        for widget in (screen.loan_result_label, screen.loan_table_btn,
                       screen.add_debt_btn):
            widget.opacity = 0
            widget.theme_text_color = None
            widget.text_color = None

        with mock.patch("mixins.calculator_mixin.toast"):
            CalculatorMixin.calculate_loan(screen)
        return screen

    def _stored(self):
        from database.db import SECRET_KEY
        from utils.crypto import decrypt

        with closing(sqlite3.connect(self.db_path)) as conn:
            total, monthly, count = conn.execute(
                "SELECT total_amount, monthly_payment, total_installments "
                "FROM active_debts"
            ).fetchone()
        return (
            Decimal(decrypt(str(total), SECRET_KEY)),
            Decimal(decrypt(str(monthly), SECRET_KEY)),
            int(count),
        )

    def test_stored_total_equals_the_instalments_that_will_be_paid(self):
        from database.db import insert_debt


        expense = {"name": "Sigorta", "type": "Çok Seferlik",
                   "amount": 1200.0, "term": 12}
        screen = self._calculate(100_000, 3.29, 36, custom_expenses=[expense])
        loan = screen.last_calculated_loan


        self.assertIn("Total Repayment", screen.loan_result_label.text)
        self.assertNotAlmostEqual(
            loan["total_amount"],
            loan["monthly_payment"] * loan["total_installments"] + 1200.0,
            places=2,
            msg="Ek masraf hâlâ borç toplamına giriyor",
        )

        insert_debt(loan["name"], loan["total_amount"],
                    loan["monthly_payment"], loan["total_installments"])
        total, monthly, count = self._stored()

        self.assertEqual(count, 36)
        self.assertEqual(total, monthly * count)

    def test_the_displayed_total_still_includes_extra_costs(self):
        """Gösterilen toplam ek masraflarla kalmalı — o kredinin maliyeti."""
        expense = {"name": "Sigorta", "type": "Çok Seferlik",
                   "amount": 1200.0, "term": 12}
        with_extra = self._calculate(
            100_000, 3.29, 36, custom_expenses=[expense]
        ).loan_result_label.text
        without = self._calculate(100_000, 3.29, 36).loan_result_label.text

        self.assertNotEqual(
            with_extra, without,
            "Ek masraf gösterilen toplamı değiştirmiyorsa kullanıcı kredinin "
            "gerçek maliyetini göremez",
        )

    def test_the_invariant_survives_both_rounding_orders(self):
        """Toplam, YUVARLANMIŞ taksitten türetilmeli — `emi * n`den değil.

        `insert_debt` iki alanı ayrı ayrı kuruşa yuvarlar ve iki sıra aynı
        sonucu vermez: emi=1,005 ve n=3 için `fiat(emi) * n` = 3,00 iken
        `fiat(emi * n)` = 3,01. Yanlış sıra seçilirse kayıtlı toplam,
        ödenecek taksitlerin toplamından bir kuruş fazla olur ve otomatik
        ödeme borcu kapattığında kapanmamış görünür.

        Bu test hesaplayıcıdan geçmez; değişmezi doğrudan sınar, çünkü
        anüite formülünün ayrışma üreten bir `emi` vermesi tesadüfe bağlıdır.
        """
        from database.db import insert_debt

        insert_debt("Ayrışma", float(fiat(1.005) * 3), 1.005, 3)
        total, monthly, count = self._stored()

        self.assertEqual(monthly, Decimal("1.00"))
        self.assertEqual(total, Decimal("3.00"))
        self.assertEqual(total, monthly * count)

    def test_a_loan_without_extras_is_unchanged(self):
        from database.db import insert_debt

        screen = self._calculate(100_000, 3.29, 36)
        loan = screen.last_calculated_loan
        insert_debt(loan["name"], loan["total_amount"],
                    loan["monthly_payment"], loan["total_installments"])
        total, monthly, count = self._stored()
        self.assertEqual(total, monthly * count)


if __name__ == "__main__":
    unittest.main()
