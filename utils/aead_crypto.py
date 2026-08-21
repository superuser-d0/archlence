"""docs/ROADMAP.md Faz 1 madde 5 — AEAD şifreleme çekirdeği.

AES-256-GCM tabanlı, versiyonlu, yetkilendirilmiş (authenticated) şifreleme.
`utils/crypto.py`'deki eski AES-CBC şemasının (sabit anahtar, MAC yok,
fail-open) yerini alacak — ama bu dosya henüz hiçbir çağrı sitesine
BAĞLANMADI. Gerçek geçiş, anahtarın nerede saklanacağını (platformdirs,
Faz 1 madde 4) ve mevcut `finance.db` verisinin nasıl migrate edileceğini
gerektiriyor; ikisi de ayrı, sonraki bir adım. Bu dosya yalnızca saf
şifreleme mantığını içerir — GUI'ye veya anahtar saklama yerine dair hiçbir
varsayım yok, tamamen bağımsız test edilebilir.

Eski `utils/crypto.py::decrypt()`'in aksine burada FAIL-OPEN YOK: her
başarısızlık `DecryptionError` fırlatır. Bu bilinçli bir tasarım kararı —
roadmap'in kendi maddesi ("On decrypt failure, surface the error — don't
fail open"). Çağıran taraf bunu nasıl karşılayacağına kendi kararıyla
karar verir.
"""
import base64
import binascii
import os

from Crypto.Cipher import AES

_VERSION = 1
_ALGO_AES_256_GCM = 1
_HEADER_LEN = 2  # version + algo id
_NONCE_LEN = 12
_TAG_LEN = 16
_KEY_LEN = 32  # AES-256


class DecryptionError(Exception):
    """Şifre çözme başarısız: yanlış anahtar, bozuk/kurcalanmış veri, ya da
    tanınmayan bir versiyon/algoritma. Fail-open YOK — çağıran gerçek
    hatayı görür."""


def _require_key_length(key: bytes) -> None:
    if len(key) != _KEY_LEN:
        raise ValueError(f"Anahtar {_KEY_LEN} byte olmalı, {len(key)} byte verildi.")


def encrypt(plaintext: str, key: bytes) -> str:
    """`plaintext`'i AES-256-GCM ile şifreler; base64(version|algo|nonce|tag|ciphertext) döndürür."""
    _require_key_length(key)
    nonce = os.urandom(_NONCE_LEN)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
    envelope = bytes([_VERSION, _ALGO_AES_256_GCM]) + nonce + tag + ciphertext
    return base64.b64encode(envelope).decode("utf-8")


def decrypt(token: str, key: bytes) -> str:
    """`encrypt()`'in ürettiği zarfı çözer. Herhangi bir tutarsızlıkta
    (kurcalanmış zarf, yanlış anahtar, tanınmayan versiyon/algoritma)
    `DecryptionError` fırlatır — sessizce yerine geçen bir değer YOK."""
    _require_key_length(key)

    try:
        envelope = base64.b64decode(token, validate=True)
    except (binascii.Error, ValueError) as e:
        raise DecryptionError(f"Geçersiz base64: {e}") from e

    if len(envelope) < _HEADER_LEN + _NONCE_LEN + _TAG_LEN:
        raise DecryptionError("Zarf çok kısa — bozuk veya kurcalanmış veri.")

    version, algo_id = envelope[0], envelope[1]
    if version != _VERSION:
        raise DecryptionError(f"Bilinmeyen zarf versiyonu: {version}")
    if algo_id != _ALGO_AES_256_GCM:
        raise DecryptionError(f"Bilinmeyen algoritma id: {algo_id}")

    body = envelope[_HEADER_LEN:]
    nonce, tag, ciphertext = (
        body[:_NONCE_LEN],
        body[_NONCE_LEN:_NONCE_LEN + _TAG_LEN],
        body[_NONCE_LEN + _TAG_LEN:],
    )

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext_bytes = cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError as e:


        raise DecryptionError(
            f"Kimlik doğrulama başarısız — yanlış anahtar ya da kurcalanmış veri: {e}"
        ) from e

    try:
        return plaintext_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise DecryptionError(f"Çözülen veri geçerli UTF-8 değil: {e}") from e
