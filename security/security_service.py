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
    """Girdi tarafının TEK politika kaynağı.

    Argon2id ve `LoginThrottle` yalnızca HASH'İ ve DENEME HIZINI korur. Girdi
    kendisi kısa ve dar bir karakter kümesindeyse arama uzayı küçük kalır ve
    ikisi de anlamsızlaşır: eski politika 4 karakter + 1 büyük harf + 1 özel
    karakter istiyordu, yani `A!!!` geçerli bir parolaydı.

    Politika: en az 12 karakter, büyük harf, küçük harf, rakam ve özel
    karakterin HEPSİ.

    BAŞ/SON BOŞLUK AÇIKÇA REDDEDİLİR, sessizce kırpılmaz. Eski davranış
    çağıranlarda `.strip()` idi: kullanıcı bir parola yazıyor, uygulama BAŞKA
    bir parolayı kaydediyordu ve bunu ona hiç söylemiyordu. İki dürüst seçenek
    vardı — ham metni tutarlı kullanmak ya da boşluğu reddetmek; ikincisi
    seçildi, çünkü kullanıcı görünmeyen bir karakterin parolasının parçası
    olduğunu doğrulayamaz.

    `setup_pin`, `_apply_new_pin` (main.py), zorunlu yenileme ve sıfırlama
    sonrası yeniden kurulum — hepsi buradan geçer.
    """

    MIN_LENGTH = 12

    # ÜST SINIR DA SÖZLEŞMENİN PARÇASI. Politikada üst sınır yokken arayüz
    # alanları farklı `max_text_length` taşıyordu — parola değiştirme
    # diyaloğunda 64, kurulum ve giriş alanlarında 32. KivyMD 1.2.0 bu değeri
    # KESMİYOR, yalnız alanı hata durumuna sokuyor; yani kilitlenme değildi
    # ama politika "geçerli" derken arayüz kırmızı gösterebiliyordu. Tek sayı,
    # tek kaynak: üç alan da bunu gösterir, politika da bunu uygular.
    #
    # 64: Argon2id girdi uzunluğundan bağımsız çalışır, yani sınır güvenlik
    # değil kullanılabilirlik/tutarlılık kararıdır. Parola yöneticilerinin
    # ürettiği uzun parolalar rahatça sığar.
    MAX_LENGTH = 64

    SPECIAL_CHARS = ".,;:!?-_@#$%^&*()+=/\\|~`'\"<>[]{}"

    #: Üretilebilecek TÜM hata metinleri. `translate()`'e verilebilecek Türkçe
    #: kaynak anahtarlarıdır ve i18n kapısı bu listeye bakar; buraya bir metin
    #: eklenip `ui/i18n.py`'ye eklenmezse kapı kırılır.
    TOO_SHORT = "Şifre en az 12 karakter olmalıdır."
    TOO_LONG = "Şifre en fazla 64 karakter olabilir."
    NO_UPPER = "Şifre en az 1 büyük harf içermelidir."
    NO_LOWER = "Şifre en az 1 küçük harf içermelidir."
    NO_DIGIT = "Şifre en az 1 rakam içermelidir."
    NO_SPECIAL = "Şifre en az 1 özel karakter (örn. . veya ,) içermelidir."
    HAS_EDGE_WHITESPACE = "Şifre başında veya sonunda boşluk içeremez."

    #: Arayüzdeki yardım metni — politikanın kendisiyle aynı kaynaktan.
    REQUIREMENTS = (
        "12-64 karakter, 1 büyük harf, 1 küçük harf, 1 rakam ve 1 özel karakter"
    )

    MESSAGES = (
        TOO_SHORT, TOO_LONG, NO_UPPER, NO_LOWER, NO_DIGIT, NO_SPECIAL,
        HAS_EDGE_WHITESPACE,
    )

    @staticmethod
    def validate(password):
        """(is_valid, error_message) döndürür.

        `error_message` geçerliyse None, değilse `MESSAGES` içindeki Türkçe
        kaynak metinlerden biri.
        """
        password = password or ""
        if password != password.strip():
            return False, PasswordPolicy.HAS_EDGE_WHITESPACE
        if len(password) < PasswordPolicy.MIN_LENGTH:
            return False, PasswordPolicy.TOO_SHORT
        if len(password) > PasswordPolicy.MAX_LENGTH:
            return False, PasswordPolicy.TOO_LONG
        if not any(c.isupper() for c in password):
            return False, PasswordPolicy.NO_UPPER
        if not any(c.islower() for c in password):
            return False, PasswordPolicy.NO_LOWER
        if not any(c.isdigit() for c in password):
            return False, PasswordPolicy.NO_DIGIT
        if not any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            return False, PasswordPolicy.NO_SPECIAL
        return True, None

    @staticmethod
    def is_compliant(password):
        """Yalnız evet/hayır — zorunlu yenileme kararı için."""
        return PasswordPolicy.validate(password)[0]


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
