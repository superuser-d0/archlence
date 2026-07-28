"""Kategori Ayarları > Gelir/Gider geçişindeki donma düzeltmesi.

BAĞLAM: varsayılan kategori listesi ~32 gelir + ~49 gider kategorisi
içeriyor (bkz. database/init_db.py). `load_categories` eskiden hepsini TEK
Clock karesinde, düz bir döngüyle inşa ediyordu — her `CategorySettingItem`
bir `MDSwitch` içeriyor (KivyMD'de inşası pahalı bir widget), yani her
basışta 30-50 ağır widget'ı senkron olarak ana thread'de kurmaya
çalışıyordu. Kullanıcı bunu gerçek kullanımda "basınca donuyor" olarak
bildirdi; gerçek bir pencerede DB'deki tam kategori sayısıyla (32/49) ve
hızlı Gelir/Gider geçişiyle ayrıca doğrulandı (bkz. commit mesajı).

Bu dosya, gerçek bir Kivy penceresi ya da KivyMD App örneği kurmadan,
`_add_categories_incrementally`'nin kademeli-ekleme ve jenerasyon-koruması
mantığını doğrudan test eder — `CategorySettingItem`'ın kendisi mock'lanır,
çünkü test edilen şey widget'ın GÖRÜNÜMÜ değil, KAÇ TANESİNİN HANGİ KAREDE
eklendiği."""
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


def _make_categories(n, cat_type="income"):
    return [(f"Kategori{i}", cat_type, "extra") for i in range(n)]


class CategoryIncrementalLoadTest(unittest.TestCase):
    def setUp(self):
        import main
        self.main = main
        self.app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        self.app._category_load_generation = 1
        self.settings_list = mock.Mock()
        self.added = []
        self.settings_list.add_widget.side_effect = self.added.append
        self.patcher = mock.patch.object(self.main, "CategorySettingItem", side_effect=lambda **kw: kw)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_first_call_adds_only_one_batch_not_everything(self):
        """Asıl regresyon kanıtı: 20 kategori verilse bile tek çağrı,
        tamamını değil yalnızca `_CATEGORY_BATCH_SIZE` kadarını eklemeli —
        geri kalanı sonraki karelere bırakılmalı."""
        categories = _make_categories(20)
        self.app._add_categories_incrementally(self.settings_list, categories, generation=1)
        self.assertEqual(len(self.added), self.app._CATEGORY_BATCH_SIZE)

    def test_all_items_eventually_added_across_frames(self):
        from kivy.clock import Clock

        categories = _make_categories(20)
        self.app._add_categories_incrementally(self.settings_list, categories, generation=1)
        for _ in range(10):
            Clock.tick()
        self.assertEqual(len(self.added), 20)

    def test_fewer_items_than_batch_size_all_added_in_one_pass(self):
        categories = _make_categories(3)
        self.app._add_categories_incrementally(self.settings_list, categories, generation=1)
        self.assertEqual(len(self.added), 3)

    def test_stale_generation_stops_adding_more_widgets(self):
        """Kullanıcı Gelir/Gider arasında hızlıca geçerse, eski (artık
        geçersiz) bir yükleme kalan gruplarını eklemeye devam etmemeli —
        aksi hâlde iki listenin widget'ları karışır."""
        from kivy.clock import Clock

        categories = _make_categories(20)
        self.app._add_categories_incrementally(self.settings_list, categories, generation=1)
        after_first_batch = len(self.added)
        self.assertLess(after_first_batch, 20)

        # Kullanıcı başka bir sekmeye geçti: gerçek load_categories() bunu
        # yeni bir jenerasyon numarasıyla yapar.
        self.app._category_load_generation = 2

        for _ in range(10):
            Clock.tick()

        self.assertEqual(
            len(self.added), after_first_batch,
            "bayat (generation=1) yükleme durdurulmadı, widget eklemeye devam etti",
        )

    def test_correct_generation_is_unaffected_by_a_stale_one(self):
        """Aynı senaryo ama gerçekçi hâliyle: eski yükleme dururken YENİ
        jenerasyonun kendi yüklemesi normal şekilde tamamlanabilmeli."""
        from kivy.clock import Clock

        stale_categories = _make_categories(20, "income")
        self.app._add_categories_incrementally(self.settings_list, stale_categories, generation=1)

        # Yeni sekme: yeni jenerasyon + yeni (ayrı) liste/mock.
        self.app._category_load_generation = 2
        new_settings_list = mock.Mock()
        new_added = []
        new_settings_list.add_widget.side_effect = new_added.append
        new_categories = _make_categories(15, "expense")
        self.app._add_categories_incrementally(new_settings_list, new_categories, generation=2)

        for _ in range(10):
            Clock.tick()

        self.assertEqual(len(new_added), 15)


if __name__ == "__main__":
    unittest.main()
