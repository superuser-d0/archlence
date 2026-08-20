"""docs/ROADMAP.md Faz 1 madde 6 (PIN -> Argon2id + deneme sınırlama):
`ArchlenceApp.check_login`'e eklenen lazy-migration VE throttle dallarının
gerçek davranışını doğrular.

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
import hashlib
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
# "KIVY_WINDOW=mock" was never a real Kivy provider (bkz. docs/ROADMAP.md
# Faz 1 madde 2) — main.py artık gerçek pencere kurulamadığında yalnızca
# ARCHLENCE_HEADLESS=1 açıkça set edildiyse sessizce stub sınıflara düşüyor.
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class _FakeStore:
    """Kivy JsonStore'un exists(key)/get(key)/put(key, **kwargs) arayüzünü
    taklit eder. Anahtar başına put çağrısı sayar — `self` gerçek bir Mock
    olmadığı için Mock'un assert_not_called()'ı burada kullanılamaz."""

    def __init__(self, initial):
        self._data = dict(initial)
        self.put_calls = {}

    def exists(self, key):
        return key in self._data

    def get(self, key):
        return self._data[key]

    def put(self, key, **kwargs):
        self.put_calls[key] = self.put_calls.get(key, 0) + 1
        self._data[key] = kwargs


class _FakeIds(dict):
    def __getattr__(self, name):
        return self[name]


# PAROLA POLİTİKASI 12 KARAKTER + BÜYÜK/KÜÇÜK/RAKAM/ÖZEL istiyor. Bu dosyanın
# konusu tembel Argon2id geçişi ve throttle; ikisi de parolanın POLİTİKAYI
# GEÇTİĞİ durumda anlamlı, çünkü politikayı geçmeyen bir parola bugün zaten
# zorunlu yenilemeye yönlendiriliyor (bkz.
# tests/test_password_policy_and_change.py). Eski fixture "2468" kullanıyordu;
# o PIN artık geçerli bir parola değil, dolayısıyla yükseltme yolunu hiç
# temsil etmiyor.
CORRECT_PASSWORD = "Guclu-Parola-2026!"
WRONG_PASSWORD = "Yanlis-Parola-2026!"


def _legacy_hash(pin, salt):
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


class PinLazyMigrationTest(unittest.TestCase):
    def setUp(self):
        import main
        self.ArchlenceApp = main.ArchlenceApp

    def _make_fake_app(self, security_record, pin_text, throttle_record=None):
        from security.security_service import SecurityService

        app = mock.Mock()
        app.root.ids = _FakeIds(password_input=mock.Mock(text=pin_text))
        store_data = {"security": security_record}
        if throttle_record is not None:
            store_data["security_throttle"] = throttle_record
        app.config_store = _FakeStore(store_data)
        app.authentication_screen.return_value = "login"
        self._SecurityService = SecurityService
        return app

    def test_correct_pin_on_legacy_hash_upgrades_to_argon2id(self):
        from security.security_service import SecurityService

        salt = SecurityService.generate_salt()
        legacy_hash = _legacy_hash(CORRECT_PASSWORD, salt)

        app = self._make_fake_app(
            {"salt": salt, "pin_hash": legacy_hash, "is_set": True}, CORRECT_PASSWORD,
        )

        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_called_once()
        app._handle_failed_login.assert_not_called()

        stored = app.config_store.get("security")
        self.assertTrue(stored["pin_hash"].startswith("$argon2id$"))
        self.assertTrue(
            SecurityService.verify_password(CORRECT_PASSWORD, None, stored["pin_hash"])
        )

    def test_wrong_pin_on_legacy_hash_does_not_upgrade(self):
        """Yanlış PIN girildiğinde yükseltme TETİKLENMEMELİ — offline bir
        saldırgan doğru PIN'i bilmeden hash'i Argon2id'ye 'temizleyip'
        SHA-256 zayıflığını gizleyemesin."""
        from security.security_service import SecurityService

        salt = SecurityService.generate_salt()
        legacy_hash = _legacy_hash(CORRECT_PASSWORD, salt)

        app = self._make_fake_app(
            {"salt": salt, "pin_hash": legacy_hash, "is_set": True}, WRONG_PASSWORD,
        )

        self.ArchlenceApp.check_login(app)

        app._handle_failed_login.assert_called_once()
        app._handle_successful_login.assert_not_called()
        self.assertNotIn("security", app.config_store.put_calls)

        stored = app.config_store.get("security")
        self.assertEqual(stored["pin_hash"], legacy_hash)

    def test_correct_pin_on_already_upgraded_hash_does_not_rewrite(self):
        from security.security_service import SecurityService

        pin_hash = SecurityService.hash_password(CORRECT_PASSWORD)
        app = self._make_fake_app(
            {"salt": None, "pin_hash": pin_hash, "is_set": True}, CORRECT_PASSWORD,
        )

        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_called_once()
        self.assertNotIn("security", app.config_store.put_calls)


class PinThrottleTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 1 madde 6 — deneme sınırlama kısmı."""

    def setUp(self):
        import main
        self.ArchlenceApp = main.ArchlenceApp

    def _make_fake_app(self, pin_text, throttle_record=None, correct_pin=CORRECT_PASSWORD):
        from security.security_service import SecurityService

        app = mock.Mock()
        app.root.ids = _FakeIds(password_input=mock.Mock(text=pin_text))
        pin_hash = SecurityService.hash_password(correct_pin)
        store_data = {"security": {"salt": None, "pin_hash": pin_hash, "is_set": True}}
        if throttle_record is not None:
            store_data["security_throttle"] = throttle_record
        app.config_store = _FakeStore(store_data)
        app.authentication_screen.return_value = "login"
        return app

    def test_first_wrong_attempts_below_threshold_do_not_lock(self):
        from security.security_service import LoginThrottle

        app = self._make_fake_app(WRONG_PASSWORD)
        for _ in range(LoginThrottle.FAILED_ATTEMPT_THRESHOLD - 1):
            self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_not_called()
        self.assertEqual(
            app._handle_failed_login.call_count,
            LoginThrottle.FAILED_ATTEMPT_THRESHOLD - 1,
        )
        # Hiçbiri kilit mesajıyla çağrılmamış olmalı (eşik altı).
        for call in app._handle_failed_login.call_args_list:
            self.assertEqual(call.kwargs, {})

    def test_reaching_threshold_locks_out_and_blocks_further_pin_checks(self):
        """Kilitlendikten sonra DOĞRU PIN bile denenmemeli — kilitliyken
        PIN hiç doğrulanmaz."""
        from security.security_service import LoginThrottle

        app = self._make_fake_app(WRONG_PASSWORD)
        for _ in range(LoginThrottle.FAILED_ATTEMPT_THRESHOLD):
            self.ArchlenceApp.check_login(app)
        app._handle_successful_login.assert_not_called()

        # Şimdi DOĞRU PIN'i dener — ama kilit hâlâ aktif olmalı (0 saniye
        # geçmiş sayılır, gerçek saat kullanılıyor ama lockout süresi en az
        # birkaç saniye).
        app.root.ids.password_input.text = CORRECT_PASSWORD
        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_not_called()
        last_call = app._handle_failed_login.call_args
        self.assertIn("saniye sonra tekrar deneyin", last_call.kwargs["message"])

    def test_successful_login_resets_throttle_counter(self):
        # Eşiğin altında (henüz kilitli değil) birkaç başarısız deneme.
        throttle_state = {"failed_attempts": 0, "last_failed_at": None}
        app = self._make_fake_app(CORRECT_PASSWORD, throttle_record=throttle_state)

        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_called_once()
        stored_throttle = app.config_store.get("security_throttle")
        self.assertEqual(stored_throttle["failed_attempts"], 0)

    def test_already_locked_state_blocks_login_without_checking_pin(self):
        """Zaten kilitli bir state'le başlarsak, DOĞRU PIN girilse bile
        doğrulama hiç çalışmamalı (throttle_state değişmemeli)."""
        import time
        from security.security_service import LoginThrottle

        throttle_state = LoginThrottle.record_failure({}, now=time.time())
        for _ in range(LoginThrottle.FAILED_ATTEMPT_THRESHOLD - 1):
            throttle_state = LoginThrottle.record_failure(
                throttle_state, now=time.time()
            )
        self.assertTrue(LoginThrottle.is_locked(throttle_state))

        app = self._make_fake_app(
            CORRECT_PASSWORD, throttle_record=throttle_state, correct_pin=CORRECT_PASSWORD
        )
        self.ArchlenceApp.check_login(app)

        app._handle_successful_login.assert_not_called()
        # "security" kaydına hiç dokunulmamalı (upgrade dahil) — kilitliyken
        # PIN doğrulaması hiç çalışmadı.
        self.assertNotIn("security", app.config_store.put_calls)


if __name__ == "__main__":
    unittest.main()
