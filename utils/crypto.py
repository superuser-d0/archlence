import base64
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

# PBKDF2 için sabit tuz (salt). Gerçek projelerde bu tuz her kullanıcı için rastgele üretilip DB'de saklanmalıdır.
STATIC_SALT = b'finora_secure_salt_2026'
DEFAULT_PASSWORD = "finora_secure_2026"

import functools

@functools.lru_cache(maxsize=4)
def _get_key(password: str) -> bytes:
    """PBKDF2 kullanarak şifreden 32 byte'lık güvenli anahtar (AES-256 için) üretir."""
    return PBKDF2(password, STATIC_SALT, dkLen=32, count=1000000)

def encrypt(data, password: str = DEFAULT_PASSWORD) -> str:
    """Veriyi AES-256-CBC ile şifreler ve base64 (IV:Ciphertext) olarak döndürür."""
    if data is None or str(data).strip() == "":
        return data

    try:
        key = _get_key(password)
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Veriyi byte dizisine çevir ve blok boyutuna göre pad (doldurma) yap
        data_bytes = str(data).encode('utf-8')
        ciphertext = cipher.encrypt(pad(data_bytes, AES.block_size))
        
        # IV ve Ciphertext'i birleştirip base64'e çevir
        encrypted_payload = iv + ciphertext
        return base64.b64encode(encrypted_payload).decode('utf-8')
    except Exception as e:
        # Hata durumunda verinin orijinalini döndür
        print(f"Şifreleme hatası: {e}")
        return str(data)

def decrypt(enc_data, password: str = DEFAULT_PASSWORD) -> str:
    """Base64 formatındaki (IV:Ciphertext) veriyi AES-256-CBC ile çözer."""
    if enc_data is None or str(enc_data).strip() == "":
        return enc_data

    try:
        # Şifreli verinin base64 çözümü
        encrypted_payload = base64.b64decode(str(enc_data))
        
        # İlk 16 byte IV, kalanı Ciphertext
        iv = encrypted_payload[:16]
        ciphertext = encrypted_payload[16:]
        
        key = _get_key(password)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Çözme ve unpad işlemi
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted_bytes.decode('utf-8')
    except Exception:
        # Şifreleme hatalarına karşı uygulamanın çökmesini önlemek için:
        return "[Şifreli Veri]"
