import sys
import os

# Add the parent directory to sys.path so we can import utils.crypto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.crypto import encrypt, decrypt

def run_crypto_test():
    # 1. Define dummy test string and password
    original_text = "Market Alışverişi - 150 TL"
    test_password = "finora_secure_2026"
    
    print("-" * 50)
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

if __name__ == "__main__":
    run_crypto_test()
