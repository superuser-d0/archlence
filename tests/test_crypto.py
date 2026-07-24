import sys
import os
import unittest

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

if __name__ == "__main__":
    unittest.main()
