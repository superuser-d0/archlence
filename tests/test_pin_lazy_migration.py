"""docs/ROADMAP.md Faz 1 madde 6 (PIN -> Argon2id): `ArchlenceApp.check_login`'e
eklenen lazy-migration dalının gerçek davranışını doğrular.

main.py'nin geri kalanı (KV binding'leri, pencere yaşam döngüsü) burada
çalıştırılmıyor — headless ortamda gerçek pencere açılamıyor (bkz.
tests/test_startup_import.py, tests/test_ids.py'deki aynı kısıt). Ama
`check_login` saf bir metottur: yalnızca `self.root.ids...`,
`self.config_store`, `self.authentication_screen()`,
`self._handle_successful_login/_handle_failed_login`'e ihtiyaç duyar. Gerçek
bir Kivy App örneği kurmadan, bu arayüzü taklit eden hafif bir sahte `self`
ile metodu DOĞRUDAN çağırmak, mock'lanan her şeyin gerçek main.py imzasıyla
eşleştiğini garanti eder — davranışı yeniden yazıp ayrı test etmek değil.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "mock")


class _FakeStore:
    """Kivy JsonStore'un put(key, **kwargs)/get(key) arayüzünü taklit eder.
    put çağrılarını kendi içinde sayar — `self` gerçek bir Mock olmadığı
    için Mock'un assert_not_called()'ı burada kullanılamaz."""

    def __init__(self, initial):
        self._data = dict(initial)
        self.put_call_count = 0

    def get(self, key):
        return self._data[key]

    def put(self, key, **kwargs):
        self.put_call_count += 1
        self._data[key] = kwargs


class _FakeIds(dict):
    def __getattr__(self, name):
        return self[name]


class PinLazyMigrationTest(unittest.TestCase):
    def setUp(self):
        import main
        self.ArchlenceApp = main.ArchlenceApp

    def _make_fake_app(self, security_record, pin_text):
        app = mock.Mock()
        app.root.ids = _FakeIds(password_input=mock.Mock(text=pin_text))
        app.config_store = _FakeStore({"security": security_record})
        app.authentication_screen.return_value = "login"
        return app

    def test_correct_pin_on_legacy_hash_upgrades_to_argon2id(self):
        import hashlib
        from security.security_service import SecurityService

        salt = SecurityService.generate_salt()
        legacy_hash = hashlib.sha256((salt + "2468").encode("utf-8")).hexdigest()

        app = self._make_fake_app(
            {"salt": salt, "pin_hash": legacy_hash, "is_set": True}, "2468",
        )

        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_called_once()
        app._handle_failed_login.assert_not_called()

        stored = app.config_store.get("security")
        self.assertTrue(stored["pin_hash"].startswith("$argon2id$"))
        self.assertTrue(
            SecurityService.verify_password("2468", None, stored["pin_hash"])
        )

    def test_wrong_pin_on_legacy_hash_does_not_upgrade(self):
        """Yanlış PIN girildiğinde yükseltme TETİKLENMEMELİ — offline bir
        saldırgan doğru PIN'i bilmeden hash'i Argon2id'ye 'temizleyip'
        SHA-256 zayıflığını gizleyemesin."""
        import hashlib
        from security.security_service import SecurityService

        salt = SecurityService.generate_salt()
        legacy_hash = hashlib.sha256((salt + "2468").encode("utf-8")).hexdigest()

        app = self._make_fake_app(
            {"salt": salt, "pin_hash": legacy_hash, "is_set": True}, "9999",
        )

        self.ArchlenceApp.check_login(app)

        app._handle_failed_login.assert_called_once()
        app._handle_successful_login.assert_not_called()
        self.assertEqual(app.config_store.put_call_count, 0)

        stored = app.config_store.get("security")
        self.assertEqual(stored["pin_hash"], legacy_hash)

    def test_correct_pin_on_already_upgraded_hash_does_not_rewrite(self):
        from security.security_service import SecurityService

        pin_hash = SecurityService.hash_password("2468")
        app = self._make_fake_app(
            {"salt": None, "pin_hash": pin_hash, "is_set": True}, "2468",
        )

        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_called_once()
        self.assertEqual(app.config_store.put_call_count, 0)


if __name__ == "__main__":
    unittest.main()
