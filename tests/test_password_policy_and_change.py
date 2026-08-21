"""Parola politikası, eski kullanıcı geçişi ve parola değiştirme sözleşmesi.

ÖLÇÜLEN KUSURLAR:

1. POLİTİKA ÇOK ZAYIF. `PasswordPolicy.MIN_LENGTH` 4'tü ve yalnız bir büyük
   harf + bir özel karakter isteniyordu. `A!!!` geçerli bir parolaydı; dört
   haneli bir PIN'in arama uzayı Argon2id'yi bile anlamsız kılacak kadar
   küçük.

2. PAROLA DEĞİŞTİRMEK MEVCUT PAROLAYI SORMUYORDU. `_apply_new_pin` doğrudan
   yeni hash'i yazıyordu — açık bırakılmış bir uygulamanın başına oturan
   herkes parolayı değiştirip kilitleyebilirdi. Throttle da devrede değildi.

3. `setup_pin` SİSTEMDE ZATEN PAROLA VARKEN ÇAĞRILABİLİYORDU ve mevcut
   credential'ı sessizce eziyordu.

4. `.strip()` KULLANICININ PAROLASINI DEĞİŞTİRİYORDU. Girilen metnin baş/son
   boşluğu sessizce atılıyor, yani kullanıcı bir parola yazıp BAŞKA bir
   parola kaydediyordu. Artık politika boşluğu açıkça reddediyor ve ham
   metin tutarlı biçimde kullanılıyor.

ESKİ KULLANICI GEÇİŞİ: doğru parolayla giriş DOĞRULANMADAN hiçbir credential
değişmez. Doğrulanan parola yeni politikayı karşılıyorsa (gerekiyorsa
Argon2id'ye yükseltilip) normal giriş sürer. Karşılamıyorsa kullanıcı
finansal ekranlara GEÇİRİLMEDEN zorunlu yenilemeye yönlendirilir ve o yetki
yalnız o başarılı login'den gelir.
"""
import unittest
from unittest import mock

from security.security_service import (
    LoginThrottle,
    PasswordPolicy,
    SecurityService,
)

STRONG = "Guclu-Parola-2026!"
ANOTHER_STRONG = "Baska-Guclu-Parola-2026!"
WEAK_LEGACY = "A!!!"


class PasswordPolicyTest(unittest.TestCase):
    def test_minimum_length_is_twelve(self):
        self.assertEqual(PasswordPolicy.MIN_LENGTH, 12)

    def test_the_old_four_character_password_is_now_refused(self):
        valid, message = PasswordPolicy.validate("A!!!")
        self.assertFalse(valid)
        self.assertTrue(message)

    def test_a_four_digit_pin_is_refused(self):
        valid, _ = PasswordPolicy.validate("1234")
        self.assertFalse(valid)

    def test_eleven_characters_are_refused(self):
        """Sınır tam olarak 12'de: 11 karakter geçmemeli."""
        candidate = "Abcdefgh1!x"
        self.assertEqual(len(candidate), 11)
        valid, _ = PasswordPolicy.validate(candidate)
        self.assertFalse(valid)

    def test_each_character_class_is_required(self):
        cases = {
            "abcdefghijk1!": "büyük harf yok",
            "ABCDEFGHIJK1!": "küçük harf yok",
            "Abcdefghijkl!": "rakam yok",
            "Abcdefghijk12": "özel karakter yok",
        }
        for candidate, reason in cases.items():
            with self.subTest(reason=reason):
                self.assertGreaterEqual(len(candidate), 12)
                valid, message = PasswordPolicy.validate(candidate)
                self.assertFalse(valid, f"{reason} olmasına rağmen kabul edildi")
                self.assertTrue(message)

    def test_a_compliant_password_is_accepted(self):
        valid, message = PasswordPolicy.validate(STRONG)
        self.assertTrue(valid)
        self.assertIsNone(message)

    def test_surrounding_whitespace_is_refused_rather_than_silently_stripped(self):
        for candidate in (f" {STRONG}", f"{STRONG} ", f"\t{STRONG}"):
            with self.subTest(candidate=repr(candidate)):
                valid, message = PasswordPolicy.validate(candidate)
                self.assertFalse(valid)
                self.assertTrue(message)

    def test_none_and_empty_are_refused_without_raising(self):
        for candidate in (None, ""):
            with self.subTest(candidate=repr(candidate)):
                valid, _ = PasswordPolicy.validate(candidate)
                self.assertFalse(valid)

    def test_every_message_comes_from_the_single_policy_source(self):
        """Hata metinleri tek kaynaktan gelmeli; i18n kapısı onlara bakıyor."""
        produced = set()
        for candidate in (
            "", "kisa", "abcdefghijk1!", "ABCDEFGHIJK1!",
            "Abcdefghijkl!", "Abcdefghijk12", f" {STRONG}",
        ):
            valid, message = PasswordPolicy.validate(candidate)
            self.assertFalse(valid)
            produced.add(message)
        self.assertTrue(produced <= set(PasswordPolicy.MESSAGES))


class HashingCompatibilityTest(unittest.TestCase):
    """Argon2id ve eski hash doğrulaması bozulmamalı."""

    def test_argon2id_round_trip(self):
        hashed = SecurityService.hash_password(STRONG)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(SecurityService.verify_password(STRONG, "salt", hashed))
        self.assertFalse(
            SecurityService.verify_password("yanlis", "salt", hashed)
        )

    def test_legacy_sha256_still_verifies_and_is_flagged_for_upgrade(self):
        import hashlib

        salt = "abc123"
        legacy = hashlib.sha256((salt + WEAK_LEGACY).encode("utf-8")).hexdigest()
        self.assertTrue(
            SecurityService.verify_password(WEAK_LEGACY, salt, legacy)
        )
        self.assertTrue(SecurityService.needs_upgrade(legacy))
        self.assertFalse(
            SecurityService.needs_upgrade(SecurityService.hash_password(STRONG))
        )


class _Store:
    """`config_store` yerine geçen, gerçek okuma/yazma davranışını taklit eden depo."""

    def __init__(self):
        self.data = {}
        self.writes = []

    def exists(self, key):
        return key in self.data

    def get(self, key):
        return dict(self.data[key])

    def put(self, key, **values):
        self.data[key] = dict(values)
        self.writes.append((key, dict(values)))

    def delete(self, key):
        self.data.pop(key, None)


class _Field:
    def __init__(self, text=""):
        self.text = text


class _Ids(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _ScreenManager:
    def __init__(self):
        self.current = "login"


class _Root:
    def __init__(self, ids):
        self.ids = ids


class AuthFlowTestBase(unittest.TestCase):
    """`ArchlenceApp`'in auth metotlarını GERÇEK sınıftan, penceresiz çalıştırır.

    Kivy penceresi kurulmuyor: bu metotlar düz Python ve yalnız `self.root.ids`
    ile `self.config_store`'a dokunuyor. Böylece test ettiğimiz şey gerçek
    üretim kodu oluyor, yeniden yazılmış bir kopyası değil.
    """

    def setUp(self):
        import main

        self.main = main
        self.app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        self.store = _Store()
        self.app.config_store = self.store
        self.screen_manager = _ScreenManager()
        self.ids = _Ids({
            "screen_manager": self.screen_manager,
            "password_input": _Field(),
            "login_error_label": _Field(),
            "pin_setup_input": _Field(),
            "pin_confirm_input": _Field(),
            "pin_setup_error_label": _Field(),
            "password_container": _Field(),
        })
        self.app.root = _Root(self.ids)
        self.app._handle_failed_login = self._record_failure
        self.failures = []
        self.route_patch = mock.patch.object(
            main.ArchlenceApp, "route_after_auth", return_value="home"
        )
        self.route_patch.start()
        self.addCleanup(self.route_patch.stop)

    def _record_failure(self, message=None):
        self.failures.append(message)
        self.ids.login_error_label.text = message or "Hatalı Şifre!"

    def _install_credential(self, password, *, legacy=False):
        if legacy:
            import hashlib

            salt = "eski-tuz"
            stored = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        else:
            salt = SecurityService.generate_salt()
            stored = SecurityService.hash_password(password)
        self.store.put("security", pin_hash=stored, salt=salt, is_set=True)
        self.store.writes.clear()
        return stored, salt


class ForcedRenewalTest(AuthFlowTestBase):
    def test_a_strong_argon2_user_logs_straight_in(self):
        self._install_credential(STRONG)
        self.ids.password_input.text = STRONG
        self.app.check_login()
        self.assertEqual(self.screen_manager.current, "home")
        self.assertEqual(self.failures, [])

    def test_a_strong_legacy_password_is_upgraded_and_logs_in(self):
        stored, _ = self._install_credential(STRONG, legacy=True)
        self.assertTrue(SecurityService.needs_upgrade(stored))

        self.ids.password_input.text = STRONG
        self.app.check_login()

        self.assertEqual(self.screen_manager.current, "home")
        upgraded = self.store.get("security")["pin_hash"]
        self.assertTrue(upgraded.startswith("$argon2id$"))
        self.assertTrue(SecurityService.verify_password(STRONG, "x", upgraded))

    def test_a_weak_password_is_routed_to_renewal_not_to_the_financial_screens(self):
        self._install_credential(WEAK_LEGACY, legacy=True)
        self.ids.password_input.text = WEAK_LEGACY

        self.app.check_login()

        self.assertEqual(self.screen_manager.current, "pin_setup")
        self.assertNotEqual(self.screen_manager.current, "home")
        self.assertTrue(self.app.password_renewal_required)

        self.assertEqual(self.store.writes and self.store.get("security")[
            "pin_hash"], self.store.get("security")["pin_hash"])

    def test_a_wrong_password_grants_no_renewal_authorisation(self):
        self._install_credential(WEAK_LEGACY, legacy=True)
        self.ids.password_input.text = "tamamen-yanlis"

        self.app.check_login()

        self.assertFalse(getattr(self.app, "password_renewal_required", False))
        self.assertNotEqual(self.screen_manager.current, "pin_setup")
        self.assertEqual(len(self.failures), 1)

    def test_setup_pin_cannot_overwrite_an_existing_credential_unbidden(self):
        stored, salt = self._install_credential(STRONG)
        self.app.password_renewal_required = False

        self.ids.pin_setup_input.text = ANOTHER_STRONG
        self.ids.pin_confirm_input.text = ANOTHER_STRONG
        self.app.setup_pin()

        self.assertEqual(self.store.get("security")["pin_hash"], stored)
        self.assertEqual(self.store.get("security")["salt"], salt)
        self.assertTrue(self.ids.pin_setup_error_label.text)

    def test_renewal_replaces_the_credential_then_clears_the_authorisation(self):
        stored, _ = self._install_credential(WEAK_LEGACY, legacy=True)
        self.ids.password_input.text = WEAK_LEGACY
        self.app.check_login()
        self.assertTrue(self.app.password_renewal_required)

        self.ids.pin_setup_input.text = STRONG
        self.ids.pin_confirm_input.text = STRONG
        self.app.setup_pin()

        new_hash = self.store.get("security")["pin_hash"]
        self.assertNotEqual(new_hash, stored)
        self.assertTrue(SecurityService.verify_password(STRONG, "x", new_hash))
        self.assertFalse(self.app.password_renewal_required)

        self.assertEqual(
            self.store.get("security_throttle")["failed_attempts"], 0
        )
        self.assertEqual(self.screen_manager.current, "login")

    def test_renewal_still_enforces_the_policy(self):
        stored, _ = self._install_credential(WEAK_LEGACY, legacy=True)
        self.ids.password_input.text = WEAK_LEGACY
        self.app.check_login()

        self.ids.pin_setup_input.text = "zayif1!"
        self.ids.pin_confirm_input.text = "zayif1!"
        self.app.setup_pin()

        self.assertEqual(self.store.get("security")["pin_hash"], stored)
        self.assertTrue(self.app.password_renewal_required)

    def test_first_time_setup_is_unaffected(self):
        self.assertFalse(self.store.exists("security"))
        self.ids.pin_setup_input.text = STRONG
        self.ids.pin_confirm_input.text = STRONG
        self.app.setup_pin()
        self.assertTrue(
            SecurityService.verify_password(
                STRONG, "x", self.store.get("security")["pin_hash"]
            )
        )


class ChangePasswordTest(AuthFlowTestBase):
    def setUp(self):
        super().setUp()
        self.stored, self.salt = self._install_credential(STRONG)
        self.app._current_pin_input = _Field()
        self.app._new_pin_input = _Field()
        self.app._new_pin_confirm = _Field()
        self.app._change_pin_dialog = mock.Mock()
        self.toasts = []
        self.toast_patch = mock.patch(
            "utils.toast.toast", side_effect=lambda text: self.toasts.append(text)
        )
        self.toast_patch.start()
        self.addCleanup(self.toast_patch.stop)

    def _attempt(self, current, new, confirm=None):
        self.app._current_pin_input.text = current
        self.app._new_pin_input.text = new
        self.app._new_pin_confirm.text = confirm if confirm is not None else new
        self.app._apply_new_pin(None)

    def _assert_credential_untouched(self):
        security = self.store.get("security")
        self.assertEqual(security["pin_hash"], self.stored)
        self.assertEqual(security["salt"], self.salt)

    def test_a_wrong_current_password_changes_nothing(self):
        self._attempt("tamamen-yanlis", ANOTHER_STRONG)
        self._assert_credential_untouched()

    def test_a_wrong_current_password_feeds_the_persistent_throttle(self):
        self._attempt("tamamen-yanlis", ANOTHER_STRONG)
        self.assertEqual(
            self.store.get("security_throttle")["failed_attempts"], 1
        )
        self._attempt("yine-yanlis", ANOTHER_STRONG)
        self.assertEqual(
            self.store.get("security_throttle")["failed_attempts"], 2
        )

    def test_an_active_lockout_blocks_the_change_flow_too(self):
        import time

        self.store.put(
            "security_throttle",
            failed_attempts=8, last_failed_at=time.time(),
        )
        self.assertTrue(LoginThrottle.is_locked(self.store.get("security_throttle")))

        self._attempt(STRONG, ANOTHER_STRONG)
        self._assert_credential_untouched()

    def test_a_weak_new_password_is_refused(self):
        self._attempt(STRONG, "zayif1!")
        self._assert_credential_untouched()

    def test_a_mismatched_confirmation_is_refused(self):
        self._attempt(STRONG, ANOTHER_STRONG, confirm="Baska-Bir-Sey-2026!")
        self._assert_credential_untouched()

    def test_reusing_the_current_password_is_refused(self):
        self._attempt(STRONG, STRONG)
        self._assert_credential_untouched()

    def test_a_correct_change_writes_once_and_requires_a_fresh_login(self):
        self._attempt(STRONG, ANOTHER_STRONG)

        security = self.store.get("security")
        self.assertNotEqual(security["pin_hash"], self.stored)
        self.assertTrue(
            SecurityService.verify_password(ANOTHER_STRONG, "x", security["pin_hash"])
        )
        self.assertFalse(
            SecurityService.verify_password(STRONG, "x", security["pin_hash"])
        )

        security_writes = [k for k, _ in self.store.writes if k == "security"]
        self.assertEqual(len(security_writes), 1)

        self.assertEqual(
            self.store.get("security_throttle")["failed_attempts"], 0
        )
        self.assertEqual(self.screen_manager.current, "login")
        self.assertEqual(self.app._current_pin_input, None)

    def test_the_dialog_drops_its_sensitive_field_references_on_dismiss(self):
        self.app.close_change_pin_dialog()
        self.assertIsNone(self.app._current_pin_input)
        self.assertIsNone(self.app._new_pin_input)
        self.assertIsNone(self.app._new_pin_confirm)


if __name__ == "__main__":
    unittest.main()
