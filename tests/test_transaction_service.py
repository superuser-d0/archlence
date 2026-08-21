import os
import tempfile
import unittest
from decimal import Decimal
from unittest import mock


class TransactionStatementTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.card_id = AccountService.create_account(
            "Test Kart", "credit_card", credit_limit=10000
        )
        self.other_id = AccountService.create_account(
            "Diğer Kart", "credit_card", credit_limit=10000
        )

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add(self, account_id, amount, kind, description, date):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            account_id,
            amount,
            kind,
            "Test",
            description,
            transaction_date=date,
        )

    def test_statement_is_newest_first_and_isolated_by_account(self):
        from services.transaction_service import TransactionService

        self._add(self.card_id, 100, "expense", "Eski harcama", "2026-07-20 10:00:00")
        self._add(self.card_id, 50, "income", "İade", "2026-07-21 10:00:00")
        self._add(self.other_id, 999, "expense", "Başka kart", "2026-07-22 10:00:00")

        items = TransactionService.get_recent_for_account(self.card_id, limit=None)

        self.assertEqual([item["description"] for item in items], ["İade", "Eski harcama"])
        self.assertEqual([item["amount"] for item in items], [50.0, 100.0])
        self.assertEqual([item["date"] for item in items], ["2026-07-21", "2026-07-20"])

    def test_recent_summary_respects_limit_but_statement_does_not(self):
        from services.transaction_service import TransactionService

        for index in range(5):
            self._add(
                self.card_id,
                index + 1,
                "expense",
                f"Hareket {index}",
                f"2026-07-{index + 1:02d} 10:00:00",
            )

        self.assertEqual(len(TransactionService.get_recent_for_account(self.card_id, limit=3)), 3)
        self.assertEqual(len(TransactionService.get_recent_for_account(self.card_id, limit=None)), 5)

    def test_empty_description_falls_back_to_category(self):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 25, "expense", "Market", "", transaction_date="2026-07-20 10:00:00"
        )
        item = TransactionService.get_recent_for_account(self.card_id, limit=None)[0]
        self.assertEqual(item["description"], "Market")

    def test_negative_limit_is_rejected(self):
        from services.transaction_service import TransactionService

        with self.assertRaisesRegex(ValueError, "negatif"):
            TransactionService.get_recent_for_account(self.card_id, limit=-1)


    def test_six_installments_divides_total_and_lists_plan(self):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 6000, "expense", "Elektronik", "Telefon (6 Taksit)",
            transaction_date="2026-07-22 10:00:00", installments=6,
        )
        plans = TransactionService.get_installment_plans(self.card_id)
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan["total_amount"], 6000.0)
        self.assertEqual(plan["monthly_amount"], 1000.0)   # 6000 / 6
        self.assertEqual(plan["total_installments"], 6)
        self.assertEqual(plan["paid_installments"], 0)
        self.assertEqual(plan["remaining_installments"], 6)
        self.assertEqual(plan["remaining_amount"], 6000.0)
        self.assertEqual(plan["description"], "Telefon (6 Taksit)")

    def test_uneven_split_never_drifts_from_the_principal(self):
        """Tam bölünmeyen taksit, anaparadan sapan bir borç göstermemeli.

        Mevcut kapsam yalnızca 6000/6 gibi TAM BÖLÜNEN vakaları kullanıyordu,
        bu yüzden kusuru hiç göremiyordu: `round(float(tutar)/n, 2)` ile
        `aylık x kalan` birlikte anaparayı korumuyordu. 1000,00/3 -> 333,33 ve
        3 x 333,33 = 999,99 (bir kuruş EKSİK); 12.500,00/12 -> 1.041,67 ve
        12 x 1.041,67 = 12.500,04 (dört kuruş FAZLA). Sapma iki yönde de
        oluşabildiği için tek yönlü bir kontrol yeterli değil.

        Taksit sayısı uygulamada 1-12 ile sınırlı, o yüzden vakalar bu
        aralıktan seçildi — erişilemeyen bir senaryoyu test etmek olmaz.
        """
        from services.transaction_service import TransactionService

        for principal, count in ((1000, 3), (12500, 12), (4999.90, 7)):
            with self.subTest(principal=principal, installments=count):
                from services.account_service import AccountService
                account_id = AccountService.create_account(
                    f"Kart {principal}-{count}", "credit_card",
                    credit_limit=100000,
                )
                TransactionService.add_transaction(
                    account_id, principal, "expense", "Elektronik",
                    f"{count} taksit",
                    transaction_date="2026-07-22 10:00:00",
                    installments=count,
                )
                plan = TransactionService.get_installment_plans(account_id)[0]


                self.assertEqual(plan["remaining_amount"], round(principal, 2))


                monthly = Decimal(str(plan["monthly_amount"]))
                last = Decimal(str(plan["remaining_amount"])) - monthly * (count - 1)
                total_paid = monthly * (count - 1) + last
                self.assertEqual(total_paid, Decimal(str(round(principal, 2))))

    def test_remaining_amount_shrinks_by_the_principal_not_the_instalment(self):
        """Ödeme ilerledikçe kalan borç anaparadan düşülmeli."""
        from services.transaction_service import TransactionService

        from database.db import managed_connection
        from services.account_service import AccountService
        account_id = AccountService.create_account(
            "Kart kalan", "credit_card", credit_limit=100000
        )
        TransactionService.add_transaction(
            account_id, 1000, "expense", "Elektronik", "3 taksit",
            transaction_date="2026-07-22 10:00:00", installments=3,
        )
        plan_id = TransactionService.get_installment_plans(account_id)[0]["id"]

        with managed_connection() as conn:
            cur = conn.cursor()
            for paid, expected in ((1, 666.67), (2, 333.34)):
                cur.execute(
                    "UPDATE installment_plans SET paid_installments = ? "
                    "WHERE id = ?",
                    (paid, plan_id),
                )
                conn.commit()
                plan = TransactionService.get_installment_plans(account_id)[0]
                self.assertEqual(
                    plan["remaining_amount"], expected,
                    f"{paid} taksit ödenmişken kalan {expected} olmalı",
                )

    def test_installment_plans_are_isolated_by_card(self):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 1200, "expense", "Market", "TV (3 Taksit)",
            transaction_date="2026-07-22 10:00:00", installments=3,
        )
        self.assertEqual(TransactionService.get_installment_plans(self.other_id), [])

    def test_single_shot_and_one_installment_create_no_plan(self):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 500, "expense", "Market", "Tek çekim",
            transaction_date="2026-07-22 10:00:00",
        )
        TransactionService.add_transaction(
            self.card_id, 500, "expense", "Market", "1 taksit = tek çekim",
            transaction_date="2026-07-22 10:00:00", installments=1,
        )
        self.assertEqual(TransactionService.get_installment_plans(self.card_id), [])

    def test_installment_count_out_of_range_rejected(self):
        from services.transaction_service import TransactionService

        for bad in (0, 13, -2):
            with self.assertRaisesRegex(ValueError, "1 ile 12"):
                TransactionService.add_transaction(
                    self.card_id, 100, "expense", "Market", "x",
                    transaction_date="2026-07-22 10:00:00", installments=bad,
                )

        self.assertEqual(TransactionService.get_installment_plans(self.card_id), [])
        self.assertEqual(
            TransactionService.get_recent_for_account(self.card_id, limit=None), []
        )

    def test_installment_description_not_stored_plaintext(self):
        from database.db import get_connection
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 1200, "expense", "Elektronik", "Gizli Alışveriş (3 Taksit)",
            transaction_date="2026-07-22 10:00:00", installments=3,
        )
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT description FROM installment_plans WHERE account_id = ?",
                (self.card_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertNotIn("Gizli", str(row["description"]))

        plans = TransactionService.get_installment_plans(self.card_id)
        self.assertEqual(plans[0]["description"], "Gizli Alışveriş (3 Taksit)")

    def test_installment_charge_hits_card_balance_once_with_full_amount(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 6000, "expense", "Elektronik", "Telefon (6 Taksit)",
            transaction_date="2026-07-22 10:00:00", installments=6,
        )
        card = AccountService.get_account(self.card_id)

        self.assertEqual(card["debt"], 6000.0)
        items = TransactionService.get_recent_for_account(self.card_id, limit=None)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["amount"], 6000.0)


if __name__ == "__main__":
    unittest.main()
