"""İşlem Ekle diyaloğundaki "Kategori Seç" arama menüsünün donma düzeltmesi.

BAĞLAM: `open_category_menu`'nün `populate()` iç fonksiyonu, eşleşen TÜM
kategorileri (boş aramada ~30-50 tanesi, bkz. database/init_db.py) TEK
karede, senkron olarak inşa ediyordu — VE arama kutusuna her karakter
yazıldığında yeniden çalışıyordu (`search_field.bind(text=...)`).
main.py::load_categories'teki aynı hata sınıfı (bkz.
tests/test_category_settings_performance.py), burada daha da sık
tetikleniyordu. Aynı kademeli-ekleme + jenerasyon-koruması deseni
`_add_category_items_incrementally`'ye uygulandı; bu dosya onu doğrudan
test eder — `OneLineListItem` mock'lanır, test edilen widget render'ı
değil, gruplandırma/jenerasyon algoritmasıdır."""
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


def _names(n):
    return [f"Kategori{i}" for i in range(n)]


class CategorySearchIncrementalLoadTest(unittest.TestCase):
    def setUp(self):
        import main
        self.main = main
        self.app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        self.app._category_populate_generation = 1
        self.app._category_list = mock.Mock()
        self.added = []
        self.app._category_list.add_widget.side_effect = self.added.append
        self.patcher = mock.patch(
            "kivymd.uix.list.OneLineListItem", side_effect=lambda **kw: mock.Mock(**kw)
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_first_call_adds_only_one_batch_not_everything(self):
        self.app._add_category_items_incrementally(_names(20), generation=1)
        self.assertEqual(len(self.added), self.app._CATEGORY_MENU_BATCH_SIZE)

    def test_all_items_eventually_added_across_frames(self):
        from kivy.clock import Clock

        self.app._add_category_items_incrementally(_names(20), generation=1)
        for _ in range(10):
            Clock.tick()
        self.assertEqual(len(self.added), 20)

    def test_fewer_items_than_batch_size_all_added_in_one_pass(self):
        self.app._add_category_items_incrementally(_names(3), generation=1)
        self.assertEqual(len(self.added), 3)

    def test_stale_search_generation_stops_adding_more_widgets(self):
        """Kullanıcı arama kutusuna hızlı yazarsa (her karakter yeni bir
        jenerasyon başlatır), önceki karakterin bayat sonucu widget
        eklemeye devam etmemeli — aksi hâlde iki arama sonucu karışır."""
        from kivy.clock import Clock

        self.app._add_category_items_incrementally(_names(20), generation=1)
        after_first_batch = len(self.added)
        self.assertLess(after_first_batch, 20)


        self.app._category_populate_generation = 2

        for _ in range(10):
            Clock.tick()

        self.assertEqual(
            len(self.added), after_first_batch,
            "bayat (generation=1) arama sonucu durdurulmadı",
        )

    def test_empty_category_list_reference_is_handled_safely(self):
        """Kullanıcı arama diyaloğunu tam da bir grup eklenirken kapatırsa
        `_category_list` referansı geçersiz kalabilir; çökmemeli."""
        from kivy.clock import Clock

        self.app._add_category_items_incrementally(_names(20), generation=1)
        self.app._category_list = None

        for _ in range(10):
            Clock.tick()


if __name__ == "__main__":
    unittest.main()
