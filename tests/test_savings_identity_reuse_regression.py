"""Kimlik yeniden kullanımı: restore sonrası para YANLIŞ hedefe gidiyor.

ÖLÇÜLEN KUSUR (sözleşme: docs/ARCHITECTURE.md). Birikim hedefleri iki yerde
yaşıyordu: para SQLite'ta, ekrandaki kart ise `savings_goals.json`'da. JSON
hedefi yalnızca SQL satırının SAYISAL id'siyle işaretliyor.

`sqlite_sequence` `finance.db` dosyasının İÇİNDE. Restore dosyayı bütün olarak
değiştirdiği için sayaç da yedekteki değere geri sarıyor; restore'dan sonra
açılan ilk hedef, bayat JSON'un hâlâ işaret ettiği id'yi yeniden alıyor.
Kullanıcı ekranda "Tatil Fonu" kartına para yatırıyor, para bambaşka bir
hedefe ("Yeni Hedef") yazılıyor ve hesabından gerçekten çıkıyor.

Bu dosya planın 7 adımını GERÇEK bileşenlerle kuruyor: gerçek `SavingsService`,
gerçek `finance.db` dosyaları, gerçek `create_backup`/`restore_backup`.
`sqlite_sequence`'i taklit eden bir unit test bu kusuru kanıtlayamaz — sayacın
geri sarması restore'un dosya değiştirme davranışının SONUCU, ayrı bir olgu
değil.

SÜRÜM-NÖTR OLMASI KASITLI: yatırma çağrısı `_deposit_from_card` üzerinden
geçiyor. Uygulama servis sınırına taşındığında o sınırı, henüz taşınmamışken
bugünkü (`_ensure_goal_db_id` + `deposit_to_goal`) yolunu kullanıyor. İddia her
iki hâlde de aynı: **kullanıcının gördüğü karttan yapılan yatırım başka bir
hedefe gidemez.** Test bu yüzden düzeltmeden ÖNCE kırmızı, sonra yeşildir.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.savings_service import SavingsService

PASSPHRASE = "kimlik-yeniden-kullanim-2026"


class _FakeStore:
    """`JsonStore`'un testte kullanılan üç metodu — diske yazmadan.

    Gerçek dosyaya yazmak bu testin ölçtüğü şeyi değiştirmez; ölçülen şey
    SQL tarafındaki kimlik çakışması. JSON tarafı yalnızca "ekranda duran
    bayat kart" rolünde.
    """

    def __init__(self):
        self.data = {}

    def exists(self, key):
        return key in self.data

    def get(self, key):
        return self.data[key]

    def put(self, key, **values):
        self.data[key] = values


def _deposit_from_card(app, card, amount, account_id):
    """Bir hedef KARTINDAN yatırma işleminin uygulama yolu.

    Yeni sınır (`SavingsMixin.deposit_into_goal`) varsa o kullanılır; yoksa
    bugünkü `_do_add` gövdesinin yaptığı iki adım birebir tekrarlanır.
    """
    from mixins.savings_mixin import SavingsMixin

    handler = getattr(SavingsMixin, "deposit_into_goal", None)
    if handler is not None:
        return handler(app, card, amount, account_id)

    goal_id = SavingsMixin._ensure_goal_db_id(app, card)
    return SavingsService.deposit_to_goal(goal_id, amount, account_id)


class IdentityReuseAfterRestoreTest(unittest.TestCase):
    """Planın 7 adımı, gerçek dosyalar ve gerçek restore ile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.package = root / "backup.archlence-backup"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)

        self._db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self._db_patch.start()
        self.addCleanup(self._db_patch.stop)
        self._key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self._key_patch.start()
        self.addCleanup(self._key_patch.stop)

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=5000.0
        )


    def _sqlite_sequence(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'savings_goals'"
            ).fetchone()
        return row[0] if row else None

    def _balance(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (self.account_id,)
            ).fetchone()[0]

    def _ledger_rows(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM balance_events"
            ).fetchone()[0]

    def _goal_amounts(self):
        return {
            goal["goal_name"]: float(goal["current_amount"])
            for goal in SavingsService.get_goals()
        }

    def _app_with_stale_card(self, card):
        app = SimpleNamespace()
        app.savings_goals = [card]
        app.store = _FakeStore()
        app.store.put("goals", data=app.savings_goals)
        return app

    def _backup(self):
        from services.backup_service import create_backup

        create_backup(
            self.package,
            PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )

    def _restore(self):
        from services.backup_service import restore_backup

        restore_backup(
            self.package,
            PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
            safety_backup_path=Path(self._tmp.name) / "safety.archlence-backup",
        )


    def test_stale_card_cannot_fund_a_goal_that_reused_its_id(self):

        first_id = SavingsService.create_goal("Araba Fonu", 20000.0)
        self.assertEqual(first_id, 1)


        self._backup()
        self.assertEqual(self._sqlite_sequence(), 1)


        holiday_id = SavingsService.create_goal("Tatil Fonu", 10000.0)
        self.assertEqual(holiday_id, 2)
        stale_card = {
            "id": holiday_id,
            "name": "Tatil Fonu",
            "target": 10000.0,
            "current": 0.0,
            "color": "blue",
            "auto_deposit": False,
            "created_at": "2026-01-05",
        }


        self._restore()
        self.assertEqual(
            self._sqlite_sequence(), 1,
            "restore sqlite_sequence'i yedekteki değere döndürmeli",
        )
        self.assertEqual(
            [g["goal_name"] for g in SavingsService.get_goals()],
            ["Araba Fonu"],
            "restore edilen DB yalnız yedekteki hedefi taşımalı",
        )


        new_id = SavingsService.create_goal("Yeni Hedef", 3000.0)
        self.assertEqual(
            new_id, holiday_id,
            "kusurun ön şartı: sayısal id yeniden kullanılıyor",
        )

        balance_before = self._balance()
        ledger_before = self._ledger_rows()


        app = self._app_with_stale_card(stale_card)
        refusal = None
        try:
            _deposit_from_card(app, stale_card, 250.0, self.account_id)
        except ValueError as exc:
            refusal = exc


        amounts = self._goal_amounts()
        self.assertEqual(
            amounts.get("Yeni Hedef"), 0.0,
            "BAYAT KART BAŞKA BİR HEDEFİ FONLADI — sessiz yanlış atıf",
        )
        self.assertNotIn(
            "Tatil Fonu", amounts,
            "restore edilen profilde Tatil Fonu hiç olmamalı",
        )
        self.assertEqual(
            self._balance(), balance_before,
            "reddedilen yatırımda hesap bakiyesi değişmemeli",
        )
        self.assertEqual(
            self._ledger_rows(), ledger_before,
            "reddedilen yatırım deftere satır yazmamalı",
        )

        self.assertIsNotNone(
            refusal,
            "işlem sessizce yutulamaz; kullanıcıya tutarlı bir durum "
            "bildirilmeli",
        )
        message = str(refusal)
        self.assertTrue(message.strip(), "kullanıcıya boş hata gösterilemez")
        for forbidden in ("Traceback", "sqlite3", "SELECT", "UPDATE"):
            self.assertNotIn(
                forbidden, message,
                f"kullanıcı metninde teknik ayrıntı: {forbidden!r}",
            )

    def test_restore_brings_back_the_backed_up_goal_for_the_user(self):
        """Kök nedenin (a) yarısı: restore edilen hedef kullanıcıya görünmeli.

        Yedek yalnız SQL taşıyor; arayüz JSON'dan okuduğu sürece boş profile
        yapılan restore hedefleri GÖSTERMİYORDU.
        """
        SavingsService.create_goal("Araba Fonu", 20000.0)
        self._backup()


        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("DELETE FROM savings_goals")
            conn.commit()
        self.assertEqual(SavingsService.get_goals(), [])

        self._restore()

        names = [goal["goal_name"] for goal in SavingsService.get_goals()]
        self.assertEqual(names, ["Araba Fonu"])


if __name__ == "__main__":
    unittest.main()
