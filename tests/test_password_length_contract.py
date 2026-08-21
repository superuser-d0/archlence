"""Parola uzunluk sözleşmesi TEK kaynaktan gelmeli.

ÖLÇÜLEN TUTARSIZLIK:

    parola değiştirme diyaloğu (main.py) : max_text_length = 64
    kurulum ve giriş alanları (.kv)      : max_text_length = 32
    PasswordPolicy                       : ÜST SINIR YOK

    PasswordPolicy.validate("Ab1!" + "x" * 61)  ->  (True, None)   # 65 karakter
    PasswordPolicy.validate("Ab1!" + "x" * 196) ->  (True, None)   # 200 karakter

KivyMD 1.2.0'da `max_text_length` metni KESMİYOR, yalnız alanı hata durumuna
sokuyor. Yani bu bir hesap kilidi değildi; ama politika "geçerli" derken
arayüz kırmızı gösterebiliyordu ve iki farklı sayı iki farklı ekranda
yaşıyordu. Sözleşme tek sayıya indirildi: `PasswordPolicy.MAX_LENGTH`.

ESKİ UZUN PAROLA: 64'ten uzun bir parolayla kurulmuş bir hesap doğrulama
YAPILMADAN reddedilip kilitlenmemeli. Önce mevcut hash'e karşı doğrulanır;
doğruysa kullanıcı finans ekranına geçirilmeden zorunlu yenilemeye gider.
"""
import re
import unittest
from pathlib import Path

from security.security_service import PasswordPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: A policy-compliant, 64-character password.
AT_LIMIT = "Ab1!" + "x" * 60
#: A 65-character password, one character too long.
OVER_LIMIT = "Ab1!" + "x" * 61


class PasswordLengthPolicyTest(unittest.TestCase):
    def test_the_limit_is_declared_once(self):
        self.assertEqual(PasswordPolicy.MAX_LENGTH, 64)
        self.assertGreater(PasswordPolicy.MAX_LENGTH, PasswordPolicy.MIN_LENGTH)

    def test_exactly_the_limit_is_accepted(self):
        self.assertEqual(len(AT_LIMIT), PasswordPolicy.MAX_LENGTH)
        valid, message = PasswordPolicy.validate(AT_LIMIT)
        self.assertTrue(valid, message)
        self.assertIsNone(message)

    def test_one_character_over_the_limit_is_refused(self):
        self.assertEqual(len(OVER_LIMIT), PasswordPolicy.MAX_LENGTH + 1)
        valid, message = PasswordPolicy.validate(OVER_LIMIT)
        self.assertFalse(valid)
        self.assertEqual(message, PasswordPolicy.TOO_LONG)

    def test_a_very_long_password_is_refused_too(self):
        valid, message = PasswordPolicy.validate("Ab1!" + "x" * 5000)
        self.assertFalse(valid)
        self.assertEqual(message, PasswordPolicy.TOO_LONG)

    def test_the_message_lives_in_the_single_policy_source(self):
        self.assertIn(PasswordPolicy.TOO_LONG, PasswordPolicy.MESSAGES)

    def test_the_message_has_an_english_translation(self):
        from ui.i18n import tr

        for message in PasswordPolicy.MESSAGES + (PasswordPolicy.REQUIREMENTS,):
            with self.subTest(message=message):
                self.assertNotEqual(tr(message, "en"), message)

    def test_the_requirements_text_states_both_bounds(self):
        self.assertIn(str(PasswordPolicy.MIN_LENGTH), PasswordPolicy.REQUIREMENTS)
        self.assertIn(str(PasswordPolicy.MAX_LENGTH), PasswordPolicy.REQUIREMENTS)


class PasswordFieldLimitGateTest(unittest.TestCase):
    """STATİK KAPI: üç parola alanı da politika sınırını göstermeli.

    KV bir Python sabitini doğrudan okuyamıyor (`max_text_length: 64` düz bir
    sayı), bu yüzden eşitlik kaynak metni üzerinden kanıtlanıyor. Kapı
    olmasaydı iki dosyanın sayısı yine sessizce ayrışırdı — kusurun ilk hâli
    tam olarak buydu.
    """

    def test_every_kv_password_field_uses_the_policy_limit(self):
        source = (PROJECT_ROOT / "ui" / "dashboard.kv").read_text(
            encoding="utf-8"
        )
        lines = source.splitlines()
        password_lines = [
            index for index, line in enumerate(lines)
            if line.strip() == "password: True"
        ]
        self.assertEqual(
            len(password_lines), 3,
            "beklenen üç parola alanı bulunamadı; kapı güncellenmeli",
        )
        for index in password_lines:
            window = lines[index:index + 6]
            limits = [
                int(match.group(1))
                for line in window
                for match in [re.search(r"max_text_length:\s*(\d+)", line)]
                if match
            ]
            self.assertEqual(
                limits, [PasswordPolicy.MAX_LENGTH],
                f"{index + 1}. satırdaki parola alanı politika sınırını "
                f"taşımıyor: {limits}",
            )

    def test_every_python_password_field_binds_to_the_constant(self):
        source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        bound = source.count("max_text_length=PasswordPolicy.MAX_LENGTH")
        literal = re.findall(r"max_text_length=(\d+)", source)
        self.assertEqual(
            bound, 3,
            "parola diyaloğundaki üç alan politika sabitine bağlı değil",
        )
        self.assertEqual(
            literal, [],
            f"main.py hâlâ sabit sayı kullanıyor: {literal}",
        )


class LongLegacyPasswordTest(unittest.TestCase):
    """65+ karakterli eski parola: önce doğrula, sonra yenilemeye yolla."""

    def setUp(self):
        import main
        from unittest import mock

        from security.security_service import SecurityService

        self.SecurityService = SecurityService
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
        })
        self.app.root = _Root(self.ids)
        self.failures = []
        self.app._handle_failed_login = (
            lambda message=None: self.failures.append(message)
        )
        self.route_patch = mock.patch.object(
            main.ArchlenceApp, "route_after_auth", return_value="home"
        )
        self.route_patch.start()
        self.addCleanup(self.route_patch.stop)

        salt = SecurityService.generate_salt()
        self.stored = SecurityService.hash_password(OVER_LIMIT, salt)
        self.store.put("security", pin_hash=self.stored, salt=salt, is_set=True)
        self.store.writes.clear()

    def test_the_correct_long_password_verifies_then_forces_renewal(self):
        self.ids.password_input.text = OVER_LIMIT
        self.app.check_login()

        self.assertEqual(self.screen_manager.current, "pin_setup")
        self.assertTrue(self.app.password_renewal_required)
        self.assertEqual(self.failures, [], "doğru parola reddedildi")
        self.assertEqual(
            self.store.get("security")["pin_hash"], self.stored,
            "credential yenileme öncesinde değiştirildi",
        )

    def test_a_wrong_long_password_grants_no_authorisation(self):
        self.ids.password_input.text = "Ab1!" + "y" * 61
        self.app.check_login()

        self.assertFalse(getattr(self.app, "password_renewal_required", False))
        self.assertNotEqual(self.screen_manager.current, "pin_setup")
        self.assertEqual(len(self.failures), 1)

    def test_renewal_refuses_another_over_limit_password(self):
        self.ids.password_input.text = OVER_LIMIT
        self.app.check_login()

        self.ids.pin_setup_input.text = "Ab1!" + "z" * 61
        self.ids.pin_confirm_input.text = "Ab1!" + "z" * 61
        self.app.setup_pin()

        self.assertEqual(self.store.get("security")["pin_hash"], self.stored)
        self.assertTrue(self.app.password_renewal_required)

    def test_renewal_accepts_a_password_at_the_limit(self):
        self.ids.password_input.text = OVER_LIMIT
        self.app.check_login()

        self.ids.pin_setup_input.text = AT_LIMIT
        self.ids.pin_confirm_input.text = AT_LIMIT
        self.app.setup_pin()

        stored = self.store.get("security")["pin_hash"]
        self.assertNotEqual(stored, self.stored)
        self.assertTrue(
            self.SecurityService.verify_password(AT_LIMIT, "x", stored)
        )
        self.assertFalse(self.app.password_renewal_required)


class _Store:
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


if __name__ == "__main__":
    unittest.main()
