"""`mixins/account_mixin.py`'daki dört kullanıcıya-dönük sınırın KAPSAMI.

NEDEN VAR: dördü de `except Exception` idi ve denetim aracı
(`scripts/audit_exception_handlers.py`) bunları "kullanıcıya gösterilen;
daraltılması incelenmeli" diye işaretliyordu. Daraltma bir tur boyunca bilerek
ertelendi ve gerekçesi kayıtlıydı: GUI koşturulamadığı için daraltılmış bir
catch'in ekranı zarifçe bozulmak yerine ÇÖKERTMEDİĞİ doğrulanamıyordu.

Bu paket daraltmanın İKİ YÖNÜNÜ birlikte sabitliyor ve ikisi birlikte anlamlı:

  * BEKLENEN hata tipleri hâlâ yakalanıyor — kullanıcı toast görüyor, ekran
    ayakta kalıyor. Daraltma zarafeti bozmadı.
  * BEKLENMEYEN tip artık YAKALANMIYOR — yukarı çıkıyor. Asıl kazanç bu:
    `KeyError` gibi bir kodlama hatası, kullanıcıya anlaşılmaz bir toast
    göstermek yerine `main.py::_log_unhandled_exception`'a gidip traceback'le
    loglanıyor.

Biri sınırı `Exception`'a geri genişletirse "yukarı çıkmalı" testleri kırmızıya
döner. Bu, kapının bilinen-bozuk duruma karşı doğrulanma biçimi.
"""
import os
import sqlite3
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


def _mixin():


    from mixins import account_mixin
    return account_mixin


class ErrorSetIsDerivedFromWhatTheServicesRaiseTest(unittest.TestCase):

    def test_set_covers_the_domain_and_database_errors(self):
        from utils.errors import ArchlenceError

        errors = _mixin()._USER_FACING_ERRORS
        self.assertIn(ArchlenceError, errors)
        self.assertIn(sqlite3.Error, errors)


        self.assertIn(ValueError, errors)
        self.assertIn(TypeError, errors)

    def test_set_does_not_swallow_plain_exception(self):
        """Küme `Exception` içerirse daraltma anlamsızdır."""
        self.assertNotIn(Exception, _mixin()._USER_FACING_ERRORS)

    def test_crypto_errors_are_reachable_through_the_base_class(self):
        """Kripto hataları kümede AYRI AYRI sayılmıyor; tabanı yeterli."""
        from utils.errors import (
            DecryptionError, IntegrityVerificationError, KeyUnavailableError,
        )

        for error in (DecryptionError, IntegrityVerificationError,
                      KeyUnavailableError):
            with self.subTest(error=error.__name__):
                self.assertTrue(
                    issubclass(error, _mixin()._USER_FACING_ERRORS),
                    f"{error.__name__} kullanıcıya-dönük kümeye girmiyor",
                )


class _Harness:
    """`open_card_statement` / `open_upcoming_installments` için asgari `self`."""

    def __init__(self):
        self.toasts = []


class StatementBoundaryTest(unittest.TestCase):
    """`open_card_statement` — ekstre okunamadığında."""

    def _call(self, raised):
        module = _mixin()
        harness = _Harness()
        with mock.patch(
            "services.transaction_service.TransactionService"
            ".get_recent_for_account",
            side_effect=raised,
        ), mock.patch.object(
            module, "toast", lambda text: harness.toasts.append(text)
        ):
            module.AccountMixin.open_card_statement(harness, 1)
        return harness

    def test_domain_error_is_shown_not_raised(self):
        from utils.errors import KeyUnavailableError

        harness = self._call(KeyUnavailableError("anahtar yok"))
        self.assertEqual(len(harness.toasts), 1)
        self.assertIn("Could not read the statement", harness.toasts[0])

    def test_database_error_is_shown_not_raised(self):
        harness = self._call(sqlite3.OperationalError("kilitli"))
        self.assertEqual(len(harness.toasts), 1)

    def test_value_error_is_shown_not_raised(self):
        harness = self._call(ValueError("bozuk tutar"))
        self.assertEqual(len(harness.toasts), 1)

    def test_programming_error_propagates_instead_of_becoming_a_toast(self):
        """Daraltmanın ASIL KAZANCI. Genişletilirse burası kırmızıya döner."""
        with self.assertRaises(KeyError):
            self._call(KeyError("beklenmeyen"))

    def test_attribute_error_also_propagates(self):
        with self.assertRaises(AttributeError):
            self._call(AttributeError("beklenmeyen"))


class InstallmentPlansBoundaryTest(unittest.TestCase):
    """`open_upcoming_installments` — taksit planları okunamadığında."""

    def _call(self, raised):
        module = _mixin()
        harness = _Harness()
        with mock.patch(
            "services.transaction_service.TransactionService"
            ".get_installment_plans",
            side_effect=raised,
        ), mock.patch.object(
            module, "toast", lambda text: harness.toasts.append(text)
        ):
            module.AccountMixin.open_upcoming_installments(harness, 1)
        return harness

    def test_database_error_is_shown_not_raised(self):
        harness = self._call(sqlite3.OperationalError("kilitli"))
        self.assertEqual(len(harness.toasts), 1)
        self.assertIn("Could not read the instalment plans", harness.toasts[0])

    def test_domain_error_is_shown_not_raised(self):
        from utils.errors import DecryptionError

        harness = self._call(DecryptionError("çözülemedi"))
        self.assertEqual(len(harness.toasts), 1)

    def test_programming_error_propagates(self):
        with self.assertRaises(KeyError):
            self._call(KeyError("beklenmeyen"))


if __name__ == "__main__":
    unittest.main()
