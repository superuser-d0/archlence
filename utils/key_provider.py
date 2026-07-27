"""docs/ROADMAP.md Faz 1 madde 5 — anahtar sağlayıcı arayüzü.

`utils/aead_crypto.py`'nin ihtiyaç duyduğu 32 byte'lık AES-256 anahtarını
NASIL sağlandığından bağımsız bir arayüz arkasına koyar. Gerçek OS keystore
(Windows DPAPI/Credential Manager) entegrasyonu Faz 1 madde 6'nın işi —
Windows'a özel, burada YOK. `FileKeyProvider`, her platformda çalışan
referans implementasyon: anahtarı verilen dosya yoluna ham byte olarak
yazar/okur. NEREYE yazılacağı (platformdirs kullanıcı-veri dizini) Faz 1
madde 4'ün işi — bu sınıf yalnızca çağıranın verdiği bir yolu kullanır.
"""
import os
from abc import ABC, abstractmethod

_KEY_LEN = 32


class KeyProvider(ABC):
    @abstractmethod
    def get_or_create_key(self) -> bytes:
        """32 byte'lık bir AES-256 anahtarı döndürür. İlk çağrıda yoksa
        üretip kalıcı hale getirir; sonraki her çağrıda AYNI anahtarı
        döndürür."""


class FileKeyProvider(KeyProvider):
    """Tek kullanıcılı masaüstü uygulaması varsayımıyla yazılmıştır — eşzamanlı
    süreçlerin aynı anda ilk anahtarı üretmeye çalışması gerçekçi bir tehdit
    değil, bu yüzden burada kilitleme/yarış-durumu koruması yok."""

    def __init__(self, key_path: str):
        self._key_path = key_path

    def get_or_create_key(self) -> bytes:
        if os.path.exists(self._key_path):
            return self._read_existing()

        key = os.urandom(_KEY_LEN)
        directory = os.path.dirname(self._key_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        # 0o600: yalnızca sahibi okuyabilir/yazabilir — anahtar dosyası
        # başka bir yerel kullanıcı tarafından okunabilir olmamalı.
        fd = os.open(self._key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key

    def _read_existing(self) -> bytes:
        with open(self._key_path, "rb") as f:
            key = f.read()
        if len(key) != _KEY_LEN:
            raise ValueError(
                f"Anahtar dosyası bozuk: {len(key)} byte (beklenen {_KEY_LEN})."
            )
        return key
