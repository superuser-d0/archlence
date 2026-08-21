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


        self.assertNotIn("clearbit.com", url)
        self.assertIn("netflix.com", url)
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

    @staticmethod
    def _encoded_image(size, image_format="PNG", color=(10, 20, 30, 255)):
        """Gerçekten çözülebilen bir görüntü üretir.

        Sahte baytlar (`b"\\x89PNG...fake"`) artık yetmiyor: indirme yolu
        içeriği Pillow ile GERÇEKTEN çözüp boyutuna bakıyor — sahte bayt
        testi, ölçtüğünü sandığı şeyi ölçmezdi."""
        from io import BytesIO

        from PIL import Image

        buffer = BytesIO()
        Image.new("RGBA", (size, size), color).save(
            buffer, format=image_format
        )
        return buffer.getvalue()

    def test_successful_png_download_is_cached(self):
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=self._encoded_image(256),
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

    def test_small_favicon_is_upscaled_instead_of_being_dropped(self):
        """REGRESYON: bir ara 32px altındaki logolar tamamen elenmişti ve
        hiçbir sağlayıcıda 16x16'dan büyük favicon yayınlamayan markaların
        (Türk Telekom, Superonline) logosu arayüzden KAYBOLDU. Markayı
        tanımak kenar keskinliğinden önemli — küçük logo artık büyütülerek
        saklanır."""
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=self._encoded_image(16),
        )
        with mock.patch("requests.get", return_value=response):
            self.assertTrue(
                brand_icon_service.fetch_and_cache_brand_icon("Türk Telekom")
            )

        destination = os.path.join(self.temp_dir.name, "turk-telekom.png")
        from PIL import Image
        with Image.open(destination) as cached:
            self.assertEqual(
                cached.size,
                (brand_icon_service.TARGET_ICON_PX,) * 2,
            )
        self.assertEqual(
            brand_icon_service.resolve_cached_brand_icon_path("TTNET internet"),
            destination,
        )

    def test_unusably_tiny_payload_is_still_rejected(self):
        """Eşiğin altı yalnızca bozuk/anlamsız içeriği eler; gerçek
        favicon'lar en az 16px olduğu için bu yol pratikte nadirdir."""
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=self._encoded_image(8),
        )
        with mock.patch("requests.get", return_value=response):
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Turkcell")
            )

        self.assertIsNone(
            brand_icon_service.resolve_cached_brand_icon_path("Turkcell")
        )

    def test_rejected_brand_is_not_refetched_on_every_render(self):
        """REGRESYON KORUMASI: çağıran taraf (main.py::_render_recent_
        transactions) diskte ikon YOKSA indirmeyi tetikler. 'Uygun logo yok'
        kararı hatırlanmazsa, kalıcı olarak elenen her marka dashboard'ın HER
        çiziminde sağlayıcı sayısı kadar HTTP isteği doğurur."""
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=self._encoded_image(8),
        )
        with mock.patch("requests.get", return_value=response) as request:
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Turkcell")
            )
        first_round = request.call_count
        self.assertGreater(first_round, 0)

        with mock.patch("requests.get", return_value=response) as request:
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Turkcell")
            )
        request.assert_not_called()

    def test_stale_miss_marker_allows_a_retry(self):
        """Negatif önbellek kalıcı olmamalı: marka ileride daha büyük bir
        favicon yayınlarsa TTL dolduğunda yeniden denenmeli."""
        import os as _os
        import time

        small = mock.Mock(
            status_code=200, headers={}, content=self._encoded_image(8),
        )
        with mock.patch("requests.get", return_value=small):
            self.assertFalse(
                brand_icon_service.fetch_and_cache_brand_icon("Turkcell")
            )

        marker = brand_icon_service._miss_path("turkcell")
        stale = time.time() - brand_icon_service._MISS_TTL_SECONDS - 60
        _os.utime(marker, (stale, stale))

        large = mock.Mock(
            status_code=200, headers={}, content=self._encoded_image(256),
        )
        with mock.patch("requests.get", return_value=large):
            self.assertTrue(
                brand_icon_service.fetch_and_cache_brand_icon("Turkcell")
            )

    def test_ico_payload_is_normalized_to_a_real_png_on_disk(self):
        """Sağlayıcılar `.png` isteğine ICO döndürebiliyor (ölçüldü:
        icon.horse → claude.ai). Ham baytları yazmak, PNG adlı bir ICO
        bırakırdı; uzantıya göre yükleyici seçen ortamlarda (paketlenmiş
        Windows derlemesi) bu sessizce kırılır."""
        response = mock.Mock(
            status_code=200,
            headers={"Content-Type": "image/x-icon"},
            content=self._encoded_image(128, image_format="ICO"),
        )
        with mock.patch("requests.get", return_value=response):
            self.assertTrue(
                brand_icon_service.fetch_and_cache_brand_icon("Claude Pro")
            )

        destination = os.path.join(self.temp_dir.name, "claude.png")
        with open(destination, "rb") as handle:
            self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")

    def test_largest_provider_result_wins_when_none_hit_the_target(self):
        """Hiçbir aday TARGET'ı geçmezse en büyüğü seçilmeli — tek sağlayıcıya
        bağlanmanın markadan markaya kalite kaybettirmesinin çözümü budur."""


        winner = (200, 30, 40, 255)
        responses = [
            mock.Mock(status_code=200, headers={},
                      content=self._encoded_image(48, color=(1, 2, 3, 255))),
            mock.Mock(status_code=200, headers={},
                      content=self._encoded_image(96, color=winner)),
            mock.Mock(status_code=200, headers={},
                      content=self._encoded_image(64, color=(4, 5, 6, 255))),
        ]
        with mock.patch("requests.get", side_effect=responses) as request:
            self.assertTrue(
                brand_icon_service.fetch_and_cache_brand_icon("Netflix")
            )

        self.assertEqual(request.call_count, 3, "hepsi denenmeli")
        from PIL import Image
        with Image.open(os.path.join(self.temp_dir.name, "netflix.png")) as cached:
            self.assertEqual(
                cached.convert("RGBA").getpixel((5, 5)), winner,
                "en büyük aday (96px) diske yazılmalı",
            )
            self.assertEqual(
                cached.size, (brand_icon_service.TARGET_ICON_PX,) * 2)

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
                self.assertTrue(url, "her tanınan marka bir URL üretmeli")

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

    def test_generic_google_does_not_shadow_later_specific_brands(self):
        """Ekstre açıklamalarında ödeme aracısı önce yazılabilir. Genel
        Google eşleşmesi, listedeki daha özgül markaları gölgelememeli."""
        self.assertEqual(
            brand_icon_service.classify_brand(
                "GOOGLE *ProtonVPN aylık abonelik"
            )[0],
            "proton-vpn",
        )
        self.assertEqual(
            brand_icon_service.classify_brand("Google hizmeti")[0], "google",
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
            "instagram.com",
            brand_icon_service.classify_brand("Instagram")[1],
        )

    def test_proton_family_products_resolve_to_brand_icons(self):
        cases = {
            "Proton Unlimited": ("proton", "proton.me"),
            "Proton VPN Plus": ("proton-vpn", "protonvpn.com"),
            "ProtonMail": ("proton-mail", "proton.me"),
            "Proton Pass Plus": ("proton-pass", "proton.me"),
            "Proton Drive": ("proton-drive", "proton.me"),
            "Proton Calendar": ("proton-calendar", "proton.me"),
        }
        for text, (expected_key, expected_domain) in cases.items():
            with self.subTest(text=text):
                key, url = brand_icon_service.classify_brand(text)
                self.assertEqual(key, expected_key)
                self.assertIn(expected_domain, url)

    def test_extended_subscription_catalog_resolves_to_icons(self):
        cases = {
            "tabii Premium": "tabii",
            "Storytel": "storytel",
            "Audible Plus": "audible",
            "Kindle Unlimited": "kindle-unlimited",
            "Blinkist Premium": "blinkist",
            "Figma Professional": "figma",
            "JetBrains All Products Pack": "jetbrains",
            "1Password Families": "1password",
            "LastPass Premium": "lastpass",
            "Claude Pro": "claude",
            "Gemini Advanced": "gemini",
            "Udemy Personal Plan": "udemy",
            "Coursera Plus": "coursera",
            "Duolingo Super": "duolingo",
            "Skillshare": "skillshare",
            "MACFit üyeliği": "macfit",
            "Club Sporium": "sporium",
            "Strava Premium": "strava",
            "Headspace": "headspace",
            "Patreon": "patreon",
            "Wikipedia bağışı": "wikipedia",
        }
        for text, expected_key in cases.items():
            with self.subTest(text=text):
                key, url = brand_icon_service.classify_brand(text)
                self.assertEqual(key, expected_key)
                self.assertTrue(url, "her tanınan marka bir URL üretmeli")

    def test_turkish_telecom_brands_and_statement_aliases_resolve(self):
        cases = {
            "Türk Telekom mobil faturası": (
                "turk-telekom", "turktelekom.com.tr",
            ),
            "TURKTELEKOM OTOMATİK ÖDEME": (
                "turk-telekom", "turktelekom.com.tr",
            ),
            "TTNET internet": ("turk-telekom", "turktelekom.com.tr"),
            "Vodafone Red tarifem": ("vodafone", "vodafone.com.tr"),
            "Vodafone Net": ("vodafone", "vodafone.com.tr"),
            "Turkcell Platinum": ("turkcell", "turkcell.com.tr"),
            "Turkcell Superonline": ("superonline", "superonline.net"),
        }
        for text, (expected_key, expected_domain) in cases.items():
            with self.subTest(text=text):
                key, url = brand_icon_service.classify_brand(text)
                self.assertEqual(key, expected_key)
                self.assertIn(expected_domain, url)

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


                icon_path = brand_icon_service.resolve_cached_brand_icon_path(
                    payment.get("name", "")
                )
                self.assertIsNone(icon_path)
                self.assertEqual(
                    brand_icon_service.classify_brand(payment["name"])[0],
                    "instagram",
                )
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
