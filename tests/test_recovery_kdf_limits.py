"""Kurtarma materyalinin KDF parametreleri sınırsız kabul edilmemeli.

ÖLÇÜLEN KUSUR: `decrypt_recovery_material` `iterations` alanını
`int(payload["iterations"])` ile alıp DOĞRUDAN PBKDF2'ye veriyordu ve `kdf`
alanına hiç bakmıyordu. Sonuçlar:

  * `"iterations": 10**12` — PBKDF2 o sayıyla çalışmaya BAŞLIYOR. Yanlış
    parolayla bile. Yani paketi veren taraf, paketi açmayı deneyen makinede
    süresiz CPU tüketimi tetikleyebiliyordu.
  * `True` bir `int`'tir (`int(True) == 1`) — tek turluk bir KDF sessizce
    kabul edilirdi.
  * `"600000"` (string) de kabul ediliyordu; tip sözleşmesi yoktu.
  * `salt`/`nonce`/`tag` uzunlukları PBKDF2 ve AES çalıştırıldıktan SONRA,
    ancak istisna yoluyla anlaşılıyordu.

Bu dosya sınırların PBKDF2'ye ULAŞMADAN uygulandığını kanıtlar: PBKDF2
sahte bir nesneyle değiştirilir ve hiç çağrılmadığı doğrulanır.
"""
import base64
import os
import unittest
from unittest import mock

import services.backup_service as backup_service
from services.backup_service import (
    decrypt_recovery_material,
    encrypt_recovery_material,
)
from utils.errors import IntegrityVerificationError

PASSPHRASE = "kurtarma-parolasi-2026"


class RecoveryKdfBoundsTest(unittest.TestCase):
    def setUp(self):
        self.key = os.urandom(32)
        self.payload = encrypt_recovery_material(self.key, PASSPHRASE)

    def _rejected_without_touching_pbkdf2(self, payload):
        """Reddin PBKDF2'den ÖNCE gelmesi şart — asıl maliyet orada."""
        sentinel = mock.Mock(side_effect=AssertionError("PBKDF2 çağrıldı"))
        with mock.patch.object(backup_service, "PBKDF2", sentinel):
            with self.assertRaises(IntegrityVerificationError):
                decrypt_recovery_material(payload, PASSPHRASE)
        sentinel.assert_not_called()

    def test_valid_material_still_round_trips(self):
        self.assertEqual(self.payload["iterations"], 600_000)
        self.assertEqual(self.payload["kdf"], "PBKDF2-HMAC-SHA256")
        self.assertEqual(
            decrypt_recovery_material(self.payload, PASSPHRASE), self.key
        )

    def test_absurd_iteration_count_never_reaches_pbkdf2(self):
        payload = dict(self.payload, iterations=10 ** 12)
        self._rejected_without_touching_pbkdf2(payload)

    def test_boolean_iterations_are_rejected(self):
        """`int(True) == 1` — tip kontrolü olmadan tek turluk KDF geçerdi."""
        for value in (True, False):
            with self.subTest(value=value):
                self._rejected_without_touching_pbkdf2(
                    dict(self.payload, iterations=value)
                )

    def test_string_iterations_are_rejected(self):
        self._rejected_without_touching_pbkdf2(
            dict(self.payload, iterations="600000")
        )

    def test_float_iterations_are_rejected(self):
        self._rejected_without_touching_pbkdf2(
            dict(self.payload, iterations=600000.0)
        )

    def test_zero_and_negative_iterations_are_rejected(self):
        for value in (0, -1, -600000):
            with self.subTest(value=value):
                self._rejected_without_touching_pbkdf2(
                    dict(self.payload, iterations=value)
                )

    def test_iterations_below_the_supported_floor_are_rejected(self):
        from services.backup_service import MIN_RECOVERY_ITERATIONS

        self._rejected_without_touching_pbkdf2(
            dict(self.payload, iterations=MIN_RECOVERY_ITERATIONS - 1)
        )

    def test_iterations_above_the_supported_ceiling_are_rejected(self):
        from services.backup_service import MAX_RECOVERY_ITERATIONS

        self._rejected_without_touching_pbkdf2(
            dict(self.payload, iterations=MAX_RECOVERY_ITERATIONS + 1)
        )

    def test_unknown_kdf_is_rejected(self):
        for value in ("PBKDF2-HMAC-SHA1", "scrypt", "", None, 7):
            with self.subTest(value=value):
                self._rejected_without_touching_pbkdf2(
                    dict(self.payload, kdf=value)
                )

    def test_missing_kdf_is_rejected(self):
        payload = dict(self.payload)
        payload.pop("kdf")
        self._rejected_without_touching_pbkdf2(payload)

    def test_wrong_field_lengths_are_rejected_before_pbkdf2(self):
        cases = {
            "salt": base64.b64encode(os.urandom(8)).decode("ascii"),
            "nonce": base64.b64encode(os.urandom(4)).decode("ascii"),
            "tag": base64.b64encode(os.urandom(3)).decode("ascii"),
            "ciphertext": base64.b64encode(b"").decode("ascii"),
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                self._rejected_without_touching_pbkdf2(
                    dict(self.payload, **{field: value})
                )

    def test_wrong_passphrase_still_raises_the_same_contract(self):
        with self.assertRaises(IntegrityVerificationError):
            decrypt_recovery_material(self.payload, "yanlis-parola-2026")

    def test_corrupt_ciphertext_still_raises_the_same_contract(self):
        raw = bytearray(base64.b64decode(self.payload["ciphertext"]))
        raw[0] ^= 0xFF
        payload = dict(
            self.payload,
            ciphertext=base64.b64encode(bytes(raw)).decode("ascii"),
        )
        with self.assertRaises(IntegrityVerificationError):
            decrypt_recovery_material(payload, PASSPHRASE)


if __name__ == "__main__":
    unittest.main()
