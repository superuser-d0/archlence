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
        self.assertIn("netflix.com", url)
        self.assertIn("format=png", url)
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


if __name__ == "__main__":
    unittest.main()
