import os
import subprocess
import sys
import textwrap
import unittest

# Testler tests/ altında; main.py proje kökünde. Kök, çalışma dizininden değil
# bu dosyanın konumundan türetilir ki test her yerden çalıştırılabilsin.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(script, extra_env=None, strip_display=False):
    env = os.environ.copy()
    env.pop("KIVY_WINDOW", None)
    env.pop("ARCHLENCE_HEADLESS", None)
    env.pop("KIVY_NO_ARGS", None)
    env.pop("SDL_VIDEODRIVER", None)
    if strip_display:
        # CI runner'ları (ör. GitHub Actions ubuntu-latest) gibi: HİÇBİR
        # display sunucusu yok, yalnızca ARCHLENCE_HEADLESS + main.py'nin
        # kendi SDL_VIDEODRIVER=dummy/KIVY_WINDOW=sdl2 varsayılanlarına
        # güveniliyor.
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
    env.setdefault("PYTHONPATH", PROJECT_ROOT)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


class StartupImportTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 1 madde 2. Eski davranış: `DISPLAY` yoksa
    `KIVY_WINDOW=mock` set edilirdi. Bu, ampirik olarak doğrulandığı üzere
    ikili bir hataydı — `DISPLAY` Windows'ta hiç set edilmez (X11'e özgü),
    "mock" ise Kivy 2.3.1'de gerçek bir sağlayıcı değil; ikisi birleşince
    her Windows kurulumunda gerçek pencere denemesi hiç yapılmadan (sessizce,
    exit code 0 ile) atlanıyordu. Bu dosya artık üç ayrı gerçek senaryoyu
    doğruluyor."""

    def test_import_succeeds_with_a_genuinely_working_window_provider(self):
        """Asıl regresyon kanıtı: main.py artık KIVY_WINDOW'a hiç
        dokunmuyor, bu yüzden Kivy'nin kendi doğal sağlayıcı araması
        çalışabiliyor. Bu sandbox'ta DISPLAY hiç yok ama SDL2 yine de
        gerçek bir pencere nesnesi kurabiliyor (kendi headless/offscreen
        fallback'i sayesinde) — eskiden KIVY_WINDOW=mock zorlaması bunu
        HİÇ denemeden engelliyordu."""
        completed = _run(
            """
            import main
            assert main._KivyWindow is not None, "gercek pencere kurulamadi"
            assert type(main.Window).__name__ != "Window", (
                "main.py'nin kendi stub Window sinifina dusmus"
            )
            print("real-window-ok")
            """
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("real-window-ok", completed.stdout)

    def test_genuinely_broken_window_fails_loudly_without_headless_flag(self):
        """ARCHLENCE_HEADLESS set edilmediyse, pencere gerçekten
        kurulamadığında bu SESSİZCE geçiştirilmemeli — kullanıcı "uygulama
        hiçbir şey yapmadan kapandı" yerine gerçek bir hata görmeli."""
        completed = _run(
            "import main",
            extra_env={"KIVY_WINDOW": "gecerli_olmayan_saglayici_xyz"},
        )
        self.assertNotEqual(
            completed.returncode, 0,
            msg="pencere kurulamayınca sessizce (exit 0) çıkmamalı",
        )

        crash_log = os.path.join(PROJECT_ROOT, "crash.log")
        with open(crash_log, encoding="utf-8") as f:
            tail = f.read()[-2000:]
        self.assertIn(
            "Kivy herhangi bir pencere sağlayıcısı bulamadı", tail,
            msg="crash.log gercek hatayi kaydetmemis",
        )

    def test_genuinely_broken_window_degrades_gracefully_with_headless_flag(self):
        """Aynı kırık senaryo, ama ARCHLENCE_HEADLESS=1 açıkça istendiğinde
        — main.py, ArchlenceApp'i yine de import edilebilir bırakan stub
        sınıflara sessizce düşmeli (test/CI/tooling kullanım senaryosu)."""
        completed = _run(
            """
            import importlib
            module = importlib.import_module('main')
            assert module.ArchlenceApp is not None
            assert module._KivyWindow is None
            print('imported')
            """,
            extra_env={
                "KIVY_WINDOW": "gecerli_olmayan_saglayici_xyz",
                "ARCHLENCE_HEADLESS": "1",
            },
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        self.assertIn("imported", completed.stdout)

    def test_headless_import_survives_a_display_server_that_does_not_exist_at_all(self):
        """PR #16'nın ilk CI çalışmasının gerçek başarısızlık senaryosu:
        DISPLAY hiç yok (X11/Wayland yok), yalnızca ARCHLENCE_HEADLESS=1
        set. Önceki bir düzeltme burada YETERSİZDİ: `except (ImportError,
        RuntimeError)` bir Python istisnası bekliyordu, ama Kivy'nin ham
        `x11` sağlayıcısı display'e ulaşamayınca düşük seviye bir Xlib
        connect() çağrısıyla SÜRECİ ÇÖKERTİYORDU (exit code 102) — hiçbir
        Python except bloğu bunu yakalayamaz. main.py artık
        ARCHLENCE_HEADLESS altında arama listesini `sdl2`'ye kısıtlayıp
        SDL_VIDEODRIVER=dummy veriyor, böylece çökmeye sebep olan x11
        sağlayıcısına hiç ulaşılmıyor ve başarısızlık (varsa) Python
        seviyesinde, yakalanabilir kalıyor."""
        completed = _run(
            """
            import main
            assert main._KivyWindow is None
            assert main.ArchlenceApp is not None
            print('headless-no-display-ok')
            """,
            extra_env={"ARCHLENCE_HEADLESS": "1"},
            strip_display=True,
        )
        self.assertEqual(
            completed.returncode, 0,
            msg=f"stdout={completed.stdout!r} stderr={completed.stderr!r}",
        )
        self.assertIn("headless-no-display-ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
