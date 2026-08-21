"""docs/ROADMAP.md Faz 1 madde 4. `utils/app_paths.py`'nin yol çözümlemesini
ve tek seferlik dosya taşıma mekaniğini doğrular — hiçbiri GUI'ye bağımlı
değil, platformdirs'in kendi okuduğu ortam değişkenleri (Linux'ta
XDG_DATA_HOME vb.) monkeypatch'lenerek gerçek bir OS kurulumu gerekmeden
test edilir."""
import os
import sys
import tempfile
import unittest
from unittest import mock

from utils.app_paths import cache_dir, data_dir, log_dir, migrate_legacy_path, resource_dir


class PathResolutionTest(unittest.TestCase):
    """platformdirs'in kendisi zaten test edilmiş bir kütüphane — burada
    doğrulanan, BİZİM sarmalayıcımızın gerçekten platformdirs'e delege
    ettiği ve üç farklı amaç (data/cache/log) için üç FARKLI, birbirinden
    ayrık dizin döndürdüğü."""

    def test_import_alone_creates_no_directories(self):
        """Modülü salt import etmek / fonksiyonları çağırmak hiçbir gerçek
        dizin yaratmamalı — test suite'inin her import edişinde geliştiricinin
        gerçek ev dizininde yan etki bırakmaması buna bağlı."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = os.path.join(tmp, "xdg-probe")
            with mock.patch.dict(
                os.environ,
                {"XDG_DATA_HOME": fake_home, "XDG_CACHE_HOME": fake_home, "XDG_STATE_HOME": fake_home},
            ):
                data_dir()
                cache_dir()
                log_dir()
            self.assertFalse(os.path.exists(fake_home))

    @staticmethod
    def _home_override(root):
        """Yolları sandbox'a çeken PLATFORMDAN BAĞIMSIZ yönlendirme.

        Eskiden burada yalnız XDG_* vardı. XDG Windows'ta ÇALIŞMAZ:
        `platformdirs` orada ortam değişkenlerine hiç bakmaz, `ctypes` ile
        `SHGetFolderPathW` çağırır. Yani bu test Linux'ta yeşil olup Windows'ta
        yol yönlendirmesinin tamamen kırık olduğunu GİZLİYORDU — ve test
        paketinin kendi izolasyonu da aynı kırık mekanizmaya dayanıyordu.
        `ARCHLENCE_HOME` (utils/app_paths.py) her platformda geçerlidir.
        """
        return {"ARCHLENCE_HOME": root}

    def test_data_cache_log_dirs_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                os.environ,
                self._home_override(tmp),
            ):
                d, c, log = data_dir(), cache_dir(), log_dir()


            self.assertNotEqual(d, c)
            self.assertNotEqual(d, log)
            self.assertNotEqual(c, log)
            for resolved in (d, c, log):
                self.assertTrue(
                    resolved.startswith(tmp),
                    f"{resolved!r} sandbox {tmp!r} altında değil — bu "
                    "platformda yol yönlendirmesi ÇALIŞMIYOR demektir.",
                )

    @unittest.skipIf(
        os.name == "nt",
        "platformdirs Windows'ta ortam değişkenlerini yok sayar (ctypes ile "
        "SHGetFolderPathW); bu test XDG üzerinden VARSAYILAN çözümlemeyi "
        "sınıyor ve orada yönlendirilemez.",
    )
    def test_resolved_dirs_are_namespaced_under_the_app_name(self):
        """VARSAYILAN (yönlendirmesiz) çözümleme uygulama adıyla isimlenmeli.

        `ARCHLENCE_HOME` burada AÇIKÇA temizlenir: bu test platformdirs'in
        varsayılan davranışını sınıyor, geçersiz kılma yolunu değil. Test
        paketi kendi izolasyonu için o değişkeni global olarak ayarlıyor
        (run_tests.py) — temizlemezsek burada yanlış kod yolunu ölçerdik.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                os.environ, {"XDG_DATA_HOME": tmp, "ARCHLENCE_HOME": ""}
            ):
                d = data_dir()
            self.assertIn("Archlence", d)

    def test_home_override_wins_over_platform_defaults(self):
        """`ARCHLENCE_HOME` her platformda çözümlemeyi yönlendirmeli.

        Bu, test paketi izolasyonunun dayandığı sözleşmedir; kırılırsa
        testler geliştiricinin GERÇEK veri dizinine yazmaya başlar.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ARCHLENCE_HOME": tmp}):
                self.assertTrue(data_dir().startswith(tmp))
                self.assertTrue(cache_dir().startswith(tmp))
                self.assertTrue(log_dir().startswith(tmp))


class ResourceDirTest(unittest.TestCase):
    """Gerçek bir Windows kurulumunda ampirik olarak üretilen çökmenin
    (`FileNotFoundError: 'ui/tools.kv'`) kök nedenini kapatan fonksiyon.

    `main.py` artık başlangıçta `os.chdir(resource_dir())` çağırıyor —
    bu, `resource_dir()`'ın PAKETLENMİŞ (sys.frozen) ve GELİŞTİRME
    modlarının İKİSİNDE de doğru dizini döndürdüğüne bağlı. `sys.frozen`/
    `sys._MEIPASS`, PyInstaller'ın paketlenmiş bir .exe çalışırken gerçekten
    ayarladığı öznitelikler — burada gerçek bir .exe olmadan (Linux'ta
    mümkün değil) taklit ediliyor."""

    def test_dev_mode_resolves_to_the_repo_root(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(resource_dir(), repo_root)

        self.assertTrue(os.path.isdir(os.path.join(resource_dir(), "ui")))

    def test_frozen_mode_resolves_to_sys_meipass_not_cwd_or_file(self):
        """PyInstaller'ın kendi mekanizması: paketlenmiş bir derlemede
        `sys.frozen = True` ve `sys._MEIPASS`, `datas=[...]` ile gömülen
        dosyaların GERÇEKTE durduğu dizini gösterir — .exe'nin kendi
        dizininden FARKLI olabilir (PyInstaller 6.x'in `_internal` alt
        klasörü, bkz. archlence.spec). `__file__` ya da `os.getcwd()`'e
        güvenmenin YANLIŞ olacağını kanıtlamak için ikisini de gerçek
        değerden FARKLI bırakıyoruz."""
        fake_meipass = "/some/fake/pyinstaller/bundle/dir"
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "_MEIPASS", fake_meipass, create=True):
            self.assertEqual(resource_dir(), fake_meipass)

    def test_frozen_flag_absent_means_dev_mode_even_if_meipass_lingers(self):
        """`sys.frozen` gerçekten False/yok olduğu sürece (gerçek geliştirme
        ortamının hâli), `sys._MEIPASS` her ne sebeple olursa olsun ortamda
        kalmış olsa bile göz ardı edilmeli."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with mock.patch.object(sys, "_MEIPASS", "/leftover/stale/path", create=True):
            self.assertEqual(resource_dir(), repo_root)


class MigrateLegacyPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_path = os.path.join(self.tmp.name, "old", "finance.db")
        self.new_path = os.path.join(self.tmp.name, "new", "finance.db")
        os.makedirs(os.path.dirname(self.old_path))

    def _write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_moves_old_file_to_new_location(self):
        self._write(self.old_path, "gercek kullanici verisi")
        moved = migrate_legacy_path(self.old_path, self.new_path)
        self.assertTrue(moved)
        self.assertFalse(os.path.exists(self.old_path))
        with open(self.new_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "gercek kullanici verisi")

    def test_creates_missing_parent_directory_of_new_path(self):
        self._write(self.old_path, "veri")
        nested_new = os.path.join(self.tmp.name, "a", "b", "c", "finance.db")
        self.assertTrue(migrate_legacy_path(self.old_path, nested_new))
        self.assertTrue(os.path.exists(nested_new))

    def test_fresh_install_with_no_legacy_file_does_nothing(self):
        moved = migrate_legacy_path(self.old_path, self.new_path)
        self.assertFalse(moved)
        self.assertFalse(os.path.exists(self.new_path))

    def test_never_overwrites_an_existing_new_location(self):
        """En kritik davranış: hedefte zaten (güncel) bir dosya varsa, eski
        konumdaki bayat kopya onun ÜZERİNE yazılmamalı — kullanıcı verisi
        kaybı buradan olur."""
        self._write(self.old_path, "eski/bayat veri")
        self._write(self.new_path, "guncel veri")
        moved = migrate_legacy_path(self.old_path, self.new_path)
        self.assertFalse(moved)
        with open(self.new_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "guncel veri")

        self.assertTrue(os.path.exists(self.old_path))

    def test_survives_a_read_only_source_directory(self):
        """Bu fonksiyonun ASIL kullanım senaryosu: kaynak, paketlenmiş bir
        Windows kurulumunda genelde SALT-OKUNUR olan uygulama kurulum
        dizini — madde 4'ün var olma sebebi. İlk sürüm burada `shutil.move`
        kullanıyordu; move aynı dosya sisteminde `os.rename`e iner ve
        kaynak DİZİNDE yazma izni ister, bu yüzden PermissionError
        fırlatıyordu ve build() bunu yakalamadığı için uygulama hiç
        açılmadan düşüyordu. Veri yine de yeni konuma ulaşmalı."""
        self._write(self.old_path, "salt okunur dizindeki veri")
        old_dir = os.path.dirname(self.old_path)
        os.chmod(old_dir, 0o555)
        self.addCleanup(os.chmod, old_dir, 0o755)

        moved = migrate_legacy_path(self.old_path, self.new_path)

        self.assertTrue(moved)
        with open(self.new_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "salt okunur dizindeki veri")

    def test_undeletable_source_is_not_recopied_on_the_next_run(self):
        """Salt-okunur kaynakta eski dosya silinemeden kalır; bu KABUL
        EDİLEBİLİR, ama bir sonraki açılışta kullanıcının o an güncel olan
        verisinin üzerine tekrar kopyalanmamalı."""
        self._write(self.old_path, "eski veri")
        old_dir = os.path.dirname(self.old_path)
        os.chmod(old_dir, 0o555)
        self.addCleanup(os.chmod, old_dir, 0o755)

        self.assertTrue(migrate_legacy_path(self.old_path, self.new_path))

        with open(self.new_path, "w", encoding="utf-8") as f:
            f.write("kullanicinin guncel verisi")

        self.assertFalse(migrate_legacy_path(self.old_path, self.new_path))
        with open(self.new_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "kullanicinin guncel verisi")

    def test_repeated_calls_are_idempotent(self):
        self._write(self.old_path, "veri")
        first = migrate_legacy_path(self.old_path, self.new_path)
        second = migrate_legacy_path(self.old_path, self.new_path)
        self.assertTrue(first)
        self.assertFalse(second)


if __name__ == "__main__":
    unittest.main()
