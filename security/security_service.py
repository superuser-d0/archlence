"""Parola hash'leme servisi (login doğrulaması için).

NOT: Veri şifreleme burada DEĞİL, utils/crypto.py'de (AES-256-CBC) yapılır.
Eskiden bu dosyada Fernet tabanlı encrypt_data/decrypt_data da vardı; ancak
veritabanına hiçbir veri Fernet ile yazılmadığı hâlde okuma tarafında yanlışlıkla
kullanılıyor ve açıklamaları çözemiyordu. Tek şifreleme sistemi kalması için
Fernet kısmı kaldırıldı (bkz. utils/crypto.py).

DÜZELTME (docs/ROADMAP.md Faz 1 madde 6): PIN eskiden tek tur, tuzlu SHA-256
ile hash'leniyordu. Tuz rainbow table'a karşı korur ama hesaplamayı
PAHALILAŞTIRMAZ — 4-6 haneli bir PIN'in olası kombinasyonları offline olarak
saniyeler içinde denenebilir. Argon2id'ye geçirildi (bellek-zor, GPU/ASIC
brute-force'u anlamlı ölçüde yavaşlatır).

GERİYE DÖNÜK UYUMLULUK: mevcut kullanıcıların hash'i hâlâ eski SHA-256
formatında diskte duruyor. `verify_password` iki formatı da tanır (Argon2id
hash'leri kendi kendini tanımlar: "$argon2id$..." ile başlar; SHA-256 tam
64 hex karakterdir). Yeni hash'ler her zaman Argon2id — `hash_password`
artık yalnızca Argon2id üretir. Bir kullanıcı eski formatla başarıyla giriş
yaptığında `needs_upgrade()` True döner; çağıran (main.py) bunu görünce
PIN'i sessizce Argon2id'ye yeniden hash'leyip saklar — kullanıcı hiçbir şey
fark etmez, PIN'ini yeniden girmesi gerekmez.
"""
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

# Argon2 kütüphanesinin kendi varsayılanları (OWASP'ın önerdiği aralıkta:
# m=65536 KiB [64 MiB], t=3 tur, p=4 paralellik) — burada elle ayarlanmıyor,
# kütüphanenin kendi güncel önerisine güvenilir.
_hasher = PasswordHasher()

# SHA-256 hex digest'i her zaman TAM 64 karakter ve yalnızca hex rakamları
# içerir — Argon2id'nin "$argon2id$..." formatıyla asla karışmaz.
_LEGACY_SHA256_LENGTH = 64


class SecurityService:

    @staticmethod
    def generate_salt():
        """Her yerel profil için kriptografik olarak güvenli bir tuz üretir.

        GERİYE DÖNÜK UYUMLULUK İÇİN KORUNDU: `main.py::setup_pin` hâlâ bunu
        çağırıp saklıyor (eski kayıtların doğrulanması için gerekli), ama
        yeni Argon2id hash'leri kendi tuzunu kendi içinde üretip saklar —
        bu fonksiyonun ürettiği değer YENİ hash'ler için kullanılmaz.
        """
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password, salt=None):
        """PIN'i Argon2id ile hash'ler; düz PIN hiçbir zaman saklanmaz.

        `salt` parametresi yalnızca eski çağrı imzasıyla uyumluluk için
        kabul edilir ve KULLANILMAZ — Argon2id kendi rastgele tuzunu üretip
        döndürdüğü hash string'inin içine gömer, ayrıca yönetilmesi gerekmez.
        """
        del salt
        return _hasher.hash(str(password))

    @staticmethod
    def _is_legacy_sha256(hashed_password):
        h = str(hashed_password)
        return len(h) == _LEGACY_SHA256_LENGTH and all(
            c in "0123456789abcdef" for c in h.lower()
        )

    @staticmethod
    def verify_password(plain_password, salt, hashed_password):
        """Girilen PIN'i sabit zamanlı karşılaştırmayla doğrular.

        Hem eski (SHA-256+tuz) hem yeni (Argon2id) formatı tanır — hangisi
        olduğu `hashed_password`'ın kendi şeklinden çıkarılır, çağıranın
        bunu bilmesi gerekmez.
        """
        if SecurityService._is_legacy_sha256(hashed_password):
            payload = (str(salt) + str(plain_password)).encode("utf-8")
            candidate = hashlib.sha256(payload).hexdigest()
            return hmac.compare_digest(candidate, str(hashed_password))

        try:
            _hasher.verify(str(hashed_password), str(plain_password))
            return True
        except VerifyMismatchError:
            return False
        except InvalidHash:
            # Ne SHA-256 ne geçerli bir Argon2id string'i — bozuk/tanınmayan
            # bir kayıt. Çökmek yerine güvenli tarafta kal: giriş reddedilir.
            return False

    @staticmethod
    def needs_upgrade(hashed_password):
        """Bu hash eski (SHA-256) formatta mı? True ise, başarılı bir
        doğrulamadan hemen sonra çağıran `hash_password` ile yeniden
        hash'leyip saklamalı (lazy migration — kullanıcı fark etmez)."""
        return SecurityService._is_legacy_sha256(hashed_password)
