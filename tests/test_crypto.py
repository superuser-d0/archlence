import io
import sys
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

# Proje kökünü (tests/'in bir üstü) sys.path'e ekle ki utils.crypto bulunsun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.crypto import DEFAULT_PASSWORD, encrypt, decrypt

def run_crypto_test():
    original_text = "Market Alışverişi - 150 TL"
    test_password = DEFAULT_PASSWORD
    print("🔐 CRYPTO MODULE TEST")
    print("-" * 50)
    print(f"Original String : {original_text}")
    print(f"Test Password   : {test_password}")
    
    # 2. Encrypt
    encrypted_text = encrypt(original_text, test_password)
    print("\n[ENCRYPTING...]")
    print(f"Encrypted Output (Base64 IV:Ciphertext):\n{encrypted_text}")
    
    # 3. Decrypt
    decrypted_text = decrypt(encrypted_text, test_password)
    print("\n[DECRYPTING...]")
    print(f"Decrypted Output: {decrypted_text}")
    
    # 4. Boolean Check
    print("\n[VERIFICATION]")
    if original_text == decrypted_text:
        print("✅ SUCCESS: The decrypted string matches the original exactly.")
    else:
        print("❌ FAILED: The decrypted string does NOT match the original.")
    print("-" * 50)


class CryptoCompatibilityTest(unittest.TestCase):
    def test_current_cipher_round_trip(self):
        value = "Archlence güvenli veri"
        self.assertEqual(decrypt(encrypt(value)), value)


class NarrowedExceptHandlingTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 2 "except ayrımı". DAVRANIŞ BİLEREK DEĞİŞMEDİ —
    gerçek şifreleme/çözme hatası hâlâ aynı fail-open değerine düşüyor
    (decrypt -> "[Şifreli Veri]", encrypt -> düz metin). Değişen: (1) artık
    loglanıyor, (2) yalnızca gerçekten olabilecek hata tipleri yakalanıyor —
    alakasız bir programlama hatası artık bu yoldan sessizce yutulmuyor,
    gerçek traceback'iyle yükseliyor."""

    def test_corrupted_ciphertext_still_falls_back_gracefully(self):
        """Gerçek bozuk/kurcalanmış veri (geçersiz base64) davranışı
        korunmalı — hâlâ çöküş yok, hâlâ yerine geçen değer."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = decrypt("bu-gecerli-bir-base64-degil-!!!")
        self.assertEqual(result, "[Şifreli Veri]")
        self.assertIn("VERİ BÜTÜNLÜĞÜ", buf.getvalue())

    def test_truncated_ciphertext_still_falls_back_gracefully(self):
        """16 byte'tan kısa (IV'siz) bir yük geçerli base64 olabilir ama
        AES.new'e geçersiz IV verir — ValueError, hâlâ yakalanmalı."""
        import base64
        short_payload = base64.b64encode(b"kisa").decode("utf-8")
        result = decrypt(short_payload)
        self.assertEqual(result, "[Şifreli Veri]")

    def test_unrelated_bug_inside_decrypt_now_propagates(self):
        """Asıl davranış değişikliği: şifre çözmeyle ilgisi olmayan bir hata
        (ör. burada simüle edilen bir programlama hatası) artık '[Şifreli
        Veri]' arkasına gizlenip sessizce yutulmuyor — gerçek hata olarak
        yükseliyor. Eskiden `except Exception` bunu da yutardı."""
        with mock.patch(
            "utils.crypto.unpad", side_effect=RuntimeError("beklenmedik bug")
        ):
            with self.assertRaises(RuntimeError):
                decrypt(encrypt("test verisi"))

    def test_unrelated_bug_inside_encrypt_now_propagates(self):
        with mock.patch(
            "utils.crypto.get_random_bytes",
            side_effect=RuntimeError("beklenmedik bug"),
        ):
            with self.assertRaises(RuntimeError):
                encrypt("test verisi")

    def test_encrypt_failure_still_falls_back_to_plaintext_and_logs(self):
        """DAVRANIŞ BİLEREK DEĞİŞMEDİ (Faz 1'in konusu) — ama artık en
        azından loglanıyor; önceden şifreleme başarısız olup gerçek veri
        düz metin yazıldığında hiçbir iz yoktu."""
        buf = io.StringIO()
        with mock.patch(
            "utils.crypto.get_random_bytes", side_effect=ValueError("kirik")
        ), redirect_stdout(buf):
            result = encrypt("hassas veri")
        self.assertEqual(result, "hassas veri")
        self.assertIn("GÜVENLİK", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
