"""Faz 1 içgörü motorunun testleri (abonelik radarı, anomali, sağlık skoru).

Testler geçici bir veritabanı dosyası üzerinde çalışır — kullanıcının gerçek
finance.db'sine dokunulmaz (tests/test_account_service.py ile aynı izolasyon
deseni: database.db.DB_NAME patch'lenir, get_connection çağrı anında okur).

NOT: tests/test_metrics.py bir unittest DEĞİL, assertion'ı olmayan bir yazdırma
script'i; oradaki "çek → decrypt et → hesapla" akışı örnek alındı ama test
iskeleti olarak test_account_service.py izlendi.
"""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class InsightsServiceTestCase(unittest.TestCase):

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

    # ─── Yardımcılar ─────────────────────────────────────────────────────────

    def _add_tx(self, amount, tx_type, category, description, days_ago):
        """Şifreli bir işlem satırı yazar (tutar + açıklama encrypt edilir)."""
        from database.db import SECRET_KEY
        from utils.crypto import encrypt

        when = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO transactions"
            " (account_id, amount, type, category, description, transaction_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (1, encrypt(str(amount), SECRET_KEY), tx_type, category,
             encrypt(str(description), SECRET_KEY), when),
        )
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return transaction_id

    def _add_monthly_series(self, name, amount, category="Dijital Platformlar",
                            count=6, jitter=0.0):
        """Aylık tekrarlayan bir gider serisi üretir (30 gün aralıkla)."""
        for i in range(count):
            value = amount + (jitter if i % 2 else -jitter)
            self._add_tx(value, "expense", category, name, days_ago=30 * i + 1)

    # ─── 1. Abonelik radarı ──────────────────────────────────────────────────

    def test_detects_monthly_subscription(self):
        """Sabit tutarlı, 30 gün aralıklı gider abonelik adayı olmalı."""
        from services.insights_service import detect_recurring_candidates

        self._add_monthly_series("Netflix Abonelik", 149.90)
        candidates = detect_recurring_candidates(lookback_days=200)

        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertIn("netflix", c["name"].lower())
        self.assertEqual(c["frequency"], "monthly")
        self.assertAlmostEqual(c["average_amount"], 149.90, places=2)
        self.assertEqual(c["occurrences"], 6)

    def test_amount_tolerance_allows_small_drift(self):
        """%10 tolerans içindeki zam adayı elemez (kur/zam oynaması normal)."""
        from services.insights_service import detect_recurring_candidates

        # 200 +/- 8  => sapma %4, tolerans içinde
        self._add_monthly_series("Spotify", 200.0, jitter=8.0)
        self.assertEqual(len(detect_recurring_candidates(lookback_days=200)), 1)

    def test_wildly_varying_amounts_are_not_candidates(self):
        """Tutarı savrulan market alışverişi abonelik sayılmamalı."""
        from services.insights_service import detect_recurring_candidates

        for i, amount in enumerate([100.0, 850.0, 320.0, 1500.0, 210.0, 640.0]):
            self._add_tx(amount, "expense", "Süpermarket", "Market Alisveris",
                         days_ago=30 * i + 1)
        self.assertEqual(detect_recurring_candidates(lookback_days=200), [])

    def test_irregular_intervals_are_not_candidates(self):
        """Tutar sabit olsa bile aralık düzensizse aday değildir."""
        from services.insights_service import detect_recurring_candidates

        for days in (1, 4, 40, 44, 130, 133):
            self._add_tx(99.0, "expense", "Hobiler", "Rastgele Odeme", days_ago=days)
        self.assertEqual(detect_recurring_candidates(lookback_days=200), [])

    def test_too_few_occurrences_is_not_a_candidate(self):
        """İki kez görülen bir gider henüz kalıp değildir."""
        from services.insights_service import detect_recurring_candidates

        self._add_monthly_series("Dergi", 50.0, count=2)
        self.assertEqual(detect_recurring_candidates(lookback_days=200), [])

    def test_already_tracked_recurring_payment_is_excluded(self):
        """recurring_payments'ta aktif olan abonelik tekrar önerilmemeli."""
        from database.db import SECRET_KEY
        from utils.crypto import encrypt
        from services.insights_service import detect_recurring_candidates

        self._add_monthly_series("Netflix Abonelik", 149.90)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO recurring_payments"
            " (name, amount, category, frequency, next_due_date, is_active)"
            " VALUES (?, ?, ?, 'monthly', ?, 1)",
            (encrypt("Netflix", SECRET_KEY), encrypt("149.90", SECRET_KEY),
             "Dijital Platformlar", datetime.now().strftime("%Y-%m-%d")),
        )
        conn.commit()
        conn.close()

        self.assertEqual(detect_recurring_candidates(lookback_days=200), [])

    def test_dismissed_candidate_is_not_suggested_again(self):
        """Kullanıcı reddettiyse radar bir daha önermemeli."""
        from services.insights_service import (
            detect_recurring_candidates, dismiss_recurring_candidate,
        )

        self._add_monthly_series("Netflix Abonelik", 149.90)
        candidates = detect_recurring_candidates(lookback_days=200)
        self.assertEqual(len(candidates), 1)

        dismiss_recurring_candidate(candidates[0]["key"])
        self.assertEqual(detect_recurring_candidates(lookback_days=200), [])

    def test_monthly_cost_normalizes_weekly_series(self):
        """Haftalık abonelik aylık maliyete normalize edilerek raporlanmalı."""
        from services.insights_service import detect_recurring_candidates

        for i in range(8):
            self._add_tx(25.0, "expense", "Dışarıda Yemek", "Haftalik Kahve",
                         days_ago=7 * i + 1)
        candidates = detect_recurring_candidates(lookback_days=200)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["frequency"], "weekly")
        self.assertTrue(candidates[0]["can_track"])
        # 25 TL x (30/7) ≈ 107 TL/ay
        self.assertAlmostEqual(candidates[0]["monthly_cost"], 25.0 * 30 / 7, delta=1.0)

    def test_all_detected_frequencies_can_be_tracked(self):
        """Radarın tanıdığı düzenli periyotların tümü ödeme motoruna aktarılabilir."""
        from services.insights_service import detect_recurring_candidates

        for name, interval, count in (
            ("Haftalik", 7, 5),
            ("Iki Haftalik", 14, 5),
            ("Aylik", 30, 5),
            ("Uc Aylik", 90, 3),
        ):
            with self.subTest(frequency=name):
                conn = sqlite3.connect(self.db_path)
                conn.execute("DELETE FROM transactions")
                conn.commit()
                conn.close()
                for i in range(count):
                    self._add_tx(
                        100.0, "expense", "Dijital Platformlar", name,
                        days_ago=interval * i + 1,
                    )
                candidates = detect_recurring_candidates(lookback_days=400)
                self.assertEqual(len(candidates), 1)
                self.assertTrue(candidates[0]["can_track"])

    def test_advance_due_date_supports_every_frequency(self):
        from database.db import _advance_due_date

        cases = (
            ("2026-01-01", "weekly", "2026-01-08"),
            ("2026-01-01", "biweekly", "2026-01-15"),
            ("2026-01-31", "monthly", "2026-02-28"),
            ("2026-01-31", "quarterly", "2026-04-30"),
            ("2024-02-29", "yearly", "2025-02-28"),
        )
        for start, frequency, expected in cases:
            with self.subTest(frequency=frequency):
                self.assertEqual(_advance_due_date(start, frequency), expected)

    def test_advance_due_date_rejects_unknown_frequency(self):
        from database.db import _advance_due_date

        with self.assertRaises(ValueError):
            _advance_due_date("2026-01-01", "sometimes")

    def test_processing_quarterly_payment_advances_due_date(self):
        """Gerçek ödeme yazımı üç aylık vadeyi aynı işlemde ilerletmeli."""
        from database.db import (
            get_active_recurring_payments, insert_recurring_payment,
            process_due_recurring_payment,
        )

        insert_recurring_payment(
            "Uc Aylik Test", 100.0, "Dijital Platformlar", "quarterly",
            "2026-01-31", auto_deduct=0,
        )
        payment = get_active_recurring_payments()[0]
        process_due_recurring_payment(payment)

        conn = sqlite3.connect(self.db_path)
        due_date = conn.execute(
            "SELECT next_due_date FROM recurring_payments WHERE id = ?",
            (payment["id"],),
        ).fetchone()[0]
        transaction_count = conn.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(due_date, "2026-04-30")
        self.assertEqual(transaction_count, 1)

    def test_normalize_name_collapses_noise(self):
        """Farklı yazımlar aynı adaya düşmeli."""
        from services.insights_service import normalize_name

        self.assertEqual(normalize_name("NETFLIX.COM 12/2026"), normalize_name("netflix com"))
        self.assertEqual(normalize_name("Spotify (Otomatik)"), "spotify")

    # ─── 2. Anomali tespiti ──────────────────────────────────────────────────

    def test_detects_outlier_expense(self):
        """Kategori ortalamasının çok üstündeki işlem anomali olmalı."""
        from services.insights_service import detect_anomalies

        for i in range(10):
            self._add_tx(100.0 + i, "expense", "Süpermarket", f"Market {i}", days_ago=i + 1)
        self._add_tx(5000.0, "expense", "Süpermarket", "Buyuk Alisveris", days_ago=2)

        anomalies = detect_anomalies(lookback_days=60, z_threshold=2.0)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["amount"], 5000.0)
        self.assertEqual(anomalies[0]["category"], "Süpermarket")
        self.assertGreater(anomalies[0]["z_score"], 2.0)

    def test_uniform_spending_has_no_anomaly(self):
        """Düzgün dağılmış harcamada anomali olmamalı."""
        from services.insights_service import detect_anomalies

        for i in range(10):
            self._add_tx(100.0, "expense", "Süpermarket", f"Market {i}", days_ago=i + 1)
        self.assertEqual(detect_anomalies(lookback_days=60), [])

    def test_cheap_outlier_is_not_flagged(self):
        """Normalden UCUZ işlem uyarı değildir — yalnızca üste sapma işaretlenir."""
        from services.insights_service import detect_anomalies

        for i in range(10):
            self._add_tx(1000.0, "expense", "Kıyafet", f"Alisveris {i}", days_ago=i + 1)
        self._add_tx(5.0, "expense", "Kıyafet", "Ucuz Corap", days_ago=2)

        self.assertEqual(detect_anomalies(lookback_days=60, z_threshold=2.0), [])

    def test_thin_category_is_skipped(self):
        """3'ten az işlemi olan kategoride sapma hesaplanmamalı."""
        from services.insights_service import detect_anomalies

        self._add_tx(10.0, "expense", "Hobiler", "Kucuk", days_ago=1)
        self._add_tx(9000.0, "expense", "Hobiler", "Devasa", days_ago=2)
        self.assertEqual(detect_anomalies(lookback_days=60), [])

    def test_z_threshold_is_respected(self):
        """Eşik yükseltilince sınırdaki anomali elenmeli."""
        from services.insights_service import detect_anomalies

        for i in range(10):
            self._add_tx(100.0 + i, "expense", "Süpermarket", f"M{i}", days_ago=i + 1)
        self._add_tx(5000.0, "expense", "Süpermarket", "Buyuk", days_ago=2)

        self.assertEqual(len(detect_anomalies(lookback_days=60, z_threshold=2.0)), 1)
        self.assertEqual(detect_anomalies(lookback_days=60, z_threshold=99.0), [])

    def test_dismissed_anomaly_is_not_returned_again(self):
        """Görüldü denilen işlem sonraki anomali taramalarından elenmeli."""
        from services.insights_service import detect_anomalies, dismiss_anomaly

        for i in range(10):
            self._add_tx(
                100.0 + i, "expense", "Süpermarket", f"Market {i}",
                days_ago=i + 1,
            )
        anomaly_id = self._add_tx(
            5000.0, "expense", "Süpermarket", "Buyuk Alisveris", days_ago=2,
        )

        self.assertEqual(len(detect_anomalies(lookback_days=60)), 1)
        dismiss_anomaly(anomaly_id)
        self.assertEqual(detect_anomalies(lookback_days=60), [])

    def test_dismiss_anomaly_is_idempotent(self):
        """Aynı karttan yinelenen olay iki dismissal satırı üretmemeli."""
        from services.insights_service import dismiss_anomaly

        transaction_id = self._add_tx(
            5000.0, "expense", "Süpermarket", "Buyuk", days_ago=1,
        )
        dismiss_anomaly(transaction_id)
        dismiss_anomaly(transaction_id)

        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM anomaly_dismissals WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    # ─── 3. Finansal sağlık skoru ────────────────────────────────────────────

    def test_healthy_profile_scores_higher_than_unhealthy(self):
        """Yüksek tasarruf + borçsuz profil, açık veren profilden iyi olmalı."""
        from services.insights_service import compute_financial_health_score

        # Sağlıklı: 10.000 gelir, 5.000 gider (istikrarlı), borç yok
        for month in range(3):
            self._add_tx(10000.0, "income", "Maaş", "Maas", days_ago=30 * month + 5)
            self._add_tx(5000.0, "expense", "Ev Kirası", "Kira", days_ago=30 * month + 6)
        healthy = compute_financial_health_score(lookback_days=90, persist=False)

        # Aynı DB'yi temizleyip açık veren profili kur
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM transactions")
        conn.commit()
        conn.close()

        for month in range(3):
            self._add_tx(10000.0, "income", "Maaş", "Maas", days_ago=30 * month + 5)
            self._add_tx(11000.0, "expense", "Ev Kirası", "Kira", days_ago=30 * month + 6)
        unhealthy = compute_financial_health_score(lookback_days=90, persist=False)

        self.assertGreater(healthy["score"], unhealthy["score"])
        self.assertGreater(healthy["breakdown"]["savings_rate"], 0)
        self.assertLess(unhealthy["breakdown"]["savings_rate"], 0)

    def test_score_is_bounded_0_100(self):
        """Uç girdilerde bile skor 0-100 aralığında kalmalı."""
        from services.insights_service import compute_financial_health_score

        # Aşırı açık: gelir 1, gider 100.000
        self._add_tx(1.0, "income", "Maaş", "Maas", days_ago=5)
        for i in range(4):
            self._add_tx(25000.0, "expense", "Kıyafet", f"Harcama {i}", days_ago=10 + i)

        result = compute_financial_health_score(lookback_days=90, persist=False)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 100.0)

    def test_debt_lowers_score(self):
        """Aylık borç taksiti skoru düşürmeli."""
        from database.db import SECRET_KEY
        from utils.crypto import encrypt
        from services.insights_service import compute_financial_health_score

        for month in range(3):
            self._add_tx(10000.0, "income", "Maaş", "Maas", days_ago=30 * month + 5)
            self._add_tx(5000.0, "expense", "Ev Kirası", "Kira", days_ago=30 * month + 6)
        before = compute_financial_health_score(lookback_days=90, persist=False)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO active_debts"
            " (debt_name, total_amount, monthly_payment, total_installments,"
            "  paid_installments, is_active) VALUES (?, ?, ?, 24, 0, 1)",
            (encrypt("Araba Kredisi", SECRET_KEY), encrypt("96000", SECRET_KEY),
             encrypt("4000", SECRET_KEY)),
        )
        conn.commit()
        conn.close()

        after = compute_financial_health_score(lookback_days=90, persist=False)
        self.assertLess(after["score"], before["score"])
        self.assertGreater(after["breakdown"]["debt_ratio"], 0)

    def test_no_income_does_not_crash(self):
        """Gelir yokken oran tanımsız — skor üretilmeli, çökmemeli."""
        from services.insights_service import compute_financial_health_score

        self._add_tx(500.0, "expense", "Süpermarket", "Market", days_ago=3)
        result = compute_financial_health_score(lookback_days=90, persist=False)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 100.0)

    def test_empty_database_returns_insufficient_data(self):
        """Hiç işlem yokken nötr 50 yerine açık veri-yok durumu dönmeli."""
        from services.insights_service import (
            compute_financial_health_score, detect_anomalies,
            detect_recurring_candidates,
        )

        self.assertEqual(detect_recurring_candidates(), [])
        self.assertEqual(detect_anomalies(), [])
        result = compute_financial_health_score(persist=False)
        self.assertTrue(result["insufficient_data"])
        self.assertIsNone(result["score"])
        self.assertEqual(result["breakdown"], {})

    def test_insufficient_score_is_not_persisted(self):
        """Veri yok sonucu persist=True olsa bile geçmişe yazılmamalı."""
        from services.insights_service import (
            compute_financial_health_score, get_health_history,
        )

        result = compute_financial_health_score(persist=True)

        self.assertTrue(result["insufficient_data"])
        self.assertEqual(get_health_history(), [])

    def test_real_transactions_still_produce_a_numeric_score(self):
        """Az ama gerçek veri, veri-yok durumuyla karıştırılmamalı."""
        from services.insights_service import compute_financial_health_score

        self._add_tx(1000.0, "income", "Maaş", "Maas", days_ago=2)
        self._add_tx(800.0, "expense", "Süpermarket", "Market", days_ago=1)
        result = compute_financial_health_score(persist=False)

        self.assertFalse(result["insufficient_data"])
        self.assertIsInstance(result["score"], float)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 100.0)

    # ─── 4. Kalıcılık ────────────────────────────────────────────────────────

    def test_score_is_persisted_with_timestamp(self):
        """persist=True skoru breakdown'ıyla birlikte tabloya yazmalı."""
        from services.insights_service import (
            compute_financial_health_score, get_health_history,
        )

        for month in range(3):
            self._add_tx(8000.0, "income", "Maaş", "Maas", days_ago=30 * month + 5)
            self._add_tx(4000.0, "expense", "Ev Kirası", "Kira", days_ago=30 * month + 6)

        result = compute_financial_health_score(lookback_days=90, persist=True)
        history = get_health_history()

        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0]["score"], result["score"], places=1)
        self.assertIn("savings_rate", history[0]["breakdown"])
        self.assertTrue(history[0]["date"])

    def test_score_is_updated_instead_of_duplicated_on_same_day(self):
        """Dashboard yenilemeleri aynı gün için yalnız son skoru bırakmalı."""
        from services.insights_service import save_health_score, get_health_history

        save_health_score(
            40.0, {"savings_rate": 0.10}, "2026-07-23 08:00:00",
        )
        save_health_score(
            72.0, {"savings_rate": 0.25}, "2026-07-23 18:30:00",
        )

        history = get_health_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["score"], 72.0)
        self.assertEqual(history[0]["date"], "2026-07-23 18:30:00")
        self.assertEqual(history[0]["breakdown"]["savings_rate"], 0.25)

    def test_history_returns_newest_first(self):
        """Geçmiş en yeniden eskiye sıralı dönmeli."""
        from services.insights_service import get_health_history, save_health_score

        save_health_score(10.0, {"savings_rate": 0.1}, "2026-01-01 00:00:00")
        save_health_score(90.0, {"savings_rate": 0.9}, "2026-06-01 00:00:00")

        history = get_health_history()
        self.assertEqual([h["score"] for h in history], [90.0, 10.0])

    def test_health_tables_exist_after_init(self):
        """Migration guard iki yeni tabloyu da kurmalı."""
        conn = sqlite3.connect(self.db_path)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_health_history)")}
        conn.close()

        self.assertIn("financial_health_history", names)
        self.assertIn("recurring_candidate_dismissals", names)
        self.assertEqual(cols, {"id", "date", "score", "breakdown_json"})

    def test_score_label_boundaries(self):
        from services.insights_service import score_label

        self.assertEqual(score_label(95), "Çok İyi")
        self.assertEqual(score_label(60), "İyi")
        self.assertEqual(score_label(40), "Orta")
        self.assertEqual(score_label(20), "Zayıf")
        self.assertEqual(score_label(0), "Kritik")


if __name__ == "__main__":
    unittest.main()
