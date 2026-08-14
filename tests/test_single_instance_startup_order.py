"""Tek örnek kilidi, Kivy penceresi açılmadan ÖNCE alınmalı.

NEDEN VAR: kilit kontrolü `main.py`'ın sonundaki `__main__` bloğunda duruyordu.
Python o bloğa gelene kadar modülün tamamını çalıştırır — `kivy.core.window`
import edildiği anda da SDL penceresi açılır. Sonuç fiziksel Windows
makinesinde ölçüldü (bkz. WINDOWS_RC_CHECKLIST.md §2.4): ikinci örnek
başlatıldığında kullanıcı önce BOŞ SİYAH BİR PENCERE görüyor, "zaten
çalışıyor" uyarısı ancak onun üstüne geliyor ve kutu kapatılana kadar orada
duruyor. Koddaki "Kivy/SQLite başlangıcından önce" notu paketlenmiş yapıda
geçerli değildi.

Bu test sırayı sabitliyor. Kaynak metni üzerinden çalışıyor çünkü ölçtüğü şey
çalışma zamanı davranışı değil, `main.py`'ın İMPORT SIRASI — modülü test
içinde import etmek pencereyi açacağı için davranışı gözlemleyerek test
edilemez.

Doğrulandı: kilit alma bloğu tekrar aşağı taşınırsa bu test kırmızıya döner.
"""

import re
import unittest
from pathlib import Path

MAIN_PY = Path(__file__).parents[1] / "main.py"


class SingleInstanceRunsBeforeTheWindow(unittest.TestCase):

    def setUp(self):
        self.source = MAIN_PY.read_text(encoding="utf-8")

    def _index_of(self, pattern, label):
        match = re.search(pattern, self.source, re.MULTILINE)
        self.assertIsNotNone(
            match, f"{label} main.py içinde bulunamadı — desen: {pattern}"
        )
        return match.start()

    def test_lock_is_acquired_before_the_kivy_window_import(self):
        acquire = self._index_of(
            r"^\s*_instance_lock\.acquire\(\)", "kilit alma çağrısı"
        )
        window_import = self._index_of(
            r"^\s*from kivy\.core\.window import", "kivy.core.window import'u"
        )
        self.assertLess(
            acquire, window_import,
            "Kilit, `kivy.core.window` import'undan SONRA alınıyor. Bu sırayla "
            "ikinci örnek önce boş bir pencere açar, uyarı kutusu onun üstüne "
            "gelir (WINDOWS_RC_CHECKLIST.md §2.4).",
        )

    def test_lock_is_acquired_before_any_kivy_import(self):
        acquire = self._index_of(
            r"^\s*_instance_lock\.acquire\(\)", "kilit alma çağrısı"
        )
        first_kivy = self._index_of(
            r"^from kivy[\. ]", "ilk kivy import'u"
        )
        self.assertLess(
            acquire, first_kivy,
            "Kilit ilk `kivy` import'undan sonra alınıyor; pencere sağlayıcısı "
            "bu import zincirinin herhangi bir yerinde kurulabilir.",
        )

    def test_acquisition_is_guarded_by_the_main_check(self):
        """`import main` kilidi ALMAMALI — testler modülü böyle yüklüyor."""
        acquire = self._index_of(
            r"^\s*_instance_lock\.acquire\(\)", "kilit alma çağrısı"
        )
        guards = [
            m.start()
            for m in re.finditer(
                r'^if __name__ == "__main__":', self.source, re.MULTILINE
            )
        ]
        self.assertTrue(
            any(g < acquire for g in guards),
            "Kilit alma çağrısı bir `__main__` guard'ının içinde değil; "
            "`import main` yapan her test kilidi alırdı.",
        )

    def test_lock_is_released_on_exit(self):
        """Erken `SystemExit` yolları da kapsanmalı — bu yüzden atexit."""
        self.assertRegex(
            self.source,
            r"atexit\.register\(_instance_lock\.release\)",
            "Kilit `atexit` ile bırakılmıyor. Kilit artık Kivy'den önce "
            "alındığı için, aradaki her erken çıkış yolu kilidi asılı "
            "bırakabilir.",
        )


if __name__ == "__main__":
    unittest.main()
