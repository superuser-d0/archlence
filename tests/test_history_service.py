"""Faz 2 bakiye defteri ve zaman makinesi testleri.

Geçici bir veritabanı üzerinde çalışır — kullanıcının gerçek finance.db'sine
dokunulmaz (tests/test_account_service.py'deki DB_NAME patch deseni).

NOT: tests/test_metrics.py bir unittest değil, assertion'ı olmayan bir yazdırma
script'i; oradaki "çek → Python'da hesapla" akışı örnek alındı ama test iskeleti
olarak test_account_service.py izlendi.

Testlerin çoğu olayları SENTETİK olarak (doğrudan balance_events'e yazarak)
kurar; böylece geçmiş tarihli senaryolar kurulabiliyor. Ayrıca gerçek
SavingsService çağrılarının defterde göründüğü ayrı bir sınıfta doğrulanır —
sentetik veri, üretim kodunun gerçekten kayıt yazdığını kanıtlamaz.
"""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _LedgerTestBase(unittest.TestCase):

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

    # ── yardımcılar ──────────────────────────────────────────────────────────

    def _day(self, days_ago):
        return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    def _add_event(self, delta, days_ago, entity_type="account", entity_id=1,
                   source="test", resulting=None, hhmmss="12:00:00"):
        """Defterе doğrudan sentetik olay yazar (geçmiş tarihli senaryolar için)."""
        ts = f"{self._day(days_ago)} {hhmmss}"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO balance_events (ts, entity_type, entity_id, delta,"
            " resulting_value, source, ref_id) VALUES (?,?,?,?,?,?,NULL)",
            (ts, entity_type, entity_id, delta, resulting, source),
        )
        conn.commit()
        conn.close()

    def _add_snapshot(self, days_ago, total, goals=None):
        conn = sqlite3.connect(self.db_path)
        import json
        conn.execute(
            "INSERT INTO daily_balance_snapshot (snapshot_date, total_balance,"
            " breakdown_json) VALUES (?,?,?)",
            (self._day(days_ago), total,
             json.dumps({"accounts": {}, "savings_goals": goals or {}})),
        )
        conn.commit()
        conn.close()

    def _clear_ledger(self):
        """Defteri boşaltır — sentetik replay senaryoları için.

        initialize_database üç varsayılan hesabı açılış olaylarıyla birlikte
        kuruyor (toplam 14.000). Bu testler replay MATEMATİĞİNİ ölçüyor, o
        yüzden kendi olaylarıyla baş başa kalmalılar. Gerçek yazma noktalarını
        doğrulayan RealWriteSitesTestCase defteri KASITLI olarak temizlemez.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM balance_events")
        conn.commit()
        conn.close()

    def _events(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM balance_events ORDER BY id")]
        conn.close()
        return rows

    def _balance(self, account_id=1):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT balance FROM accounts WHERE id = ?",
                           (account_id,)).fetchone()
        conn.close()
        return row[0]


class SchemaTestCase(_LedgerTestBase):

    def test_tables_exist_with_expected_columns(self):
        conn = sqlite3.connect(self.db_path)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        ev = {r[1] for r in conn.execute("PRAGMA table_info(balance_events)")}
        sn = {r[1] for r in conn.execute("PRAGMA table_info(daily_balance_snapshot)")}
        conn.close()

        self.assertIn("balance_events", names)
        self.assertIn("daily_balance_snapshot", names)
        self.assertEqual(ev, {"id", "ts", "entity_type", "entity_id", "delta",
                              "resulting_value", "source", "ref_id"})
        self.assertEqual(sn, {"id", "snapshot_date", "total_balance", "breakdown_json"})

    def test_snapshot_date_is_unique(self):
        self._add_snapshot(0, 100.0)
        with self.assertRaises(sqlite3.IntegrityError):
            self._add_snapshot(0, 200.0)


class BaselineBackfillTestCase(_LedgerTestBase):
    """Açılış çizgisi: defter toplamı her zaman gerçek bakiyeye eşitlenmeli."""

    def _ledger_total(self, entity_type="account"):
        conn = sqlite3.connect(self.db_path)
        total = conn.execute(
            "SELECT COALESCE(SUM(delta),0) FROM balance_events WHERE entity_type = ?",
            (entity_type,)).fetchone()[0]
        conn.close()
        return total

    def test_fresh_database_ledger_matches_real_balance(self):
        conn = sqlite3.connect(self.db_path)
        real = conn.execute("SELECT SUM(balance) FROM accounts").fetchone()[0]
        conn.close()
        self.assertAlmostEqual(self._ledger_total(), real, places=2)

    def test_partial_ledger_is_healed(self):
        """Açılış çizgisi olmayan ama hareketi olan defter onarılmalı.

        Faz 2 öncesinden gelen bir veritabanında bazı hareketler kaydedilmiş
        olabilir; açılış çizgisi, MEVCUT deltalar düşülerek hesaplanmalı ki
        toplam iki kez sayılmasın.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM balance_events")
        # Açılış çizgisi olmayan, yalnızca bir hareketi olan defter kur
        conn.execute(
            "INSERT INTO balance_events (ts, entity_type, entity_id, delta,"
            " resulting_value, source) VALUES (?,?,?,?,?,?)",
            ("2026-01-01 10:00:00", "account", 1, 500.0, None, "transaction"))
        conn.commit()
        real = conn.execute("SELECT SUM(balance) FROM accounts").fetchone()[0]
        conn.close()

        from database.init_db import initialize_database
        initialize_database()

        self.assertAlmostEqual(self._ledger_total(), real, places=2)

    def test_backfill_is_idempotent(self):
        from database.init_db import initialize_database
        before = self._ledger_total()
        initialize_database()
        initialize_database()
        self.assertAlmostEqual(self._ledger_total(), before, places=2)

    def test_baseline_sorts_before_existing_events(self):
        """Açılış çizgisi mevcut olayların ÖNÜNE tarihlenmeli."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM balance_events")
        conn.execute(
            "INSERT INTO balance_events (ts, entity_type, entity_id, delta,"
            " resulting_value, source) VALUES (?,?,?,?,?,?)",
            ("2026-03-05 10:00:00", "account", 1, 100.0, None, "transaction"))
        conn.commit()
        conn.close()

        from database.init_db import initialize_database
        initialize_database()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT ts, source FROM balance_events WHERE entity_id = 1"
            " AND entity_type = 'account' ORDER BY ts").fetchall()
        conn.close()
        self.assertEqual(rows[0][1], "account_opened")
        self.assertTrue(rows[0][0] < "2026-03-05 10:00:00")


class GetBalanceAtTestCase(_LedgerTestBase):

    def setUp(self):
        super().setUp()
        self._clear_ledger()

    def test_replays_from_scratch_without_snapshot(self):
        self._add_event(+1000.0, days_ago=10)
        self._add_event(-250.0, days_ago=5)
        from services.history_service import get_balance_at

        result = get_balance_at(self._day(0))
        self.assertEqual(result["total_balance"], 750.0)
        self.assertEqual(result["basis"], "replay")
        self.assertEqual(result["events_replayed"], 2)

    def test_past_date_excludes_later_events(self):
        """Zaman makinesinin özü: 7 gün önceki bakiye sonraki olayları görmez."""
        self._add_event(+1000.0, days_ago=10)
        self._add_event(-250.0, days_ago=3)
        from services.history_service import get_balance_at

        self.assertEqual(get_balance_at(self._day(7))["total_balance"], 1000.0)
        self.assertEqual(get_balance_at(self._day(0))["total_balance"], 750.0)

    def test_same_day_events_are_included(self):
        """Hedef günün İÇİNDEKİ olaylar dahil olmalı (gün sonu sınırı)."""
        self._add_event(+500.0, days_ago=2, hhmmss="23:58:00")
        from services.history_service import get_balance_at

        self.assertEqual(get_balance_at(self._day(2))["total_balance"], 500.0)

    def test_date_before_ledger_start_returns_unknown(self):
        """Defter başlamadan önceki tarih için 0 DEĞİL, 'bilinmiyor' dönmeli.

        Sıfır döndürmek 'o tarihte paranız yoktu' demek olurdu; oysa uygulama
        o dönemde bakiye hareketi kaydetmiyordu — elimizde veri yok.
        """
        self._add_event(+500.0, days_ago=2)
        from services.history_service import get_balance_at

        result = get_balance_at(self._day(5))
        self.assertEqual(result["basis"], "before_ledger")
        self.assertIsNone(result["total_balance"])
        self.assertEqual(result["ledger_start"], self._day(2))

    def test_snapshot_is_used_as_starting_point(self):
        self._add_snapshot(days_ago=5, total=1000.0)
        self._add_event(+200.0, days_ago=2)
        from services.history_service import get_balance_at

        result = get_balance_at(self._day(0))
        self.assertEqual(result["total_balance"], 1200.0)
        self.assertEqual(result["basis"], "snapshot")
        self.assertEqual(result["snapshot_date"], self._day(5))
        # Snapshot öncesi olaylar tekrar oynatılmamalı
        self.assertEqual(result["events_replayed"], 1)

    def test_snapshot_day_events_are_not_double_counted(self):
        """Snapshot günündeki olaylar snapshot'a zaten dahildir.

        Snapshot yazıldığı ANI temsil ettiği için o günün olaylarını bir de
        replay'e katmak parayı iki kez sayardı; sınır snapshot gününün SONUNDAN
        başlar.
        """
        self._add_event(+1000.0, days_ago=5, hhmmss="09:00:00")
        self._add_snapshot(days_ago=5, total=1000.0)
        from services.history_service import get_balance_at

        result = get_balance_at(self._day(0))
        self.assertEqual(result["total_balance"], 1000.0)
        self.assertEqual(result["events_replayed"], 0)

    def test_savings_goal_events_do_not_move_total_balance(self):
        """Hedef olayları toplam bakiyeyi DEĞİŞTİRMEZ (çift sayım koruması)."""
        self._add_event(-300.0, days_ago=4, entity_type="account")
        self._add_event(+300.0, days_ago=4, entity_type="savings_goal", entity_id=7)
        from services.history_service import get_balance_at

        result = get_balance_at(self._day(0))
        self.assertEqual(result["total_balance"], -300.0)
        self.assertEqual(result["savings_total"], 300.0)

    def test_empty_ledger_returns_zero(self):
        from services.history_service import get_balance_at
        result = get_balance_at(self._day(0))
        self.assertEqual(result["total_balance"], 0.0)
        self.assertEqual(result["events_replayed"], 0)


class DiffBetweenTestCase(_LedgerTestBase):

    def setUp(self):
        super().setUp()
        self._clear_ledger()

    def test_reports_change_and_source_breakdown(self):
        self._add_event(0.0, days_ago=20, source="account_opened")
        self._add_event(+1000.0, days_ago=10, source="transaction")
        self._add_event(-200.0, days_ago=4, source="transaction")
        self._add_event(-300.0, days_ago=3, source="savings_deposit")
        from services.history_service import diff_between

        d = diff_between(self._day(7), self._day(0))
        self.assertEqual(d["balance_from"], 1000.0)
        self.assertEqual(d["balance_to"], 500.0)
        self.assertEqual(d["balance_change"], -500.0)
        self.assertEqual(d["by_source"]["transaction"]["delta"], -200.0)
        self.assertEqual(d["by_source"]["savings_deposit"]["delta"], -300.0)
        self.assertEqual(d["by_source"]["savings_deposit"]["count"], 1)

    def test_argument_order_is_normalized(self):
        """Tarihler ters verilse de aynı sonucu vermeli."""
        self._add_event(0.0, days_ago=20, source="account_opened")
        self._add_event(+100.0, days_ago=5)
        from services.history_service import diff_between

        a = diff_between(self._day(8), self._day(0))
        b = diff_between(self._day(0), self._day(8))
        self.assertEqual(a["balance_change"], b["balance_change"])
        self.assertEqual(a["from"], b["from"])

    def test_savings_change_is_tracked_separately(self):
        # Defter başlangıcını sorgulanan aralığın ÖNÜNE çek ki sonuç
        # "before_ledger" diye kırpılmasın.
        self._add_event(0.0, days_ago=9, source="account_opened")
        self._add_event(-500.0, days_ago=3, entity_type="account")
        self._add_event(+500.0, days_ago=3, entity_type="savings_goal", entity_id=1)
        from services.history_service import diff_between

        d = diff_between(self._day(5), self._day(0))
        self.assertEqual(d["balance_change"], -500.0)
        self.assertEqual(d["savings_change"], 500.0)
        self.assertFalse(d["truncated"])
        # Hedef olayı kaynak kırılımına GİRMEMELİ (aynı hareketin diğer ucu)
        self.assertEqual(d["by_source"]["test"]["count"], 1)

    def test_diff_before_ledger_start_is_marked_truncated(self):
        """Defterden eski bir başlangıç istenirse değişim uydurulmamalı."""
        self._add_event(+700.0, days_ago=2, source="transaction")
        from services.history_service import diff_between

        d = diff_between(self._day(30), self._day(0))
        self.assertTrue(d["truncated"])
        self.assertIsNone(d["balance_change"])
        self.assertEqual(d["ledger_start"], self._day(2))
        # Bildiğimiz hareketler yine raporlanmalı
        self.assertEqual(d["by_source"]["transaction"]["delta"], 700.0)


class SnapshotWritingTestCase(_LedgerTestBase):

    def test_writes_one_snapshot_per_day(self):
        from services.history_service import write_daily_snapshot

        first = write_daily_snapshot()
        second = write_daily_snapshot()

        self.assertIsNotNone(first)
        self.assertIsNone(second, "aynı gün ikinci snapshot yazılmamalı")

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM daily_balance_snapshot").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_snapshot_captures_current_account_total(self):
        from services.history_service import write_daily_snapshot

        # initialize_database üç varsayılan hesap açar: 2500 + 15000 - 3500
        result = write_daily_snapshot()
        self.assertEqual(result["total_balance"], 14000.0)

    def test_force_updates_same_day_snapshot(self):
        from services.history_service import write_daily_snapshot

        write_daily_snapshot()
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE accounts SET balance = 999 WHERE id = 1")
        conn.commit()
        conn.close()

        updated = write_daily_snapshot(force=True)
        self.assertIsNotNone(updated)
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT COUNT(*) FROM daily_balance_snapshot").fetchone()[0]
        total = conn.execute("SELECT total_balance FROM daily_balance_snapshot").fetchone()[0]
        conn.close()
        self.assertEqual(rows, 1)
        self.assertEqual(total, 999 + 15000 - 3500)


class RealWriteSitesTestCase(_LedgerTestBase):
    """Sentetik değil GERÇEK üretim kodu çağrılarının defteri beslediğini doğrular."""

    def test_transaction_writes_ledger_entry(self):
        """adjust_account_balance (defter 1/6) — işlem eklendiğinde kayıt düşmeli."""
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            amount=250.0, transaction_type="expense",
            category="Süpermarket", description="Market", account_id=1,
        )
        events = [e for e in self._events() if e["source"] == "transaction"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["delta"], -250.0)
        self.assertEqual(events[0]["entity_type"], "account")
        self.assertEqual(events[0]["resulting_value"], self._balance(1))

    def test_savings_deposit_writes_both_sides(self):
        """deposit_to_goal (defter 2/6) — hesap ve hedef olayları birlikte."""
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Tatil", 5000.0)
        SavingsService.deposit_to_goal(goal_id, 1000.0, account_id=1)

        events = [e for e in self._events() if e["source"] == "savings_deposit"]
        self.assertEqual(len(events), 2)
        by_type = {e["entity_type"]: e for e in events}
        self.assertEqual(by_type["account"]["delta"], -1000.0)
        self.assertEqual(by_type["savings_goal"]["delta"], 1000.0)
        self.assertEqual(by_type["savings_goal"]["entity_id"], goal_id)

    def test_savings_withdraw_writes_both_sides(self):
        """withdraw_from_goal (defter 3/6)."""
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Tatil", 5000.0)
        SavingsService.deposit_to_goal(goal_id, 1000.0, account_id=1)
        SavingsService.withdraw_from_goal(goal_id, 400.0, account_id=1)

        events = [e for e in self._events() if e["source"] == "savings_withdraw"]
        self.assertEqual(len(events), 2)
        by_type = {e["entity_type"]: e for e in events}
        self.assertEqual(by_type["account"]["delta"], 400.0)
        self.assertEqual(by_type["savings_goal"]["delta"], -400.0)

    def test_delete_goal_refund_is_recorded(self):
        """delete_goal (defter 4/6) — iade hesaba, hedef 0'a kapanmalı."""
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Tatil", 5000.0)
        SavingsService.deposit_to_goal(goal_id, 800.0, account_id=1)
        SavingsService.delete_goal(goal_id, account_id=1)

        events = [e for e in self._events() if e["source"] == "savings_goal_deleted"]
        by_type = {e["entity_type"]: e for e in events}
        self.assertEqual(by_type["account"]["delta"], 800.0)
        self.assertEqual(by_type["savings_goal"]["delta"], -800.0)
        self.assertEqual(by_type["savings_goal"]["resulting_value"], 0.0)

    def test_factory_reset_records_one_event_per_account(self):
        """factory_reset (defter 5/6) — toplu sıfırlama hesap başına olay."""
        from database.db import ACCOUNT, record_balance_event

        # admin_screen.factory_reset gövdesindeki defter mantığının aynısı;
        # Kivy ekranını başlatmadan davranışı doğrulamak için burada tekrarlanır.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, balance FROM accounts")
        previous = [(r["id"], r["balance"] or 0.0) for r in cursor.fetchall()]
        cursor.execute("UPDATE accounts SET balance = 0")
        for account_id, old in previous:
            record_balance_event(cursor, ACCOUNT, account_id, -old, 0.0,
                                 "admin_factory_reset")
        conn.commit()
        conn.close()

        events = [e for e in self._events() if e["source"] == "admin_factory_reset"]
        self.assertEqual(len(events), 3, "üç varsayılan hesap için üç olay")
        self.assertEqual(sum(e["delta"] for e in events), -14000.0)
        self.assertTrue(all(e["resulting_value"] == 0.0 for e in events))

    def test_ledger_matches_real_balance_after_mixed_flow(self):
        """Defterin replay'i gerçek accounts.balance ile birebir tutmalı.

        Bu, tüm yazma noktalarının kapsandığının asıl kanıtı: kaçırılan bir
        nokta olsaydı iki taraf ayrışırdı.
        """
        from services.savings_service import SavingsService
        from services.transaction_service import TransactionService
        from services.history_service import get_balance_at

        TransactionService.add_transaction(
            amount=5000.0, transaction_type="income",
            category="Maaş", description="Maas", account_id=1)
        TransactionService.add_transaction(
            amount=1200.0, transaction_type="expense",
            category="Ev Kirası", description="Kira", account_id=1)
        goal_id = SavingsService.create_goal("Acil Durum", 10000.0)
        SavingsService.deposit_to_goal(goal_id, 2000.0, account_id=1)
        SavingsService.withdraw_from_goal(goal_id, 500.0, account_id=1)

        conn = sqlite3.connect(self.db_path)
        real_total = conn.execute("SELECT SUM(balance) FROM accounts").fetchone()[0]
        real_goals = conn.execute("SELECT SUM(current_amount) FROM savings_goals").fetchone()[0]
        conn.close()

        replayed = get_balance_at(datetime.now().strftime("%Y-%m-%d"))
        self.assertAlmostEqual(replayed["total_balance"], real_total, places=2)
        self.assertAlmostEqual(replayed["savings_total"], real_goals, places=2)

    def test_failed_deposit_leaves_no_ledger_entry(self):
        """Atomiklik: yetersiz bakiyede UPDATE de defter de geri alınmalı."""
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Büyük Hedef", 999999.0)
        before = len(self._events())

        with self.assertRaises(ValueError):
            SavingsService.deposit_to_goal(goal_id, 10_000_000.0, account_id=1)

        self.assertEqual(len(self._events()), before,
                         "başarısız işlem defterde iz bırakmamalı")


if __name__ == "__main__":
    unittest.main()
