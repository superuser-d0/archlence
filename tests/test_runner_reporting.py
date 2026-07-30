"""Test raporunun Kivy'nin stderr ele geçirmesine dayanıklı olduğunu kilitler.

BAĞLAM (v1.1.0'da bulundu): Kivy, `import kivy` sırasında `sys.stderr`i kendi
`ProcessingStream`iyle değiştiriyor (kivy/logger.py, KIVY_NO_CONSOLELOG ayarlı
değilse) ve o akış kendisine yazılan her şeyi Kivy logger'ına huniliyor.

`run_tests.py` runner'ı `TextTestRunner(verbosity=2)` ile — yani akışı
ÇAĞRI ANINDAKİ `sys.stderr`den alarak — kuruyordu. Tam paket koşusunda Kivy
çekirdeği ilk kez derinden import edildiğinde rapor bu huniye düşüyor ve
kayboluyordu: kalan ~505 testin adları, assertion mesajları, traceback'ler ve
"Ran N tests" + "OK"/"FAILED" özeti dahil.

Çıkış kodu doğru kalıyordu (kasıtlı bir hatayla ölçüldü: exit 1), yani CI
"başarısız" diyebiliyordu — ama NEYİN başarısız olduğunu kimse göremiyordu.
Bu iki test hem tehlikenin gerçek olduğunu hem de düzeltmenin yerinde
durduğunu kanıtlar.
"""
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RunnerReportingContractTest(unittest.TestCase):

    def test_kivy_import_really_replaces_sys_stderr(self):
        """Tehlike gerçek mi? Ayrı bir süreçte ölç — varsayma.

        Bu test düzeltmeyi değil, düzeltmenin GEREKÇESİNİ doğrular. Kivy bir
        gün bu davranışı bırakırsa burası kırmızıya döner ve
        `run_tests.py`deki akış sabitlemesinin hâlâ gerekli olup olmadığını
        yeniden değerlendirmemiz gerektiğini söyler.
        """
        probe = textwrap.dedent(
            """
            import os, sys
            os.environ.setdefault("KIVY_NO_ARGS", "1")
            os.environ.pop("KIVY_NO_CONSOLELOG", None)
            before = sys.stderr
            import kivy.logger  # noqa: F401
            print("DEGISTI" if sys.stderr is not before else "AYNI")
            """
        )
        out = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        ).stdout
        self.assertIn(
            "DEGISTI", out,
            "Kivy artık sys.stderr'i değiştirmiyorsa run_tests.py'deki akış "
            "sabitlemesinin gerekçesi gözden geçirilmeli.",
        )

    def test_run_tests_pins_the_report_stream_taken_before_any_kivy_import(self):
        """`run_tests.py` raporu GERÇEK stderr'e yazmalı.

        İki koşul birden aranır: (1) gerçek akış Kivy'den önce yakalanmış,
        (2) runner'a açıkça verilmiş. Yalnızca birini kontrol etmek, birinin
        sessizce kaldırılmasına izin verirdi.
        """
        source = (ROOT / "run_tests.py").read_text(encoding="utf-8")

        capture = re.search(r"^_REAL_STDERR\s*=\s*sys\.stderr", source, re.M)
        self.assertIsNotNone(
            capture, "run_tests.py gerçek stderr'i yakalamıyor.")

        runner = re.search(
            r"TextTestRunner\([^)]*stream\s*=\s*_REAL_STDERR", source)
        self.assertIsNotNone(
            runner,
            "TextTestRunner'a stream=_REAL_STDERR verilmemiş; rapor Kivy'nin "
            "logger'ına düşer ve hangi testin neden battığı görünmez olur.",
        )

        # Yakalama, discovery'den (dolayısıyla her türlü kivy importundan) ÖNCE
        # olmalı — sonra yakalanırsa zaten ele geçirilmiş akışı yakalar.
        discover = source.index("discover(")
        self.assertLess(
            capture.start(), discover,
            "Gerçek stderr discovery'den SONRA yakalanmış; o noktada Kivy "
            "akışı çoktan değiştirmiş olabilir.",
        )


if __name__ == "__main__":
    unittest.main()
