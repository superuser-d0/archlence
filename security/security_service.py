"""Parola hash'leme servisi (login doğrulaması için).

NOT: Veri şifreleme burada DEĞİL, utils/crypto.py'de (AES-256-CBC) yapılır.
Eskiden bu dosyada Fernet tabanlı encrypt_data/decrypt_data da vardı; ancak
veritabanına hiçbir veri Fernet ile yazılmadığı hâlde okuma tarafında yanlışlıkla
kullanılıyor ve açıklamaları çözemiyordu. Tek şifreleme sistemi kalması için
Fernet kısmı kaldırıldı (bkz. utils/crypto.py).
"""
import hashlib
import hmac
import secrets


class SecurityService:

    @staticmethod
    def generate_salt():
        """Her yerel profil için kriptografik olarak güvenli bir tuz üretir."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password, salt):
        """PIN'i profil tuzuyla SHA-256 hash'ler; düz PIN hiçbir zaman saklanmaz."""
        payload = (str(salt) + str(password)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def verify_password(plain_password, salt, hashed_password):
        """Girilen PIN'i sabit zamanlı karşılaştırmayla doğrular."""
        candidate = SecurityService.hash_password(plain_password, salt)
        return hmac.compare_digest(candidate, str(hashed_password))
