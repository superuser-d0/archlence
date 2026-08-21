"""Türkçe hata metni, konsol kodlaması yüzünden süreci öldürmemeli.

GERÇEK HATA (Windows CI'da ölçüldü): Windows'ta stdout konsolun kod sayfasını
kullanır (Türkçe kurulumlarda genelde cp1252) ve bu kod sayfası 'ı', 'ğ', 'ş'
karakterlerini KODLAYAMAZ. `print()` o durumda `UnicodeEncodeError` fırlatır.

Bu, kozmetik bir sorun değildi: uygulamanın Türkçe hata mesajlarının çoğu
`except` bloklarının İÇİNDE basılıyor. Orada `print` patlayınca hata yutulmaz —
istisna dışarı sızıp asıl işlemi öldürür. `TransactionService.add_transaction`
içindeki "Abonelik radarına yazılamadı" satırı tam olarak bunu yapıyordu:
abonelik radarı hata verdiğinde İŞLEMİN TAMAMI kayboluyordu. Aynı test
Linux'ta (UTF-8) yeşil, Windows'ta kırmızıydı.

Testler cp1252 konsolu taklit eder — Linux'ta da anlamlı koşsun diye.
"""
import io
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TurkishTextOnLegacyConsoleTest(unittest.TestCase):

    def test_cp1252_cannot_encode_turkish_dotless_i(self):
        """Tehlikenin gerçek olduğunu göster — varsayma.

        Bu test düzeltmeyi değil, GEREKÇESİNİ doğrular: 'ı' gerçekten
        cp1252'de kodlanamıyor mu?
        """
        with self.assertRaises(UnicodeEncodeError):
            "Abonelik radarına yazılamadı".encode("cp1252")

    def test_print_survives_a_cp1252_stdout_after_reconfigure(self):
        """UTF-8'e yeniden yapılandırılmış akış Türkçe metni yutmadan basar."""
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")


        with self.assertRaises(UnicodeEncodeError):
            print("Abonelik radarına yazılamadı", file=stream)
            stream.flush()


        stream.reconfigure(encoding="utf-8", errors="replace")
        print("Abonelik radarına yazılamadı", file=stream)
        stream.flush()
        self.assertIn("radarına", raw.getvalue().decode("utf-8"))

    def test_main_reconfigures_stdio_before_any_turkish_output(self):
        """`main.py` içe aktarıldığında akışlar UTF-8'e çekilmiş olmalı.

        Alt süreçte cp1252 stdout dayatılır; düzeltme yoksa Türkçe `print`
        çöker. Bu, gerçek Windows davranışının taşınabilir taklididir.
        """
        probe = textwrap.dedent(
            """
            import io, os, sys
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="cp1252", errors="strict")
            os.environ["ARCHLENCE_HEADLESS"] = "1"
            os.environ["KIVY_NO_ARGS"] = "1"
            import main  # noqa: F401  -- reconfigure burada olmalı
            print("Abonelik radarına yazılamadı")
            print("PROBE_OK")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        self.assertIn(
            "PROBE_OK", result.stdout,
            "main.py içe aktarıldıktan sonra Türkçe print hâlâ çöküyor. "
            f"stderr: {result.stderr[-600:]}",
        )


if __name__ == "__main__":
    unittest.main()
