import unittest
from pathlib import Path

from scripts.check_version_consistency import main as check_version
from scripts.inspect_package_contents import inspect_files


class ReleaseQualityScriptsTest(unittest.TestCase):
    def test_repository_version_metadata_is_consistent(self):
        check_version()

    def test_package_scan_rejects_user_data_and_embedded_secrets(self):
        findings = inspect_files([
            ("finance.db", b""),
            ("app.bin", b"/home/cem/Documents/archlence"),
            ("other.bin", b"ghp_" + b"A" * 40),
        ])
        self.assertTrue(any(item.startswith("forbidden-name:") for item in findings))
        self.assertTrue(any(item.startswith("developer-home:") for item in findings))
        self.assertTrue(any(item.startswith("github-token:") for item in findings))

    def test_package_scan_accepts_normal_binary(self):
        self.assertEqual(
            inspect_files([("Archlence.exe", b"MZ\\x00ordinary-content")]),
            [],
        )

    def test_spec_excludes_kivy_debug_module_data(self):
        spec = Path("archlence.spec").read_text(encoding="utf-8")
        self.assertIn('startswith("kivy_install/modules/")', spec)

    def test_spec_declares_the_lazy_pywin32_import_the_file_chooser_needs(self):
        """`win32timezone` gizli import olarak DURMALI.

        Kivy'nin dosya seçicisi gizli-dosya bayrağını okumak için
        `win32file.GetFileAttributesExW` çağırıyor; pywin32 o çağrının
        içinde `win32timezone`'u TEMBEL import ediyor ve PyInstaller'ın
        statik analizi onu göremiyor. Gerçek Windows 11 makinesinde
        ölçüldü: Ayarlar -> Geri Yükle dosya seçicisini açmak uygulamanın
        tamamını düşürüyordu ("No module named 'win32timezone'").

        Bu satır silinirse hata sessizce geri gelir — Linux'ta hiçbir şey
        kırılmaz, Windows paketi de sorunsuz derlenir; yalnız kullanıcı
        çöker. Bu yüzden kapı burada, her platformda koşan bir testte.
        Paketin içeriğine bakan tamamlayıcı kapı `build-windows.yml`
        içindeki "Paketleme bütünlüğü" adımında.
        """
        spec = Path("archlence.spec").read_text(encoding="utf-8")
        self.assertIn('"win32timezone"', spec)


if __name__ == "__main__":
    unittest.main()
