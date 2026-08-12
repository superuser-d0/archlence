"""Yeniden adlandırmadan önceki iki tanımlayıcı BAYT BAYT aynı kalmalı.

NEDEN VAR: uygulamanın Archlence'tan önceki adı, kod tabanında düz metin
geçmesin diye `utils/app_paths.py` içinde base64 ile saklanıyor. Bu bir
güvenlik önlemi DEĞİL — isim hijyeni. Ama kodlanmış bir sabitin yanlışlıkla
bozulması, düz metin bir sabitinkinden çok daha sessiz olur: kimse
`Zmlub3Jh` dizesine bakıp "bu yanlış" diyemez.

O yüzden beklenen değerler BURADA, açıkça yazılı. İkisinin de değişmesi
YASAK ve sebepleri farklı:

  * `LEGACY_CBC_PASSWORD` — v0.0.9 öncesi AES-256-CBC ile şifrelenmiş
    kayıtların TEK çözme anahtarı. Değişirse eski profillerdeki tutar ve
    açıklamalar kalıcı olarak okunamaz hâle gelir. Geri dönüşü yoktur.

  * `LEGACY_CONFIG_FILENAME` — diskte duran eski ayar dosyasının adı.
    Değişirse o dosya bulunamaz ve kullanıcının ayarları göç etmez; hata
    da vermez, sessizce kaybolur.

Bu test kodlamayı çözüp beklenenle karşılaştırıyor. Kodlanmış satır
değişirse burası kırılır — kurulmak istenen güvenlik ağı budur.
"""

import base64
import unittest

from utils.app_paths import LEGACY_CBC_PASSWORD, LEGACY_CONFIG_FILENAME

# Beklenen değerler base64 olarak yazılı: bu dosyanın kendisi de "eski ad düz
# metin geçmesin" kuralına uyuyor. Çözülmüş hâlleri testlerde karşılaştırılıyor.
_EXPECTED_CBC_PASSWORD = base64.b64decode("Zmlub3JhX3NlY3VyZV8yMDI2").decode("ascii")
_EXPECTED_CONFIG_FILENAME = base64.b64decode("Zmlub3JhX2NvbmZpZy5qc29u").decode("ascii")


class LegacyIdentifiersAreFrozen(unittest.TestCase):

    def test_cbc_password_is_unchanged(self):
        """Eski kayıtların çözme anahtarı — değişirse veri okunamaz olur."""
        self.assertEqual(LEGACY_CBC_PASSWORD, _EXPECTED_CBC_PASSWORD)

    def test_config_filename_is_unchanged(self):
        """Göç edilecek eski ayar dosyasının adı — değişirse göç sessizce kaçar."""
        self.assertEqual(LEGACY_CONFIG_FILENAME, _EXPECTED_CONFIG_FILENAME)

    def test_database_secret_key_still_resolves_to_the_legacy_password(self):
        """`database.db.SECRET_KEY` aynı değeri taşımalı.

        Yüzlerce çağrı yeri bu adı kullanıyor; ortak sabite bağlanırken
        değerin kayması, eski veriyi okuyan her yolu aynı anda bozardı.
        """
        from database.db import SECRET_KEY

        self.assertEqual(SECRET_KEY, _EXPECTED_CBC_PASSWORD)

    def test_legacy_ciphertext_written_with_the_old_scheme_still_decrypts(self):
        """ASIL GARANTİ: eski şemayla yazılmış bir kayıt hâlâ çözülebiliyor.

        Sabitleri karşılaştırmak yetmez — asıl soru, o parolanın gerçekten
        eski biçimi açıp açmadığı. Şifreli metin burada, testin içinde, eski
        şemanın kendisiyle üretiliyor (`tests/test_crypto_migration_service.py`
        ile aynı kalıp); üretim kodu test için genişletilmiyor.
        """
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
        from Crypto.Util.Padding import pad

        from utils.crypto import STATIC_SALT, _decrypt_legacy_cbc

        iv = bytes(range(16))
        key = PBKDF2(LEGACY_CBC_PASSWORD, STATIC_SALT, dkLen=32, count=1_000_000)
        payload = iv + AES.new(key, AES.MODE_CBC, iv).encrypt(
            pad("1234.56".encode("utf-8"), 16))
        token = base64.b64encode(payload).decode("ascii")

        self.assertEqual(
            _decrypt_legacy_cbc(token, LEGACY_CBC_PASSWORD), "1234.56")


if __name__ == "__main__":
    unittest.main()
