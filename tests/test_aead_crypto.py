"""docs/ROADMAP.md Faz 1 madde 5. `utils/aead_crypto.py`'nin saf şifreleme
mantığını doğrular — anahtar saklama, dosya yolu, GUI'yle hiçbir ilgisi
yok, tamamen izole. Legacy `utils/crypto.py` (AES-CBC, fail-open) burada
test edilmiyor; o ayrı, hâlâ değişmemiş bir modül (bkz. tests/test_crypto.py)."""
import os
import unittest

from utils.aead_crypto import DecryptionError, decrypt, encrypt

_KEY = os.urandom(32)
_OTHER_KEY = os.urandom(32)


class RoundTripTest(unittest.TestCase):
    def test_ascii_round_trip(self):
        token = encrypt("hello world", _KEY)
        self.assertEqual(decrypt(token, _KEY), "hello world")

    def test_turkish_unicode_round_trip(self):
        value = "Market Alışverişi - 150,50 TL - şğüöçİ"
        token = encrypt(value, _KEY)
        self.assertEqual(decrypt(token, _KEY), value)

    def test_empty_string_round_trip(self):
        token = encrypt("", _KEY)
        self.assertEqual(decrypt(token, _KEY), "")

    def test_same_plaintext_encrypts_differently_each_time(self):
        """Rastgele nonce sayesinde — aynı metin iki kez şifrelenince aynı
        çıktıyı ÜRETMEMELİ (deterministik şifreleme, desen sızdırır)."""
        first = encrypt("aynı metin", _KEY)
        second = encrypt("aynı metin", _KEY)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt(first, _KEY), "aynı metin")
        self.assertEqual(decrypt(second, _KEY), "aynı metin")


class KeyValidationTest(unittest.TestCase):
    def test_encrypt_rejects_wrong_key_length(self):
        with self.assertRaises(ValueError):
            encrypt("veri", b"cok-kisa-anahtar")

    def test_decrypt_rejects_wrong_key_length(self):
        token = encrypt("veri", _KEY)
        with self.assertRaises(ValueError):
            decrypt(token, b"cok-kisa-anahtar")

    def test_decrypt_with_wrong_key_raises(self):
        token = encrypt("gizli veri", _KEY)
        with self.assertRaises(DecryptionError):
            decrypt(token, _OTHER_KEY)


class TamperDetectionTest(unittest.TestCase):
    """Faz 1 madde 5'in asıl noktası: eski CBC şemasının aksine, kurcalanmış
    veri SESSİZCE yanlış bir sayıya dönüşmüyor — açıkça reddediliyor."""

    def _tamper_last_byte(self, token: str) -> str:
        import base64

        raw = bytearray(base64.b64decode(token))
        raw[-1] ^= 0xFF
        return base64.b64encode(bytes(raw)).decode("utf-8")

    def _tamper_byte_at(self, token: str, index: int) -> str:
        import base64

        raw = bytearray(base64.b64decode(token))
        raw[index] ^= 0xFF
        return base64.b64encode(bytes(raw)).decode("utf-8")

    def test_tampered_ciphertext_raises(self):
        token = encrypt("hassas bakiye: 150000.00", _KEY)
        tampered = self._tamper_last_byte(token)
        with self.assertRaises(DecryptionError):
            decrypt(tampered, _KEY)

    def test_tampered_tag_raises(self):
        token = encrypt("hassas veri", _KEY)


        tampered = self._tamper_byte_at(token, 2 + 12 + 10)
        with self.assertRaises(DecryptionError):
            decrypt(tampered, _KEY)

    def test_tampered_nonce_raises(self):
        token = encrypt("hassas veri", _KEY)
        tampered = self._tamper_byte_at(token, 3)
        with self.assertRaises(DecryptionError):
            decrypt(tampered, _KEY)

    def test_unknown_version_byte_raises(self):
        token = encrypt("veri", _KEY)
        tampered = self._tamper_byte_at(token, 0)
        with self.assertRaises(DecryptionError):
            decrypt(tampered, _KEY)

    def test_unknown_algorithm_id_raises(self):
        token = encrypt("veri", _KEY)
        tampered = self._tamper_byte_at(token, 1)
        with self.assertRaises(DecryptionError):
            decrypt(tampered, _KEY)

    def test_invalid_base64_raises(self):
        with self.assertRaises(DecryptionError):
            decrypt("bu-gecerli-bir-base64-degil-!!!", _KEY)

    def test_truncated_envelope_raises(self):
        import base64

        short = base64.b64encode(b"kisa").decode("utf-8")
        with self.assertRaises(DecryptionError):
            decrypt(short, _KEY)


if __name__ == "__main__":
    unittest.main()
