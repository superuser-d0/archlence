import os
import hashlib
from cryptography.fernet import Fernet

class SecurityService:
    # Anahtarın kaydedileceği dosya yolu
    KEY_FILE = "security/secret.key"
    
    @classmethod
    def get_or_create_key(cls):
        # Klasör yoksa oluştur
        os.makedirs(os.path.dirname(cls.KEY_FILE), exist_ok=True)
            
        # Anahtar dosyası yoksa AES-256 anahtarı oluştur ve güvenle kaydet
        if not os.path.exists(cls.KEY_FILE):
            key = Fernet.generate_key()
            with open(cls.KEY_FILE, "wb") as key_file:
                key_file.write(key)
        else:
            # Anahtar dosyası varsa mevcut anahtarı oku
            with open(cls.KEY_FILE, "rb") as key_file:
                key = key_file.read()
        return key

    @classmethod
    def encrypt_data(cls, text):
        """Metni AES-256 ile şifreler"""
        if not text:
            return text
        f = Fernet(cls.get_or_create_key())
        return f.encrypt(str(text).encode('utf-8')).decode('utf-8')

    @classmethod
    def decrypt_data(cls, encrypted_text):
        """Şifreli metni normal okunaklı metne çevirir"""
        if not encrypted_text:
            return encrypted_text
        f = Fernet(cls.get_or_create_key())
        try:
            return f.decrypt(str(encrypted_text).encode('utf-8')).decode('utf-8')
        except:
            # Eğer veri şifresizse (eski verileriniz gibi), olduğu gibi geri döndür
            return encrypted_text

    @staticmethod
    def hash_password(password):
        """Şifreyi SHA-256 algoritmasıyla hashler"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_password(plain_password, hashed_password):
        """Girilen düz metin şifreyi, kayıtlı hash ile karşılaştırır"""
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password
