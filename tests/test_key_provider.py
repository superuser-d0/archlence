"""docs/ROADMAP.md Faz 1 madde 5. `FileKeyProvider` — anahtarın NEREYE
yazılacağına (platformdirs, Faz 1 madde 4) karar vermeden, verilen bir
yola nasıl kalıcı anahtar yazılıp okunacağını doğrular."""
import os
import stat
import tempfile
import threading
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
            barrier.wait()  # sekiz thread'i de aynı ana hizala
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

    def test_key_file_is_owner_only_readable(self):
        provider = FileKeyProvider(self.key_path)
        provider.get_or_create_key()
        mode = stat.S_IMODE(os.stat(self.key_path).st_mode)
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
