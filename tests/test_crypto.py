import io
import sys
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

# Proje kökünü (tests/'in bir üstü) sys.path'e ekle ki utils.crypto bulunsun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.crypto import DEFAULT_PASSWORD, encrypt, decrypt

def run_crypto_test():
    original_text = "Market Alışverişi - 150 TL"
    test_password = DEFAULT_PASSWORD
    print("🔐 CRYPTO MODULE TEST")
    print("-" * 50)
    print(f"Original String : {original_text}")
    print(f"Test Password   : {test_password}")
    
    # 2. Encrypt
    encrypted_text = encrypt(original_text, test_password)
    print("\n[ENCRYPTING...]")
    print(f"Encrypted Output (Base64 IV:Ciphertext):\n{encrypted_text}")
    
    # 3. Decrypt
    decrypted_text = decrypt(encrypted_text, test_password)
    print("\n[DECRYPTING...]")
    print(f"Decrypted Output: {decrypted_text}")
    
    # 4. Boolean Check
    print("\n[VERIFICATION]")
    if original_text == decrypted_text:
        print("✅ SUCCESS: The decrypted string matches the original exactly.")
    else:
        print("❌ FAILED: The decrypted string does NOT match the original.")
    print("-" * 50)


class CryptoCompatibilityTest(unittest.TestCase):
    def test_current_cipher_round_trip(self):
        """Artık varsayılan olarak YENİ (AEAD) şemayı tatbik ediyor —
        eskisi gibi CBC'yi değil. Eski şemanın round-trip'i ayrı bir testte
        (LegacyFormatBackwardCompatibilityTest), gerçek bir eski blob'a
        karşı doğrulanıyor."""
        value = "Archlence güvenli veri"
        self.assertEqual(decrypt(encrypt(value)), value)

    def test_new_ciphertext_is_marked_with_the_aead_prefix(self):
        token = encrypt("herhangi bir veri")
        self.assertTrue(token.startswith("AEADv1:"))


class LegacyFormatBackwardCompatibilityTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 1 madde 5'in asıl noktası: `encrypt()` artık
    hiçbir zaman eski AES-CBC formatını ÜRETMİYOR, ama var olan eski veri
    SONSUZA KADAR okunabilir kalmalı — migrationsuz, hiçbir kullanıcı
    verisi kaybolmadan.

    Aşağıdaki blob TEMİZ BİR ÜRETİMDİR: bu modülün AEAD'e geçmeden ÖNCEKİ
    hâliyle, gerçekten çalıştırılarak üretildi
    (`encrypt("Market Alışverişi - 150,50 TL", DEFAULT_PASSWORD)`) — bir
    varsayımla ya da bu dosyanın YENİ kodunu kullanarak yeniden inşa
    EDİLMEDİ. Bu, testin gerçekten "eski format hâlâ okunuyor mu"yu
    doğrulamasını sağlıyor; kendi kendini doğrulayan dairesel bir test
    değil."""

    _REAL_LEGACY_BLOB = (
        "jv0+2I14CybLEXqpyXgmlTsjBp4lzc2RvRdFvElllXp112r2xpjPBBMAenlFJba"
        "FtQMj0ojOQ9L1Byg2+tBv5g=="
    )
    _REAL_LEGACY_PLAINTEXT = "Market Alışverişi - 150,50 TL"

    def test_pre_existing_legacy_ciphertext_still_decrypts_correctly(self):
        result = decrypt(self._REAL_LEGACY_BLOB, DEFAULT_PASSWORD)
        self.assertEqual(result, self._REAL_LEGACY_PLAINTEXT)

    def test_legacy_ciphertext_has_no_aead_prefix(self):
        """Format ayrımının GÜVENLİ olmasının sebebi: base64 alfabesi hiç
        `:` içermez, yani eski hiçbir gerçek şifreli metin yanlışlıkla
        `AEADv1:` ile başlayamaz."""
        self.assertFalse(self._REAL_LEGACY_BLOB.startswith("AEADv1:"))


class NarrowedExceptHandlingTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 2 "except ayrımı" + Faz 1 madde 5. DAVRANIŞ
    BİLEREK DEĞİŞMEDİ — gerçek şifreleme/çözme hatası hâlâ aynı fail-open
    değerine düşüyor (decrypt -> "[Şifreli Veri]", encrypt -> düz metin),
    format (eski CBC / yeni AEAD) fark etmeksizin. Değişen: (1) loglanıyor,
    (2) yalnızca gerçekten olabilecek hata tipleri yakalanıyor — alakasız
    bir programlama hatası artık bu yoldan sessizce yutulmuyor."""

    def test_corrupted_ciphertext_still_falls_back_gracefully(self):
        """Gerçek bozuk/kurcalanmış veri (geçersiz base64, AEADv1: öneki
        yok -> eski yol) davranışı korunmalı — hâlâ çöküş yok, hâlâ yerine
        geçen değer."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = decrypt("bu-gecerli-bir-base64-degil-!!!")
        self.assertEqual(result, "[Şifreli Veri]")
        self.assertIn("VERİ BÜTÜNLÜĞÜ", buf.getvalue())

    def test_truncated_ciphertext_still_falls_back_gracefully(self):
        """16 byte'tan kısa (IV'siz) bir yük geçerli base64 olabilir ama
        AES.new'e geçersiz IV verir — ValueError, hâlâ yakalanmalı (eski
        yol, AEADv1: öneki yok)."""
        import base64
        short_payload = base64.b64encode(b"kisa").decode("utf-8")
        result = decrypt(short_payload)
        self.assertEqual(result, "[Şifreli Veri]")

    def test_corrupted_new_format_ciphertext_also_falls_back_gracefully(self):
        """Aynı sözleşme YENİ (AEAD) yol için de geçerli — kurcalanmış bir
        AEADv1: zarfı da sessizce '[Şifreli Veri]'ye düşmeli, çökmemeli."""
        buf = io.StringIO()
        token = encrypt("hassas veri")
        tampered = token[:-4] + "XXXX"  # base64 kuyruğunu boz
        with redirect_stdout(buf):
            result = decrypt(tampered)
        self.assertEqual(result, "[Şifreli Veri]")
        self.assertIn("VERİ BÜTÜNLÜĞÜ", buf.getvalue())

    def test_unrelated_bug_inside_legacy_decrypt_still_propagates(self):
        """Eski CBC yolunun İÇİNDE, şifre çözmeyle ilgisi olmayan bir hata
        (ör. burada simüle edilen bir programlama hatası) '[Şifreli Veri]'
        arkasına gizlenip sessizce yutulmamalı. `unpad` yalnızca
        `_decrypt_legacy_cbc` içinde çağrıldığı için gerçek eski formatlı
        bir girdiye karşı çalıştırılıyor — yeni format bu fonksiyona hiç
        uğramıyor."""
        with mock.patch(
            "utils.crypto.unpad", side_effect=RuntimeError("beklenmedik bug")
        ):
            with self.assertRaises(RuntimeError):
                decrypt(
                    LegacyFormatBackwardCompatibilityTest._REAL_LEGACY_BLOB,
                    DEFAULT_PASSWORD,
                )

    def test_unrelated_bug_inside_aead_decrypt_still_propagates(self):
        """Aynı invaryant, YENİ (AEAD) yol için."""
        token = encrypt("test verisi")
        with mock.patch(
            "utils.crypto.aead_crypto.decrypt",
            side_effect=RuntimeError("beklenmedik bug"),
        ):
            with self.assertRaises(RuntimeError):
                decrypt(token)

    def test_unrelated_bug_inside_encrypt_now_propagates(self):
        with mock.patch(
            "utils.crypto.aead_crypto.encrypt",
            side_effect=RuntimeError("beklenmedik bug"),
        ):
            with self.assertRaises(RuntimeError):
                encrypt("test verisi")

    def test_encrypt_failure_still_falls_back_to_plaintext_and_logs(self):
        """DAVRANIŞ BİLEREK DEĞİŞMEDİ (Faz 1'in kalan konusu — fail-open'ı
        raise'e çevirmek ayrı, GUI-doğrulaması gerektiren bir karar) — ama
        artık en azından loglanıyor. Gerçekçi bir başarısızlık senaryosu
        kullanılıyor: `_get_aead_key`'in yanlış uzunlukta bir anahtar
        döndürmesi, `aead_crypto.encrypt`'in kendi `_require_key_length`
        korumasını GERÇEKTEN tetikler — mock'lanan iç bir detay değil."""
        buf = io.StringIO()
        with mock.patch(
            "utils.crypto._get_aead_key", return_value=b"cok-kisa"
        ), redirect_stdout(buf):
            result = encrypt("hassas veri")
        self.assertEqual(result, "hassas veri")
        self.assertIn("GÜVENLİK", buf.getvalue())


class AeadKeyLazyResolutionTest(unittest.TestCase):
    """utils/app_paths.py'nin kendi ilkesiyle aynı: `utils.crypto`'yu salt
    import etmek (ya da hatta boş/None veri için encrypt/decrypt çağırmak)
    gerçek bir anahtar dosyası YARATMAMALI. Onlarca test dosyası bu modülü
    dolaylı olarak import ediyor; import'un kendisi bir yan etki üretirse
    her test çalıştırması geliştiricinin gerçek ev dizinine dokunurdu
    (run_tests.py'nin XDG_DATA_HOME sandbox'ı bunun ikinci bir güvencesi,
    birincisi değil — birincisi bu davranışın kendisi)."""

    def test_empty_and_none_values_never_touch_the_key_provider(self):
        with mock.patch("utils.crypto._get_aead_key") as get_key:
            self.assertIsNone(encrypt(None))
            self.assertEqual(encrypt(""), "")
            self.assertIsNone(decrypt(None))
            self.assertEqual(decrypt(""), "")
        get_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()
