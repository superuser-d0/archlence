"""docs/ROADMAP.md Faz 1 madde 5. `FileKeyProvider` — anahtarın NEREYE
yazılacağına (platformdirs, Faz 1 madde 4) karar vermeden, verilen bir
yola nasıl kalıcı anahtar yazılıp okunacağını doğrular."""
import os
import stat
import tempfile
import unittest

from utils.key_provider import FileKeyProvider


class FileKeyProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.key_path = os.path.join(self.tmpdir, "secret.key")

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmpdir, topdown=False):
            for name in files:
                os.chmod(os.path.join(root, name), 0o700)
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.tmpdir)

    def test_first_call_creates_a_32_byte_key(self):
        provider = FileKeyProvider(self.key_path)
        key = provider.get_or_create_key()
        self.assertEqual(len(key), 32)
        self.assertTrue(os.path.exists(self.key_path))

    def test_second_call_returns_the_same_key(self):
        provider = FileKeyProvider(self.key_path)
        first = provider.get_or_create_key()
        second = provider.get_or_create_key()
        self.assertEqual(first, second)

    def test_a_fresh_provider_instance_reads_the_persisted_key(self):
        """Kalıcılığın gerçek sınavı: bellek içi durum değil, dosyanın
        kendisi tutuluyor mu — yeni bir provider nesnesi aynı anahtarı
        okuyabilmeli."""
        first_key = FileKeyProvider(self.key_path).get_or_create_key()
        second_key = FileKeyProvider(self.key_path).get_or_create_key()
        self.assertEqual(first_key, second_key)

    def test_different_key_paths_get_different_random_keys(self):
        key_a = FileKeyProvider(self.key_path).get_or_create_key()
        key_b = FileKeyProvider(
            os.path.join(self.tmpdir, "other.key")
        ).get_or_create_key()
        self.assertNotEqual(key_a, key_b)

    def test_creates_missing_parent_directories(self):
        nested_path = os.path.join(self.tmpdir, "a", "b", "c", "secret.key")
        provider = FileKeyProvider(nested_path)
        key = provider.get_or_create_key()
        self.assertEqual(len(key), 32)

    def test_corrupted_key_file_raises(self):
        with open(self.key_path, "wb") as f:
            f.write(b"too-short")
        provider = FileKeyProvider(self.key_path)
        with self.assertRaises(ValueError):
            provider.get_or_create_key()

    def test_key_file_is_owner_only_readable(self):
        provider = FileKeyProvider(self.key_path)
        provider.get_or_create_key()
        mode = stat.S_IMODE(os.stat(self.key_path).st_mode)
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
