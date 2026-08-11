"""Kredi kartı / abonelik interceptor mantığı.

İşlem kaydedilirken abonelik gibi görünen giderler normal defter kaydının
YANINDA "Aktif Aboneliklerim" radarına da yazılır. Bu paket iki sözleşmeyi
kilitler:
  * Abonelik sinyali olan gider radara düşer, olmayan DÜŞMEZ.
  * Radar kaydı yardımcı bir kolaylıktır: orada bir sorun çıksa bile
    kullanıcının gerçek harcaması kaydedilmiş kalır.

Marka kataloğu gerçek servis adlarını içerir; dar kural testleri gerektiğinde
listeyi geçici olarak yamalayarak tek bir sinyali izole eder.
"""
import os
import tempfile
import unittest
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class SubscriptionDetectionTest(unittest.TestCase):
    """`looks_like_subscription` saf kuralları — DB gerektirmez."""

    def test_subscription_category_is_detected(self):
        from services.recurring_service import looks_like_subscription
        self.assertTrue(looks_like_subscription("Dijital Abonelik"))
        self.assertTrue(looks_like_subscription("Dijital Platformlar"))

    def test_ordinary_category_is_not_detected(self):
        from services.recurring_service import looks_like_subscription
        for category in ("Süpermarket", "Akaryakıt", "Kira", ""):
            with self.subTest(category=category):
                self.assertFalse(looks_like_subscription(category))

    def test_credit_card_alone_is_not_enough(self):
        """Karttan geçen her market alışverişi abonelik sayılırsa radar çöp olur."""
        from services.recurring_service import looks_like_subscription
        self.assertFalse(looks_like_subscription(
            "Süpermarket", "Haftalık alışveriş", is_credit_card=True))

    def test_known_brand_in_description_is_detected(self):
        from services import recurring_service
        with mock.patch.object(recurring_service, "KNOWN_BRANDS", ["netflix"]):
            self.assertTrue(recurring_service.looks_like_subscription(
                "Ekstra Gider", "NETFLIX.COM 12/2026"))

    def test_proton_products_are_detected_as_subscriptions(self):
        from services.recurring_service import looks_like_subscription
        for description in (
            "Proton VPN Plus", "ProtonMail", "Proton Pass Plus",
            "Proton Drive", "Proton Unlimited", "Proton",
        ):
            with self.subTest(description=description):
                self.assertTrue(looks_like_subscription(
                    "Ekstra Gider", description,
                ))

    def test_telecom_bills_are_detected_as_subscriptions(self):
        from services.recurring_service import looks_like_subscription
        for description in (
            "Türk Telekom mobil faturası",
            "TTNET internet",
            "Vodafone Red tarifesi",
            "Vodafone Net",
            "Turkcell Platinum",
            "Turkcell Superonline",
        ):
            with self.subTest(description=description):
                self.assertTrue(looks_like_subscription(
                    "Faturalar", description,
                ))

    def test_extended_catalog_products_are_detected_as_subscriptions(self):
        from services.recurring_service import looks_like_subscription
        descriptions = (
            "Paramount Plus", "Peacock Premium", "Crunchyroll", "Tidal",
            "SoundCloud Go", "EA Play", "Ubisoft Plus", "Slack Pro",
            "Zoom Pro", "LinkedIn Premium", "Meta Verified", "Storytel",
            "Audible Plus", "Kindle Unlimited", "Blinkist", "Figma",
            "JetBrains", "1Password", "LastPass", "Claude Pro",
            "Gemini Advanced", "Udemy", "Coursera Plus", "Duolingo Super",
            "Skillshare", "MACFit", "Club Sporium", "Strava",
            "Headspace", "Patreon", "Wikipedia", "tabii",
        )
        for description in descriptions:
            with self.subTest(description=description):
                self.assertTrue(looks_like_subscription(
                    "Ekstra Gider", description,
                ))

    def test_unknown_brand_stays_undetected(self):
        from services import recurring_service
        with mock.patch.object(recurring_service, "KNOWN_BRANDS", ["netflix"]):
            self.assertFalse(recurring_service.looks_like_subscription(
                "Ekstra Gider", "Mahalle bakkalı"))


class InterceptorWiringTest(AccountFixtureMixin, unittest.TestCase):
    """add_transaction -> radar akışı."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

        from services.account_service import CREDIT_CARD
        self.checking_id = self.create_test_account(
            name="Vadesiz", balance=20000.0)
        self.card_id = self.create_test_account(
            name="Kart", balance=0.0, account_type=CREDIT_CARD,
            credit_limit=20000,
        )

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add(self, account_id, category, description, amount=149.99, **kwargs):
        from services.transaction_service import TransactionService
        TransactionService.add_transaction(
            account_id=account_id, amount=amount, transaction_type="expense",
            category=category, description=description,
            enforce_credit_limit=False, **kwargs,
        )

    def _radar(self):
        from database.db import get_active_recurring_payments
        return get_active_recurring_payments()

    def _tx_count(self):
        from database.db import get_connection
        conn = get_connection()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM transactions").fetchone()[0]
        finally:
            conn.close()

    # ─── Pozitif yol ─────────────────────────────────────────────────────────

    def test_card_subscription_lands_in_radar(self):
        self._add(self.card_id, "Dijital Platformlar", "Netflix")

        radar = self._radar()
        self.assertEqual(len(radar), 1)
        self.assertEqual(radar[0]["name"], "Netflix")
        self.assertAlmostEqual(radar[0]["amount"], 149.99, places=2)
        self.assertEqual(radar[0]["account_id"], self.card_id)

    def test_transaction_is_still_written_alongside_radar(self):
        """Radara yazmak defter kaydının YERİNE geçmez."""
        self._add(self.card_id, "Dijital Platformlar", "Spotify")
        self.assertEqual(self._tx_count(), 1)
        self.assertEqual(len(self._radar()), 1)

    def test_detection_is_idempotent_across_months(self):
        """Kullanıcı aynı aboneliği elle tekrar girse radar tek kayıt tutar."""
        self._add(self.card_id, "Dijital Platformlar", "Netflix")
        self._add(self.card_id, "Dijital Platformlar", "Netflix")

        self.assertEqual(len(self._radar()), 1)
        self.assertEqual(self._tx_count(), 2, "Her harcama deftere yazılmalı")

    # ─── Negatif yol ─────────────────────────────────────────────────────────

    def test_ordinary_card_spending_is_ignored(self):
        self._add(self.card_id, "Süpermarket", "Haftalık alışveriş", amount=430.0)
        self.assertEqual(self._radar(), [])
        self.assertEqual(self._tx_count(), 1)

    def test_income_is_never_intercepted(self):
        from services.transaction_service import TransactionService
        TransactionService.add_transaction(
            account_id=self.checking_id, amount=5000.0,
            transaction_type="income", category="Dijital Platformlar",
            description="İade", enforce_credit_limit=False,
        )
        self.assertEqual(self._radar(), [])

    def test_flag_disables_interception(self):
        """Kullanıcı aboneliği formda kendisi kurduğunda çift kayıt olmamalı."""
        self._add(self.card_id, "Dijital Platformlar", "Netflix",
                  detect_subscription=False)
        self.assertEqual(self._radar(), [])
        self.assertEqual(self._tx_count(), 1)

    def test_radar_failure_does_not_lose_the_transaction(self):
        """Radar kaydı patlasa bile gerçek harcama kaydedilmiş kalmalı."""
        with mock.patch(
            "services.recurring_service.register_subscription_from_transaction",
            side_effect=RuntimeError("radar bozuk"),
        ):
            self._add(self.card_id, "Dijital Platformlar", "Netflix")

        self.assertEqual(self._tx_count(), 1)
        self.assertEqual(self._radar(), [])

    def test_checking_account_is_not_auto_intercepted(self):
        """Otomatik interceptor yalnız kredi kartı harcamalarını kapsar."""
        self._add(self.checking_id, "Dijital Abonelik", "Mubi", amount=79.0)
        self.assertEqual(self._radar(), [])
        self.assertEqual(self._tx_count(), 1)


if __name__ == "__main__":
    unittest.main()
