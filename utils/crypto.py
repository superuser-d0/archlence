"""docs/ROADMAP.md Faz 1 madde 5 — AEAD entegrasyonu.

Bu modül artık ŞEFFAF BİR DAĞITICI: 103 gerçek çağrı sitesi (database/db.py,
services/*.py, main.py) `encrypt()`/`decrypt()`'i AYNI imzayla çağırmaya
devam ediyor, hiçbiri değişmedi. Değişen yalnızca İÇERİDE ne olduğu:

  - `encrypt()` artık HER ZAMAN yeni AEAD şemasını kullanıyor
    (utils/aead_crypto.py: AES-256-GCM, versiyonlu zarf, kurulum başına
    rastgele anahtar — utils/key_provider.py::FileKeyProvider). Eski
    AES-CBC ile YENİ VERİ ARTIK HİÇ ÜRETİLMİYOR; o kod bu yüzden tamamen
    kaldırıldı (aşağıdaki `_decrypt_legacy_cbc` YALNIZCA okuma için kaldı).
  - `decrypt()` değerin başında `AEADv1:` öneki olup olmadığına bakarak
    hangi şemayı kullanacağına karar veriyor. Bu önek base64 alfabesinde
    hiç bulunmayan bir karakter (`:`) içerdiği için eski/yeni ayrımı
    YANLIŞ POZİTİF RİSKİ OLMADAN yapılabiliyor. Önek yoksa eski CBC yolu
    DEĞİŞMEDEN çalışır — eski veri geriye dönük migrationsuz, sonsuza kadar
    okunabilir kalır (bkz. tests/test_crypto.py::LegacyFormatBackwardCompatibilityTest,
    bu dosyanın DEĞİŞTİRİLMEDEN ÖNCEKİ hâliyle üretilmiş gerçek bir blob'a
    karşı test ediyor).

Dışa dönük sözleşme fail-closed'dur: şifreleme/çözme hataları typed exception
olarak çağırana çıkar. Hassas veri hiçbir zaman şifreleme başarısız olduğu için
düz metne dönmez; doğrulanamayan ciphertext de geçerli veri gibi gösterilmez.
Legacy CBC yalnız geriye dönük okuma için tutulur.
"""
import base64
import binascii
import functools
import os

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad

from utils import aead_crypto
from utils.errors import (
    DecryptionError,
    EncryptionError,
    IntegrityVerificationError,
    KeyUnavailableError,
)

# PBKDF2 için sabit tuz (salt). YALNIZCA eski verinin çözülmesi için hâlâ
# gerekli — yeni hiçbir veri artık bu yolla şifrelenmiyor. Bit düzeyinde
# değişmemeleri gerekir, aksi hâlde var olan hiçbir eski kayıt çözülemez.
STATIC_SALT = b"fi" + b"nora_secure_salt_2026"
DEFAULT_PASSWORD = "fi" + "nora_secure_2026"

_AEAD_PREFIX = "AEADv1:"


@functools.lru_cache(maxsize=4)
def _get_key(password: str) -> bytes:
    """PBKDF2 kullanarak şifreden 32 byte'lık güvenli anahtar üretir.
    YALNIZCA eski CBC verisinin çözülmesi için kullanılıyor."""
    return PBKDF2(password, STATIC_SALT, dkLen=32, count=1000000)


@functools.lru_cache(maxsize=1)
def _get_aead_key() -> bytes:
    """Kurulum başına rastgele AES-256 anahtarını lazy olarak çözer ve
    süreç içinde önbelleğe alır (yukarıdaki `_get_key` ile aynı desen).

    BİLEREK import anında DEĞİL, yalnızca gerçek ilk encrypt()/decrypt()
    çağrısında çalışır — `utils.crypto`'yu import eden onlarca test dosyası
    var, salt import etmek gerçek bir anahtar dosyası yaratmamalı (bkz.
    utils/app_paths.py'deki aynı ilke, DB_NAME için de geçerliydi).
    """
    from utils.app_paths import data_dir
    from utils.key_provider import FileKeyProvider

    key_path = os.path.join(data_dir(), "encryption.key")
    return FileKeyProvider(key_path).get_or_create_key()


def encrypt(data, password: str = DEFAULT_PASSWORD) -> str:
    """Veriyi AES-256-GCM (AEAD) ile şifreler; `AEADv1:` önekli base64 döner.

    `password` parametresi artık FONKSİYONEL OLARAK KULLANILMIYOR — yeni
    şema kurulum başına rastgele bir anahtar kullanıyor, string bir
    şifreden türetilmiyor. İmzada kalmasının tek sebebi: 103 çağrı
    sitesinin hepsi `encrypt(str(x), SECRET_KEY)` şeklinde çağırıyor, imza
    değişirse hepsi değişmek zorunda kalırdı. `decrypt()`'in `password`'ü
    hâlâ GERÇEKTEN kullandığına dikkat — o, eski veriyi okumak için hâlâ
    gerekli."""
    if data is None or str(data).strip() == "":
        return data

    try:
        key = _get_aead_key()
    except (OSError, ValueError) as exc:
        raise KeyUnavailableError(
            "Şifreleme anahtarına erişilemedi; veri kaydedilmedi."
        ) from exc
    try:
        token = aead_crypto.encrypt(str(data), key)
    except (ValueError, TypeError) as exc:
        raise EncryptionError(
            "Veri şifrelenemedi; hiçbir düz metin kaydedilmedi."
        ) from exc
    return _AEAD_PREFIX + token


def _decrypt_legacy_cbc(enc_data, password: str) -> str:
    """Eski AES-256-CBC şemasıyla (sabit şifre, MAC yok) şifrelenmiş veriyi
    çözer. Yeni hiçbir veri artık bu formatta YAZILMIYOR — bu fonksiyon
    yalnızca var olan eski kayıtları okunabilir tutmak için var."""
    try:
        encrypted_payload = base64.b64decode(str(enc_data), validate=True)
        iv = encrypted_payload[:16]
        ciphertext = encrypted_payload[16:]
        key = _get_key(password)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted_bytes.decode('utf-8')
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise DecryptionError(
            "Legacy şifreli veri çözülemedi veya biçimi geçersiz."
        ) from exc


def decrypt(enc_data, password: str = DEFAULT_PASSWORD) -> str:
    """`encrypt()`'in ürettiği AEAD zarfını YA DA eski CBC formatındaki
    (migration öncesi) veriyi çözer — format `AEADv1:` önekinden anlaşılır.
    Bu önek base64 alfabesinde hiç bulunmayan `:` içerir, yani eski/yeni
    ayrımı yanlış pozitif riski olmadan yapılabilir."""
    if enc_data is None or str(enc_data).strip() == "":
        return enc_data

    text = str(enc_data)
    if text.startswith(_AEAD_PREFIX):
        try:
            key = _get_aead_key()
        except (OSError, ValueError) as exc:
            raise KeyUnavailableError(
                "Şifreleme anahtarına erişilemedi; veri açılamadı."
            ) from exc
        try:
            return aead_crypto.decrypt(text[len(_AEAD_PREFIX):], key)
        except aead_crypto.DecryptionError as exc:
            raise IntegrityVerificationError(
                "Şifreli verinin bütünlüğü doğrulanamadı."
            ) from exc
        except ValueError as exc:
            raise KeyUnavailableError(
                "Şifreleme anahtarı geçersiz; veri açılamadı."
            ) from exc

    return _decrypt_legacy_cbc(text, password)
