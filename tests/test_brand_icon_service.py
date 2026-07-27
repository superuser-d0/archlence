import os
import tempfile
import unittest
from unittest import mock

from services import brand_icon_service


class BrandIconServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_patch = mock.patch.object(
            brand_icon_service,
            "BRAND_ICON_CACHE_DIR",
            self.temp_dir.name,
        )
        self.cache_patch.start()

    def tearDown(self):
        self.cache_patch.stop()
        self.temp_dir.cleanup()

    def test_classifies_known_brand_without_guessing_unknown_text(self):
        key, url = brand_icon_service.classify_brand(
            "Aylık NETFLIX.COM üyelik ödemesi"
        )
        self.assertEqual(key, "netflix")
        # logo.clearbit.com artık hiçbir DNS sunucusundan çözülmüyor (Clearbit
        # ücretsiz logo API'sini kapattı) — google favicon servisine geçirildi.
        self.assertNotIn("clearbit.com", url)
        self.assertIn("google.com", url)
        self.assertIn("domain=netflix.com", url)
        self.assertEqual(
            brand_icon_service.classify_brand("Mahalle marketi"),
            (None, None),
        )

    def test_cached_path_never_makes_network_request(self):
        path = os.path.join(self.temp_dir.name, "spotify.png")
        with open(path, "wb") as image:
            image.write(b"png")

        with mock.patch("requests.get") as request:
            resolved = brand_icon_service.resolve_cached_brand_icon_path(
                "Spotify Premium"
            )

        self.assertEqual(resolved, path)
        request.assert_not_called()

    def test_successful_png_download_is_cached(self):
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=b"\x89PNG\r\n\x1a\nfake",
        )
        with mock.patch("requests.get", return_value=response) as request:
            self.assertTrue(
                brand_icon_service.fetch_and_cache_brand_icon("Disney+")
            )

        destination = os.path.join(self.temp_dir.name, "disney-plus.png")
        self.assertTrue(os.path.exists(destination))
        self.assertEqual(
            brand_icon_service.resolve_cached_brand_icon_path("Disney Plus"),
            destination,
        )
        request.assert_called_once()

    def test_network_and_invalid_content_fail_silently(self):
        with mock.patch("requests.get", side_effect=OSError("offline")):
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Netflix")
            )

        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"not an image",
        )
        with mock.patch("requests.get", return_value=response):
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Spotify")
            )

    def test_cache_keys_are_unique(self):
        """İki farklı alias grubu aynı cache_key'e yazarsa biri diğerinin
        önbelleğini sessizce ezer — dosya sistemi seviyesinde fark edilmez."""
        keys = [cache_key for _, cache_key, _ in brand_icon_service._BRANDS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_newly_added_brands_across_categories(self):
        """Video/müzik/oyun/bulut/üretkenlik/VPN kategorilerinden birer
        örnek — genişletilen listenin gerçekten eşleştiğini doğrular."""
        cases = {
            "Twitch aboneliği": "twitch",
            "Xbox Game Pass Ultimate": "xbox-game-pass",
            "PlayStation Plus": "playstation-plus",
            "Google One 2TB": "google-one",
            "ChatGPT Plus": "chatgpt",
            "GitHub Copilot": "github",
            "NordVPN yıllık": "nordvpn",
        }
        for text, expected_key in cases.items():
            with self.subTest(text=text):
                key, url = brand_icon_service.classify_brand(text)
                self.assertEqual(key, expected_key)
                self.assertIn("google.com", url)

    def test_generic_amazon_does_not_shadow_prime_video(self):
        """Genel 'amazon' girdisi listenin SONUNDA durmalı — 'amazon prime' /
        'prime video' gibi daha özgül takma adlar önce sınanmalı, yoksa Prime
        Video hiçbir zaman kendi ikonuna ulaşamaz."""
        self.assertEqual(
            brand_icon_service.classify_brand("Amazon Prime yıllık üyelik")[0],
            "prime-video",
        )
        self.assertEqual(
            brand_icon_service.classify_brand("Amazon Music aboneliği")[0],
            "amazon",
        )

    def test_instagram_and_meta_verified_resolve_to_same_icon(self):
        """Kullanıcı çoğunlukla yalnızca 'Instagram' yazar; 'Meta Verified'
        gerçek ürün adı da aynı ikona düşmeli — ikisi de instagram.com'un
        favicon'unu kullanır (Meta'nın genel logosundan daha tanınır)."""
        self.assertEqual(
            brand_icon_service.classify_brand("Instagram")[0], "instagram",
        )
        self.assertEqual(
            brand_icon_service.classify_brand("Meta Verified")[0], "instagram",
        )
        self.assertIn(
            "domain=instagram.com",
            brand_icon_service.classify_brand("Instagram")[1],
        )

    def test_instagram_subscription_end_to_end_via_recurring_payments(self):
        """Kullanıcının asıl senaryosu: recurring_payments'a DOĞRUDAN SQL ile
        yazılan bir 'Instagram' kaydı, GUI hiç açılmadan get_active_recurring_
        payments() (gerçek şifre-çözme yolu) + brand_icon_service üzerinden
        subscription_mixin._build_subscription_row'un YAPACAĞI ikon
        çözümlemesiyle birebir aynı sonucu vermeli."""
        import tempfile
        import datetime
        from unittest import mock as _mock

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with _mock.patch("database.db.DB_NAME", db_path):
                from database.init_db import initialize_database
                initialize_database()

                from services.account_service import AccountService
                from database.db import (
                    insert_recurring_payment, get_active_recurring_payments,
                )
                from services.recurring_service import next_due_for_recurrence

                account_id = AccountService.create_account(
                    "Test Hesabı", "checking", initial_balance=5000,
                )
                next_due = next_due_for_recurrence(
                    datetime.date.today(), "monthly", 15,
                )
                insert_recurring_payment(
                    "Instagram", 149.99, "Dijital Platformlar", "monthly",
                    next_due, auto_deduct=0, account_id=account_id,
                    recurrence_day=15,
                )

                payments = get_active_recurring_payments()
                self.assertEqual(len(payments), 1)
                payment = payments[0]
                self.assertEqual(payment["name"], "Instagram")

                # _build_subscription_row'daki BİREBİR satır:
                icon_path = brand_icon_service.resolve_cached_brand_icon_path(
                    payment.get("name", "")
                )
                self.assertIsNone(icon_path)  # önbellek boş — ilk kez görülüyor
                self.assertEqual(
                    brand_icon_service.classify_brand(payment["name"])[0],
                    "instagram",
                )
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
