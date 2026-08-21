"""docs/ROADMAP.md Faz 1 madde 5. `FileKeyProvider` — anahtarın NEREYE
yazılacağına (platformdirs, Faz 1 madde 4) karar vermeden, verilen bir
yola nasıl kalıcı anahtar yazılıp okunacağını doğrular."""
import os
import stat
import tempfile
import threading
import unittest
from unittest import mock

from utils.errors import KeyUnavailableError
from utils.key_provider import (
    DpapiKeyProvider,
    FileKeyProvider,
    KeyringKeyProvider,
    MigratingKeyProvider,
    KeyProtectionStatus,
    create_platform_key_provider,
)


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
        with self.assertRaises(KeyUnavailableError):
            provider.get_or_create_key()

    def test_concurrent_first_creation_yields_one_shared_key(self):
        """Uygulamanın süreç düzeyinde tek-örnek koruması yok, yani taze bir
        kurulumda kısayola iki kez tıklamak iki süreci aynı anda anahtar
        üretmeye sokar — sıradan kullanıcı davranışı, saldırı değil.

        Bu test iki ayrı hatayı birden kilitler:
          1) Yalnızca `exists()` + yaz: iki süreç FARKLI anahtar üretir,
             ikincisi birincisinin üzerine yazar; birincinin şifrelediği her
             şey KALICI OLARAK kurtarılamaz hâle gelir.
          2) Yalnızca `O_EXCL`: dosya, oluşturulma ile içeriğin yazılması
             arasında kısa süre BOŞ görünür; yarışı kaybeden o aralıkta okur
             ve "Anahtar dosyası bozuk: 0 byte" ile patlar. (Bu, gerçek
             16-süreçli bir çalıştırmada ampirik olarak gözlendi — teorik
             değil.)
        Doğru davranış: tüm süreçler AYNI, TAM anahtarı döndürür.
        """
        import concurrent.futures

        barrier = threading.Barrier(8)

        def create():
            barrier.wait()
            return FileKeyProvider(self.key_path).get_or_create_key()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            keys = [f.result() for f in
                    [pool.submit(create) for _ in range(8)]]

        with open(self.key_path, "rb") as f:
            on_disk = f.read()

        self.assertEqual(len(set(keys)), 1, "süreçler farklı anahtar üretti")
        self.assertEqual(len(on_disk), 32)
        self.assertTrue(all(k == on_disk for k in keys),
                        "dönen anahtar diskteki anahtarla aynı değil")

    def test_no_temp_files_are_left_behind(self):
        """Atomik bağlama geçici bir dosya üzerinden yapılıyor; o dosya her
        durumda temizlenmeli, anahtar dizininde artık kalmamalı."""
        FileKeyProvider(self.key_path).get_or_create_key()
        leftovers = [n for n in os.listdir(self.tmpdir) if ".tmp." in n]
        self.assertEqual(leftovers, [])

    @unittest.skipIf(
        os.name == "nt",
        "POSIX mod bitleri Windows'ta anlam taşımıyor — aşağıdaki Windows "
        "testine bakın.",
    )
    def test_key_file_is_owner_only_readable(self):
        provider = FileKeyProvider(self.key_path)
        provider.get_or_create_key()
        mode = stat.S_IMODE(os.stat(self.key_path).st_mode)
        self.assertEqual(mode, 0o600)

    @unittest.skipUnless(os.name == "nt", "yalnızca Windows davranışı")
    def test_key_file_exists_on_windows_where_chmod_cannot_express_0600(self):
        """Windows'ta `chmod(0o600)` istenen kısıtlamayı ÜRETMEZ.

        Ölçüldü (Windows CI): `os.stat().st_mode` 0o666 döner, 0o600 değil.
        Windows POSIX izin bitlerini gerçek bir erişim denetimi olarak
        uygulamaz; koruma ACL'lerden gelir. Bu testi 0o600 bekleyecek şekilde
        bırakmak, var olmayan bir garantiyi doğruluyormuş gibi yapardı.

        Windows'ta dosya anahtarı zaten YEDEK yoldur: birincil sağlayıcı
        DPAPI'dir (utils/key_provider.py::WindowsDPAPIKeyProvider) ve anahtarı
        kullanıcı hesabına bağlar. Dosya da kullanıcı profili altında durur,
        yani varsayılan ACL'i zaten kullanıcıya özeldir.

        Burada doğrulanan: anahtar dosyası gerçekten oluşuyor ve düz bir
        dosya. Gerçek ACL doğrulaması pywin32 gerektirir ve ayrı bir iştir —
        `docs/KEY_MANAGEMENT.md` bu sınırı açıkça yazmalı.
        """
        provider = FileKeyProvider(self.key_path)
        provider.get_or_create_key()
        self.assertTrue(os.path.isfile(self.key_path))


class _FakeKeyringBackend:
    priority = 1


class _FakeKeyring:
    def __init__(self, available=True):
        self.backend = _FakeKeyringBackend()
        self.backend.priority = 1 if available else 0
        self.values = {}

    def get_keyring(self):
        return self.backend

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, value):
        self.values[(service, username)] = value


class _FakeProtector:
    def protect(self, data):
        return b"protected:" + data[::-1]

    def unprotect(self, data):
        if not data.startswith(b"protected:"):
            raise OSError("tampered")
        return data[len(b"protected:"):][::-1]


class PlatformKeyProviderTest(unittest.TestCase):
    def test_keyring_round_trip_survives_provider_restart(self):
        keyring = _FakeKeyring()
        first = KeyringKeyProvider(keyring_module=keyring)
        key = first.get_or_create_key()
        second = KeyringKeyProvider(keyring_module=keyring)
        self.assertEqual(second.get_or_create_key(), key)

    def test_unavailable_keyring_is_explicit(self):
        provider = KeyringKeyProvider(
            keyring_module=_FakeKeyring(available=False)
        )
        with self.assertRaises(KeyUnavailableError):
            provider.get_or_create_key()

    def test_dpapi_blob_never_contains_raw_key(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "key.dpapi")
            key = DpapiKeyProvider(
                path, protector=_FakeProtector()
            ).get_or_create_key()
            with open(path, "rb") as stream:
                self.assertNotEqual(stream.read(), key)
            restarted = DpapiKeyProvider(path, protector=_FakeProtector())
            self.assertEqual(restarted.get_or_create_key(), key)

    def test_legacy_file_is_migrated_only_after_store_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            legacy_path = os.path.join(temp, "encryption.key")
            legacy = FileKeyProvider(legacy_path)
            key = legacy.get_or_create_key()
            primary = KeyringKeyProvider(keyring_module=_FakeKeyring())
            provider = MigratingKeyProvider(
                primary,
                legacy,
                KeyProtectionStatus("test store", True),
            )
            self.assertEqual(provider.get_or_create_key(), key)
            self.assertFalse(os.path.exists(legacy_path))
            self.assertFalse(os.path.exists(legacy_path + ".migrated"))
            self.assertEqual(primary.load_key(), key)

    def test_linux_factory_reports_insecure_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch("utils.key_provider.sys.platform", "linux"):
                provider = create_platform_key_provider(
                    temp, keyring_module=_FakeKeyring(available=False)
                )
            self.assertFalse(provider.status.secure_store)
            self.assertIsNotNone(provider.status.warning)


if __name__ == "__main__":
    unittest.main()
