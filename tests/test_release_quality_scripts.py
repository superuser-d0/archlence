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


if __name__ == "__main__":
    unittest.main()
