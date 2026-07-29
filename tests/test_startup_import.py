import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from utils.app_paths import log_dir

# Testler tests/ altında; main.py proje kökünde. Kök, çalışma dizininden değil
# bu dosyanın konumundan türetilir ki test her yerden çalıştırılabilsin.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GitHub Actions'ın ubuntu-latest runner'ı gibi gerçek CI ortamlarının hiçbir
# görüntüleme altyapısı yok (DISPLAY yok, XDG_RUNTIME_DIR yok, Xvfb yok) —
# ampirik olarak doğrulandı (PR #16'nın CI çalışması). "Gerçek bir pencere
# sağlayıcısı gerçekten kuruluyor mu" testi böyle bir ortamda anlamsız: kurulacak
# gerçek bir şey yok. Bu, gerçek bir masaüstü oturumu (ör. yerel geliştirme)
# olduğunda hâlâ regresyon koruması sağlar, CI'da sessizce atlanır.
_HAS_REAL_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _run(script, extra_env=None, strip_display=False, cwd=None):
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
        cwd=cwd or PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


class StartupImportTest(unittest.TestCase):
    """docs/ROADMAP.md Faz 1 madde 2. Eski davranış: `DISPLAY` yoksa
    `KIVY_WINDOW=mock` set edilirdi. Bu, ampirik olarak doğrulandığı üzere
    ikili bir hataydı — `DISPLAY` Windows'ta hiç set edilmez (X11'e özgü),
    "mock" ise Kivy 2.3.1'de gerçek bir sağlayıcı değil; ikisi birleşince
    her Windows kurulumunda gerçek pencere denemesi hiç yapılmadan (sessizce,
    exit code 0 ile) atlanıyordu. Bu dosya artık üç ayrı gerçek senaryoyu
    doğruluyor."""

    def test_mouse_multitouch_debug_rings_are_disabled(self):
        """Sağ tık/Alt-Tab, Kivy'nin kırmızı sahte-touch halkalarını çizmemeli."""
        completed = _run(
            """
            import main
            from kivy.config import Config
            assert Config.get("input", "mouse") == "mouse,disable_multitouch"
            print("mouse-multitouch-disabled")
            """,
            extra_env={"ARCHLENCE_HEADLESS": "1"},
            strip_display=True,
        )
        self.assertEqual(
            completed.returncode, 0,
            msg=completed.stderr or completed.stdout,
        )
        self.assertIn("mouse-multitouch-disabled", completed.stdout)

    @unittest.skipUnless(
        _HAS_REAL_DISPLAY, "gerçek bir display sunucusu yok (ör. CI runner)"
    )
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

        # docs/ROADMAP.md Faz 1 madde 4: crash.log artık PROJECT_ROOT'ta
        # değil, platformdirs'in log dizininde. _run()'ın alt süreci
        # os.environ.copy()'den başladığı için (XDG_*/HOME değişmiyor),
        # log_dir()'in BURADA (aynı makine, aynı ortam) çözdüğü yol, alt
        # sürecin gerçekte yazdığı yolla aynı olmalı.
        crash_log = os.path.join(log_dir(), "crash.log")
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


class WorkingDirectoryIndependenceTest(unittest.TestCase):
    """Gerçek bir Windows kurulumunda ampirik olarak üretilen çökme:
    `Builder.load_file("ui/tools.kv")` gibi çağrılar göreli yol kullanıyor,
    yani çalışma dizininin (cwd) kurulum klasörüyle aynı olduğunu
    VARSAYIYORDU. Bu geliştirmede doğru (uygulama repo kökünden çalıştırılır)
    ama paketlenmiş bir .exe Başlat Menüsü/masaüstü kısayolundan ya da Inno
    Setup'ın kurulum-sonu "Başlat" adımından açıldığında YANLIŞ — gerçek bir
    kullanıcı kurulumunda `FileNotFoundError: 'ui/tools.kv'` ile açılışta
    çöküyordu (tam bu iz düşümüyle, kullanıcının kendi ekran görüntüsüne
    karşı doğrulandı).

    main.py artık başlangıçta `os.chdir(resource_dir())` çağırıyor. Bu test
    tam olarak o hatayı üreten koşulu yeniden kuruyor: `import main`'i,
    REPO KÖKÜNDEN BAŞKA bir çalışma dizininden tetikliyor."""

    def test_import_corrects_a_wrong_working_directory(self):
        """Pencere kurulup kurulmamasından TAMAMEN bağımsız: `os.chdir`,
        main.py'nin en başında, Window importundan ÖNCE gerçekleşiyor —
        bu yüzden ARCHLENCE_HEADLESS ile (gerçek pencere denemeden,
        CI'nın kendi koşuluyla aynı) test ediliyor."""
        with tempfile.TemporaryDirectory() as wrong_cwd:
            completed = _run(
                """
                import os
                before = os.getcwd()
                import main
                after = os.getcwd()
                print(f"BEFORE={before}")
                print(f"AFTER={after}")
                """,
                cwd=wrong_cwd,
                extra_env={"ARCHLENCE_HEADLESS": "1"},
                strip_display=True,
            )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn(f"BEFORE={os.path.realpath(wrong_cwd)}", completed.stdout)
        self.assertIn(f"AFTER={os.path.realpath(PROJECT_ROOT)}", completed.stdout)

    @unittest.skipUnless(
        _HAS_REAL_DISPLAY, "gerçek bir display sunucusu yok (ör. CI runner)"
    )
    def test_build_succeeds_when_launched_from_the_wrong_directory(self):
        """Asıl regresyon kanıtı: yalnızca cwd'nin düzeldiğini değil,
        `build()`'in (dolayısıyla `Builder.load_file("ui/tools.kv")`'nin)
        yanlış bir dizinden başlatılınca da GERÇEKTEN çökmediğini
        doğrular — kullanıcının bildirdiği hatanın birebir aynısı."""
        with tempfile.TemporaryDirectory() as wrong_cwd:
            completed = _run(
                """
                from kivy.clock import Clock
                import main

                app = main.ArchlenceApp()

                def _check(dt):
                    print("BUILD_SUCCEEDED")
                    app.stop()

                Clock.schedule_once(_check, 1.5)
                app.run()
                """,
                cwd=wrong_cwd,
            )
        self.assertEqual(
            completed.returncode, 0,
            msg=f"stdout={completed.stdout!r} stderr={completed.stderr!r}",
        )
        self.assertIn("BUILD_SUCCEEDED", completed.stdout)
        self.assertNotIn("FileNotFoundError", completed.stderr)


if __name__ == "__main__":
    unittest.main()
