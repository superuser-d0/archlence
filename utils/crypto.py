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

Dışa dönük davranış BİLEREK AYNI KALDI: decrypt hâlâ "[Şifreli Veri]"'ye,
encrypt hâlâ düz metne fail-open oluyor — ikisi de loglanıyor. Bu, 103
çağrı sitesinin ~55'inin GUI doğrulanmadan davranış değişikliğine
uğramaması için bilinçli bir sınır (bkz. docs/ROADMAP.md Faz 2 "except
ayrımı" notu). Bulk re-encryption migration'ı da BİLEREK YOK — roadmap'in
kendi ayrı maddesi, mevcut satırlar yeniden yazılana kadar eski formatta
kalmaya devam ediyor, hiçbir şey bozulmuyor.
"""
import base64
import binascii
import functools
import os

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad

from utils import aead_crypto

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
        token = aead_crypto.encrypt(str(data), _get_aead_key())
        return _AEAD_PREFIX + token
    except (ValueError, TypeError) as e:
        # aead_crypto.encrypt'in tek gerçekçi hata kaynağı
        # `_require_key_length` (ValueError) — FileKeyProvider her zaman 32
        # byte döndürür, bu yüzden pratikte tetiklenmemesi beklenir. Yine de
        # DAVRANIŞ BİLEREK DEĞİŞMEDİ: eski koddaki gibi düz metne fail-open
        # ediyor, loglanıyor. Bunu raise'e çevirmek Faz 1'in ayrı,
        # GUI-doğrulaması gerektiren bir kararı (bkz. modül docstring'i).
        print(f"[GÜVENLİK] Şifreleme başarısız, veri DÜZ METİN yazılıyor: {e}")
        return str(data)


def _decrypt_legacy_cbc(enc_data, password: str) -> str:
    """Eski AES-256-CBC şemasıyla (sabit şifre, MAC yok) şifrelenmiş veriyi
    çözer. Yeni hiçbir veri artık bu formatta YAZILMIYOR — bu fonksiyon
    yalnızca var olan eski kayıtları okunabilir tutmak için var."""
    try:
        encrypted_payload = base64.b64decode(str(enc_data))
        iv = encrypted_payload[:16]
        ciphertext = encrypted_payload[16:]
        key = _get_key(password)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted_bytes.decode('utf-8')
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        # DAR TUTULDU (bkz. docs/ROADMAP.md Faz 2 "except ayrımı"): gerçek
        # bozuk/kurcalanmış şifreli veri yalnızca bu üç yoldan hata verebilir
        # — bozuk base64 (binascii.Error), yanlış IV/blok uzunluğu ya da
        # geçersiz PKCS7 dolgu (ValueError), ya da çözülen bayt dizisi
        # geçerli UTF-8 değilse (UnicodeDecodeError).
        #
        # DAVRANIŞ BİLEREK DEĞİŞMEDİ: gerçek şifre çözme hatası hâlâ
        # "[Şifreli Veri]" yerine geçen değerine düşüyor (fail-open) — bkz.
        # modül docstring'indeki GUI-doğrulaması gerekçesi.
        print(f"[VERİ BÜTÜNLÜĞÜ] Şifre çözme başarısız — kayıt bozuk/kurcalanmış olabilir: {type(e).__name__}: {e}")
        return "[Şifreli Veri]"


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
            return aead_crypto.decrypt(text[len(_AEAD_PREFIX):], _get_aead_key())
        except (aead_crypto.DecryptionError, ValueError) as e:
            # Aynı fail-open sözleşmesi, aynı yerine geçen değer — eski
            # yoldan ayırt edilemez olması BİLEREK (çağıranların 40'a yakın
            # yeri tek bir "[Şifreli Veri]" davranışına güveniyor).
            print(f"[VERİ BÜTÜNLÜĞÜ] Şifre çözme başarısız — kayıt bozuk/kurcalanmış olabilir: {type(e).__name__}: {e}")
            return "[Şifreli Veri]"

    return _decrypt_legacy_cbc(text, password)
