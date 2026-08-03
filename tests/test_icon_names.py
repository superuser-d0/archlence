"""Arayüzde kullanılan her MDI ikon adının gerçekten var olduğunu doğrular.

NEDEN VAR: KivyMD, tanımadığı bir ikon adını HATA VERMEDEN boş çizer. Yani
yanlış yazılmış ya da MDI setinde bulunmayan bir ad, ancak kullanıcı ekrana
bakıp "burada simge yok" dediğinde fark ediliyor. Sahada iki tanesi böyle
yakalandı: "Anahtar Kurtarma Paketi İçe Aktar" (`key-arrow-left`) ve
"Şifreleme Anahtarını Döndür" (`key-sync`) — ikisi de KivyMD 1.2.0'ın
setinde yok ve satırlar simgesiz görünüyordu.

Kapsam sınırı (bilinçli): yalnızca KAYNAKTA DÜZ METİN olarak yazılmış adlar
sınanır. Çalışma anında hesaplanan adlar (`icon: root.some_property`) burada
görülemez; onları yakalamanın tek yolu gerçek bir pencere açmaktır.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__"}

# KV'de her özellik kendi satırında durur, bu yüzden bir `icon:` satırındaki
# TÜM düz metinler ikon adayıdır (ör. `icon: "check" if x else "close"`).
_KV_ICON_LINE = re.compile(r"\bicon(?:_active|_inactive)?\s*:")
# Python'da yapıcı çağrısında başka kwarg'lar da bulunur (`halign="center"`),
# bu yüzden yalnızca `icon=` hemen ardındaki düz metin alınır.
_PY_ICON_VALUE = re.compile(r"\bicon(?:_active|_inactive)?\s*=\s*[\"']([a-z][a-z0-9-]*)[\"']")
_QUOTED = re.compile(r"[\"']([a-z][a-z0-9-]*)[\"']")


def _iter_source_files():
    for path in sorted(ROOT.rglob("*")):
        if path.suffix not in (".py", ".kv"):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == Path(__file__).name:
            continue
        yield path


def _declared_icon_names():
    """(dosya, satır_no, ikon_adı) üçlüleri."""
    found = []
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if path.suffix == ".kv":
                if _KV_ICON_LINE.search(line):
                    for name in _QUOTED.findall(line):
                        found.append((path, number, name))
            else:
                for name in _PY_ICON_VALUE.findall(line):
                    found.append((path, number, name))
    return found


class IconNameTest(unittest.TestCase):
    def test_every_icon_name_exists_in_the_bundled_mdi_set(self):
        from kivymd.icon_definitions import md_icons

        unknown = [
            f"{path.relative_to(ROOT)}:{number} -> {name!r}"
            for path, number, name in _declared_icon_names()
            if name not in md_icons
        ]
        self.assertEqual(
            [], unknown,
            "Bu adlar KivyMD'nin MDI setinde yok; ekranda BOŞ görünürler:\n  "
            + "\n  ".join(unknown),
        )

    def test_the_scanner_actually_finds_icons(self):
        """Tarayıcı sessizce hiçbir şey bulmuyorsa test yanlış yere güven verir."""
        names = _declared_icon_names()
        self.assertGreater(len(names), 40, "ikon taraması beklenenden az sonuç verdi")


if __name__ == "__main__":
    unittest.main()
