import multiprocessing
import os
import sys
import tempfile
import unittest


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):


        pass


_REAL_STDERR = sys.stderr


os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


if os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in ("1", "true", "yes"):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("KIVY_WINDOW", "sdl2")


if "XDG_DATA_HOME" not in os.environ:
    _sandbox = tempfile.mkdtemp(prefix="archlence-test-xdg-")
    os.environ["XDG_DATA_HOME"] = os.path.join(_sandbox, "data")
    os.environ["XDG_CACHE_HOME"] = os.path.join(_sandbox, "cache")
    os.environ["XDG_STATE_HOME"] = os.path.join(_sandbox, "state")


    os.environ["ARCHLENCE_HOME"] = os.path.join(_sandbox, "home")

def main():
    """Test paketini koşturur ve süreç çıkış kodunu döndürür.

    `if __name__ == "__main__"` GUARD'I ŞART — süs değil. Windows'ta
    `multiprocessing` varsayılan olarak `spawn` kullanır ve her alt süreç ANA
    MODÜLÜ YENİDEN İÇE AKTARIR. Guard olmadan, çocuk süreç açan her test
    (tests/test_single_instance.py) tüm 599 testlik paketi çocuk içinde BAŞTAN
    çalıştırıyordu. Windows CI log'unda "Ran 599 tests" ÜÇ KEZ görünmesinin
    sebebi buydu; ayrıca çocuk süreçler zamanında bitmediği için
    single-instance testleri "process hâlâ canlı" diye düşüyordu.
    """
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2, stream=_REAL_STDERR)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":


    multiprocessing.freeze_support()
    sys.exit(main())
