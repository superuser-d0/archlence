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
import time as _time

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


class PasswordPolicy:
    """Salt+Argon2id ve `LoginThrottle` yalnızca HASH'İ ve DENEME HIZINI korur —
    girdinin kendisi hâlâ 4 haneli, yalnızca-rakam bir PIN olduğu sürece arama
    uzayı (10.000 kombinasyon) küçük kalır. Bu sınıf girdi tarafını genişletir:
    en az bir büyük harf ve en az bir noktalama/özel karakter zorunluluğu,
    karakter kümesini rakamlardan çıkarıp alfasayısal+sembol'e taşıyarak
    olası kombinasyon sayısını katlarca artırır (çevrimdışı brute-force'u
    yavaşlatır). `setup_pin`, `_apply_new_pin` (main.py) ve sıfırlama sonrası
    yeniden kurulum — hepsi `pin_setup` ekranına, dolayısıyla `setup_pin`'e
    çıktığı için tek bir politika kaynağı üçünü de kapsar.
    """

    MIN_LENGTH = 4
    SPECIAL_CHARS = ".,;:!?-_@#$%^&*()+=/\\|~`'\"<>[]{}"

    @staticmethod
    def validate(password):
        """(is_valid, error_message) döndürür. `error_message`, `translate()`'e
        verilebilecek Türkçe kaynak metindir; geçerliyse None."""
        password = password or ""
        if len(password) < PasswordPolicy.MIN_LENGTH:
            return False, "Şifre en az 4 karakter olmalıdır."
        if not any(c.isupper() for c in password):
            return False, "Şifre en az 1 büyük harf içermelidir."
        if not any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            return False, "Şifre en az 1 özel karakter (örn. . veya ,) içermelidir."
        return True, None


class LoginThrottle:
    """Ardışık başarısız PIN denemelerinden sonra artan gecikme/geçici kilit
    (docs/ROADMAP.md Faz 1 madde 6'nın Argon2id'den ayrı bırakılan kısmı).

    SAF MANTIK: state (deneme sayısı + son başarısız zaman) harici olarak
    sağlanır ve döndürülür — bu sınıf hiçbir şeyi kendi başına kalıcı
    saklamaz, `main.py` state'i `config_store`'un "security_throttle"
    kaydında tutar. `now` her yerde enjekte edilebilir (varsayılan
    `time.time()`) — testler gerçek saniyeler beklemeden saat manipülasyonunu
    simüle edebilir.

    KARAR — kilit durumu KALICI: `config_store`'da saklanır, uygulama
    yeniden başlatılınca SIFIRLANMAZ. Bilinçli bir seçim: bu, cihaza
    fiziksel/dosya erişimi olan bir saldırganı hedefleyen bir tehdit modeli
    — geçici (yalnızca bellekte) bir sayaç, uygulamayı yeniden başlatarak
    trivially bypass edilebilirdi ve tüm mekanizmayı anlamsız kılardı.

    Politika: ilk `FAILED_ATTEMPT_THRESHOLD` deneme için gecikme YOK (yanlış
    tuşlama toleransı — her PIN girişini cezalandırmak kötü UX olurdu).
    Eşikten sonra üstel artan kilit: 2^(deneme - eşik) * taban saniye,
    `LOCKOUT_MAX_SECONDS` tavanına kadar.
    """

    FAILED_ATTEMPT_THRESHOLD = 3
    LOCKOUT_BASE_SECONDS = 5
    LOCKOUT_MAX_SECONDS = 300  # 5 dakika tavan

    @staticmethod
    def _lockout_duration(failed_attempts):
        if failed_attempts < LoginThrottle.FAILED_ATTEMPT_THRESHOLD:
            return 0
        exponent = failed_attempts - LoginThrottle.FAILED_ATTEMPT_THRESHOLD
        seconds = LoginThrottle.LOCKOUT_BASE_SECONDS * (2 ** exponent)
        return min(seconds, LoginThrottle.LOCKOUT_MAX_SECONDS)

    @staticmethod
    def seconds_remaining(state, now=None):
        """`state`: {"failed_attempts": int, "last_failed_at": float|None}.
        Kilit bitmişse ya da hiç yoksa 0.0 döner."""
        if now is None:
            now = _time.time()
        state = state or {}
        failed_attempts = int(state.get("failed_attempts", 0) or 0)
        last_failed_at = state.get("last_failed_at")
        duration = LoginThrottle._lockout_duration(failed_attempts)
        if duration == 0 or last_failed_at is None:
            return 0.0
        elapsed = now - float(last_failed_at)
        return max(0.0, duration - elapsed)

    @staticmethod
    def is_locked(state, now=None):
        return LoginThrottle.seconds_remaining(state, now=now) > 0

    @staticmethod
    def record_failure(state, now=None):
        """Başarısız bir denemeden sonraki YENİ state'i döndürür (girdiyi
        mutasyona uğratmaz)."""
        if now is None:
            now = _time.time()
        state = state or {}
        failed_attempts = int(state.get("failed_attempts", 0) or 0) + 1
        return {"failed_attempts": failed_attempts, "last_failed_at": now}

    @staticmethod
    def record_success():
        """Başarılı bir girişten sonraki sıfırlanmış state."""
        return {"failed_attempts": 0, "last_failed_at": None}
