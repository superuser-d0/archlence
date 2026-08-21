"""Birikim hedefinin durumu, aynı serviste iki farklı hassasiyetle karar veremez.

NEDEN VAR: `savings_service` üç yerde aynı ekonomik soruyu soruyor ama
ikisinde kuruş hassasiyetinde, birinde ham `REAL` değeriyle:

    tamamlanma   ROUND(current_amount, 2) >= ROUND(target_amount, 2)
    çekim yeterli ROUND(current_amount, 2) >= ROUND(?, 2)
    durum geri al current_amount < target_amount        <-- yuvarlamasız

`current_amount` `current_amount + ?` ile birikiyor, yani ikili kayan nokta
artığı taşıyor (aynı dosyadaki yorum "3000 x 0,10 -> 299.9999999999997"
örneğini zaten kaydetmiş). Sonuç: hedef tam olarak hedefi tutarken ekranda
"10,40 / 10,40" yazıyor ama etiketi "aktif" oluyor.

Sıradan bir kullanımla üretiliyor — on bir servis çağrısı, gerçekçi tutarlar.
Para yanlış değil; yanlış olan hedefin tamamlanmış sayılmaması.
"""

import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


class SavingsStatusUsesKurusPrecision(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="archlence-savstatus-")
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

        from services.account_service import AccountService
        self.account_id = AccountService.create_account(
            "Kaynak", "checking", initial_balance=1000.0)

    def _goal_row(self, goal_id):
        from database.db import get_connection
        with closing(get_connection()) as conn, conn:
            return conn.execute(
                "SELECT current_amount, target_amount, status "
                "FROM savings_goals WHERE id=?", (goal_id,)
            ).fetchone()

    def _drifted_completed_goal(self):
        """Hedefi TAM olarak tutan, ama ham değeri bir tık altında kalan hedef.

        Dizi bilerek yalnız servis çağrılarından oluşuyor — doğrudan SQL ile
        sapma enjekte etmek, üretimde oluşamayacak bir durumu sınamak olurdu.
        Sapmayı üreten şey aşan yatırma ve fazlalığın geri çekilmesi:
        5,40 + 10,00 - 5,00 tam olarak 10,40 eder, ikili kayan noktada
        10.399999999999999 kalır.
        """
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Bozuk para", 10.40)
        for _ in range(9):
            SavingsService.deposit_to_goal(goal_id, 0.60, self.account_id)
        SavingsService.deposit_to_goal(goal_id, 10.00, self.account_id)
        SavingsService.withdraw_from_goal(goal_id, 5.00, self.account_id)
        return goal_id

    def test_completed_goal_survives_withdrawing_the_excess(self):
        """ASIL HATA: hedefi hâlâ tutan bir hedef "aktif"e düşmemeli."""
        from utils.financial_decimal import fiat

        goal_id = self._drifted_completed_goal()
        current, target, status = self._goal_row(goal_id)


        self.assertLess(
            current, target,
            "ham değer sapmadı; dizi artık hatayı üretmiyor olabilir",
        )
        self.assertEqual(
            fiat(current), fiat(target),
            "kuruş hassasiyetinde hedef tutulmuyor; senaryo yanlış kurulmuş",
        )
        self.assertEqual(
            status, "tamamlandi",
            f"ekranda {fiat(current)}/{fiat(target)} yazarken hedef "
            f"'{status}' olarak işaretlendi",
        )

    def test_status_returns_to_active_when_the_goal_really_drops_below(self):
        """Tamamlayıcı vaka: düzeltme "tamamlandı"yı yapışkan yapmamalı.

        Kuruş hassasiyetinde gerçekten hedefin altına düşen bir çekim,
        durumu "aktif"e geri almalı. Bu test olmadan, karşılaştırmayı
        yuvarlamak "hedef bir kez tamamlandıysa hep tamamlanmış kalır"
        hatasına dönüşebilirdi.
        """
        from services.savings_service import SavingsService

        goal_id = self._drifted_completed_goal()
        SavingsService.withdraw_from_goal(goal_id, 0.01, self.account_id)

        current, target, status = self._goal_row(goal_id)
        self.assertLess(round(current, 2), round(target, 2))
        self.assertEqual(
            status, "aktif",
            "hedefin altına düşüldüğü hâlde 'tamamlandı' kaldı",
        )


if __name__ == "__main__":
    unittest.main()
