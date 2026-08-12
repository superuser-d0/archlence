"""docs/ROADMAP.md Faz 1 madde 4. `main.py::_resolve_config_path` /
`_resolve_savings_store_path` — gerçek dosya taşıma mekaniği zaten
tests/test_app_paths.py'de doğrulandı; burada doğrulanan, main.py'nin bu
mekaniği DOĞRU parametrelerle çağırdığı (eski konum, yeni konum, yeniden
adı geçmişi zinciri). Her ikisi de `self`'e ihtiyacı olmayan saf
fonksiyonlar — gerçek bir Kivy penceresi kurmadan doğrudan çağrılabilir."""
import os
import tempfile
import unittest

from utils.app_paths import LEGACY_CONFIG_FILENAME
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class ResolveConfigPathTest(unittest.TestCase):
    def setUp(self):
        import main
        self.main = main
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app_dir = os.path.join(self.tmp.name, "app_dir")
        self.data_dir_path = os.path.join(self.tmp.name, "data_dir")
        os.makedirs(self.app_dir)

    def _patched(self):
        return (
            mock.patch.object(self.main, "_APP_DIR", self.app_dir),
            mock.patch.object(self.main, "data_dir", return_value=self.data_dir_path),
        )

    def test_env_override_is_used_as_is_and_skips_migration(self):
        override_path = os.path.join(self.tmp.name, "custom_config.json")
        legacy = os.path.join(self.app_dir, "archlence_config.json")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("eski config")
        p1, p2 = self._patched()
        with p1, p2, mock.patch.dict(os.environ, {"ARCHLENCE_CONFIG_PATH": override_path}):
            result = self.main._resolve_config_path()
        self.assertEqual(result, override_path)
        # Migration atlanmalı: eski dosya yerinde kalmalı.
        self.assertTrue(os.path.exists(legacy))

    def test_migrates_existing_app_dir_config_to_data_dir(self):
        legacy = os.path.join(self.app_dir, "archlence_config.json")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("gercek kullanici ayarlari")
        p1, p2 = self._patched()
        with p1, p2, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()
        self.assertEqual(result, os.path.join(self.data_dir_path, "archlence_config.json"))
        self.assertFalse(os.path.exists(legacy))
        with open(result, encoding="utf-8") as f:
            self.assertEqual(f.read(), "gercek kullanici ayarlari")

    def test_migrates_the_oldest_named_config_straight_to_data_dir(self):
        """EN ESKİ isimli config DOĞRUDAN kullanıcı-veri dizinine taşınır.
        Önceki hâli araya bir adım koyuyordu — en eskisini önce _APP_DIR
        içinde yeni ada kopyalayıp sonra oradan taşıyordu — yani
        paketlenmiş bir Windows kurulumunda SALT-OKUNUR olan kurulum
        dizinine YAZMAYA çalışıyordu; tam da madde 4'ün ortadan kaldırmak
        için var olduğu şey."""
        pre_rename_path = os.path.join(self.app_dir, LEGACY_CONFIG_FILENAME)
        with open(pre_rename_path, "w", encoding="utf-8") as f:
            f.write("cok eski surumden kalan veri")
        p1, p2 = self._patched()
        with p1, p2:
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()
        self.assertEqual(result, os.path.join(self.data_dir_path, "archlence_config.json"))
        with open(result, encoding="utf-8") as f:
            self.assertEqual(f.read(), "cok eski surumden kalan veri")
        # _APP_DIR'a ara dosya YAZILMAMALI.
        self.assertFalse(
            os.path.exists(os.path.join(self.app_dir, "archlence_config.json"))
        )

    def test_newer_legacy_name_wins_when_both_old_names_exist(self):
        """İki eski ad da varsa yeni olanı (archlence) kazanmalı; daha eskisi
        dosyası kullanıcının güncel ayarlarının üzerine yazmamalı."""
        with open(os.path.join(self.app_dir, "archlence_config.json"), "w", encoding="utf-8") as f:
            f.write("daha yeni ayarlar")
        with open(os.path.join(self.app_dir, LEGACY_CONFIG_FILENAME), "w", encoding="utf-8") as f:
            f.write("cok eski surumden kalan veri")
        p1, p2 = self._patched()
        with p1, p2:
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()
        with open(result, encoding="utf-8") as f:
            self.assertEqual(f.read(), "daha yeni ayarlar")

    def test_resolves_without_writing_into_a_read_only_install_dir(self):
        """Asıl regresyon koruması: kurulum dizini salt-okunur olduğunda
        (paketlenmiş Windows kurulumu) config çözümlemesi PATLAMAMALI —
        bu, build() içinde yakalanmadığı için uygulamayı hiç açılmadan
        düşürürdü."""
        with open(os.path.join(self.app_dir, "archlence_config.json"), "w", encoding="utf-8") as f:
            f.write("mevcut kurulumdan gelen ayarlar")
        os.chmod(self.app_dir, 0o555)
        self.addCleanup(os.chmod, self.app_dir, 0o755)

        p1, p2 = self._patched()
        with p1, p2:
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()

        self.assertEqual(result, os.path.join(self.data_dir_path, "archlence_config.json"))
        with open(result, encoding="utf-8") as f:
            self.assertEqual(f.read(), "mevcut kurulumdan gelen ayarlar")

    def test_fresh_install_has_no_legacy_files_to_migrate(self):
        p1, p2 = self._patched()
        with p1, p2:
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()
        self.assertEqual(result, os.path.join(self.data_dir_path, "archlence_config.json"))
        self.assertFalse(os.path.exists(result))  # JsonStore ilk put()'ta yaratır

    def test_never_overwrites_an_already_migrated_config(self):
        legacy = os.path.join(self.app_dir, "archlence_config.json")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("eski/bayat")
        os.makedirs(self.data_dir_path)
        target = os.path.join(self.data_dir_path, "archlence_config.json")
        with open(target, "w", encoding="utf-8") as f:
            f.write("guncel")
        p1, p2 = self._patched()
        with p1, p2:
            os.environ.pop("ARCHLENCE_CONFIG_PATH", None)
            result = self.main._resolve_config_path()
        with open(result, encoding="utf-8") as f:
            self.assertEqual(f.read(), "guncel")


class ResolveSavingsStorePathTest(unittest.TestCase):
    def setUp(self):
        import main
        self.main = main
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app_dir = os.path.join(self.tmp.name, "app_dir")
        self.data_dir_path = os.path.join(self.tmp.name, "data_dir")
        os.makedirs(self.app_dir)

    def test_migrates_existing_savings_goals_file(self):
        legacy = os.path.join(self.app_dir, "savings_goals.json")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("gercek birikim hedefleri")
        with (
            mock.patch.object(self.main, "_APP_DIR", self.app_dir),
            mock.patch.object(self.main, "data_dir", return_value=self.data_dir_path),
        ):
            result = self.main._resolve_savings_store_path()
        self.assertEqual(result, os.path.join(self.data_dir_path, "savings_goals.json"))
        self.assertFalse(os.path.exists(legacy))


if __name__ == "__main__":
    unittest.main()
