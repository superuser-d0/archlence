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
import tempfile
from abc import ABC, abstractmethod

_KEY_LEN = 32


class KeyProvider(ABC):
    @abstractmethod
    def get_or_create_key(self) -> bytes:
        """32 byte'lık bir AES-256 anahtarı döndürür. İlk çağrıda yoksa
        üretip kalıcı hale getirir; sonraki her çağrıda AYNI anahtarı
        döndürür."""


class FileKeyProvider(KeyProvider):
    """Anahtarı verilen dosya yolunda tutar; ilk çağrıda ATOMİK olarak üretir.

    Anahtar oluşturma `O_CREAT | O_EXCL` ile yapılır — yani "yoksa oluştur"
    kontrolü ile yazma İŞLETİM SİSTEMİ SEVİYESİNDE tek bir atomik adımdır.
    Bu şart: aksi hâlde `exists()` kontrolü ile yazma arasında iki süreç
    yarışabilir, ikisi de FARKLI rastgele anahtar üretir ve ikincisinin
    yazması birincisininkini sessizce ezerdi. Birinci sürecin o anahtarla
    şifrelediği her şey KALICI OLARAK kurtarılamaz hâle gelirdi — atılan
    anahtarın hiçbir yerde yedeği yok.

    Bu senaryo teorik değil: uygulamanın süreç düzeyinde tek-örnek koruması
    yok, dolayısıyla taze bir kurulumda masaüstü kısayoluna iki kez
    tıklamak yeterli. Sıradan bir kullanıcı davranışı, saldırı değil.

    Yarışı KAYBEDEN taraf hata vermez: kazananın yazdığı anahtarı okur — iki
    süreç de aynı anahtarla devam eder.

    Yalnızca `O_EXCL` YETMEZ; bu ampirik olarak doğrulandı. `O_EXCL` dosyayı
    atomik oluşturur ama dosya, oluşturulma anı ile içeriğin yazılması
    arasında kısa bir süre BOŞ olarak görünür. 16 süreçle yapılan gerçek
    eşzamanlılık testinde yarışı kaybedenler tam o aralıkta okuyup
    "Anahtar dosyası bozuk: 0 byte" ile patladı — yani `O_EXCL` tek başına
    "sessiz anahtar imhası"nı "açılışta çökme"ye çevirmekten öteye gitmedi.

    Bu yüzden içerik ÖNCE geçici bir dosyaya yazılır (fsync ile diske
    indirilir), sonra `os.link` ile hedef yola atomik olarak bağlanır.
    `os.link` hedef varsa FileExistsError fırlatır ve asla üzerine yazmaz.
    Sonuç: hedef yol ya HİÇ yoktur ya da TAM içerikle vardır — yarı yazılmış
    bir ara durum hiçbir okuyucuya görünmez.
    """

    def __init__(self, key_path: str):
        self._key_path = key_path

    def get_or_create_key(self) -> bytes:
        if os.path.exists(self._key_path):
            return self._read_existing()

        directory = os.path.dirname(self._key_path) or "."
        os.makedirs(directory, exist_ok=True)

        key = os.urandom(_KEY_LEN)
        # Geçici dosya HEDEFLE AYNI DİZİNDE olmalı: os.link yalnızca aynı
        # dosya sistemi içinde çalışır.
        #
        # 0o600 yalnızca POSIX'te etkilidir; Windows NTFS ACL'lerinde
        # karşılığı yoktur. Orada koruma, %LOCALAPPDATA%'nın kendi
        # kullanıcı-profili ACL varsayılanlarından gelir (bkz.
        # utils/app_paths.py::data_dir) — bu satır Windows'ta ek bir şey
        # yapmaz.
        # mkstemp: hem SÜREÇLER hem de AYNI SÜREÇTEKİ THREAD'ler arasında
        # benzersiz ad üretir ve dosyayı 0o600 ile açar. Adı yalnızca
        # os.getpid()'den türetmek yetmezdi — bu uygulama yoğun biçimde
        # thread kullanıyor (açılışta kripto ısıtma thread'i ile veri
        # thread'i ilk şifre çözmeyi aynı anda tetikleyebilir) ve aynı
        # süreçteki iki thread aynı geçici adı seçip çarpışırdı.
        fd, tmp_path = tempfile.mkstemp(
            dir=directory, prefix=os.path.basename(self._key_path) + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(key)
                f.flush()
                # Anahtar, hedef yola bağlanmadan ÖNCE fiilen diskte olmalı;
                # aksi hâlde ani bir güç kesintisi "dosya var ama içi boş"
                # durumunu kalıcılaştırabilirdi.
                os.fsync(f.fileno())
            try:
                os.link(tmp_path, self._key_path)
            except FileExistsError:
                # Yarışı başka bir süreç kazandı. Onun anahtarı geçerli
                # olandır ve os.link sıralaması sayesinde TAM yazılmıştır.
                return self._read_existing()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return key

    def _read_existing(self) -> bytes:
        with open(self._key_path, "rb") as f:
            key = f.read()
        if len(key) != _KEY_LEN:
            raise ValueError(
                f"Anahtar dosyası bozuk: {len(key)} byte (beklenen {_KEY_LEN})."
            )
        return key
