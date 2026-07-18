"""Parola hash'leme servisi (login doğrulaması için).

NOT: Veri şifreleme burada DEĞİL, utils/crypto.py'de (AES-256-CBC) yapılır.
Eskiden bu dosyada Fernet tabanlı encrypt_data/decrypt_data da vardı; ancak
veritabanına hiçbir veri Fernet ile yazılmadığı hâlde okuma tarafında yanlışlıkla
kullanılıyor ve açıklamaları çözemiyordu. Tek şifreleme sistemi kalması için
Fernet kısmı kaldırıldı (bkz. utils/crypto.py).
"""
import hashlib


class SecurityService:

    @staticmethod
    def hash_password(password):
        """Parolayı SHA-256 ile hash'ler (düz metin parola hiçbir yerde saklanmaz)."""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_password(plain_password, hashed_password):
        """Girilen parolanın hash'ini kayıtlı hash ile karşılaştırır."""
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password
