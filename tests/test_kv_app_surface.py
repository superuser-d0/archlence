"""`.kv` içinde geçen her `app.<isim>` gerçekten `ArchlenceApp`'te var mı.

NEDEN VAR: Kivy `.kv` dosyasındaki `app.foo` ifadesini ÇALIŞMA ZAMANINDA
çözer. `foo` yoksa ne derleme hatası ne uyarı olur — düğme sessizce hiçbir şey
yapmaz. Bu teorik bir incelik değil, bu depoda İKİ KEZ gerçekleşti:

  * v0.0.11'e kadar ana sayfadaki arama çubuğu hiçbir işleyiciye bağlı değildi
    ve kusuru bir kullanıcı bildirdi; tek kapısı yalnızca çubuğun nasıl
    GÖRÜNDÜĞÜNÜ ölçüyordu.
  * Aynı tarama zilin de `MDIconButton` olduğunu ama hiçbir `on_release`
    taşımadığını ortaya çıkardı — parmağın altında dalga animasyonu oynayıp
    hiçbir şey yapıyordu.

İkisi de "kontrol duruyor ama ölü" sınıfıydı ve ikisini de bir kapı değil,
elle bakış yakaladı. Bu dosya o boşluğu kapatır.

This is also the prerequisite for safely splitting `main.py` into controllers
while retaining thin delegates on `ArchlenceApp`. KV files depend on `app.` in
hundreds of places, so a misspelled delegate would otherwise fail silently.

KAPSAM SINIRI: burada isimlerin VAR OLDUĞU doğrulanır, DOĞRU ÇALIŞTIĞI değil.
Arama çubuğu vakası tam da bunu hatırlatıyor — `app.on_home_search_text`
mevcut olsaydı ama hiçbir şey yapmasaydı bu kapı yine yeşil kalırdı. Davranış
kapsamı ilgili servis/mixin testlerinin işi.
"""
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


_APP_REFERENCE = re.compile(r"\bapp\.([A-Za-z_][A-Za-z0-9_]*)")


_ROOT = Path(__file__).resolve().parents[1]


def _kv_files():
    """Depodaki `.kv` dosyaları — `.venv` HARİÇ.

    Sanal ortam Kivy/KivyMD'nin kendi kv'lerini taşıyor; onlar bu uygulamanın
    `app` nesnesine bağlı değil ve taranırlarsa yüzlerce yanlış pozitif üretir.
    """
    return sorted(
        path for path in _ROOT.rglob("*.kv")
        if ".venv" not in path.parts and "build" not in path.parts
    )


def _references():
    """(isim, "dosya:satır") çiftleri.

    TAM SATIR YORUMLARI atlanır. Satır sonu yorumları AYIKLANMAZ: `.kv`
    içinde `#` renk kodlarının (`#14B85F`) içinde de geçiyor ve gövdeden
    ayırmak güvenilir değil. Sonuç olarak bir yorumda geçen `app.eskiAd` da
    kapıyı kırmızıya döndürür — bu bilinçli: bayat bir yorum da düzeltilmeye
    değer ve yanlış negatif vermekten iyidir.
    """
    found = []
    for path in _kv_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            for match in _APP_REFERENCE.finditer(line):
                found.append(
                    (match.group(1), f"{path.relative_to(_ROOT)}:{lineno}")
                )
    return found


class KvAppSurfaceTest(unittest.TestCase):

    def setUp(self):


        from main import ArchlenceApp
        self.app_class = ArchlenceApp

    def test_kv_files_are_actually_found(self):
        """Kapının ölçtüğü bir şey olduğunu sabitler.

        Dosya bulma bozulursa (yol değişikliği, glob hatası) referans listesi
        boşalır ve kapı hiçbir şey ölçmeden yeşil kalırdı — sessizce işe
        yaramaz bir teste dönüşür.
        """
        files = _kv_files()
        self.assertTrue(files, "hiç .kv dosyası bulunamadı")
        names = {name for name, _ in _references()}
        self.assertGreater(
            len(names), 20,
            f"beklenenden az `app.` referansı bulundu ({len(names)}); "
            "tarama bozulmuş olabilir",
        )

    def test_every_app_reference_exists_on_the_app_class(self):
        """ASIL KAPI. Eksik bir isim = sessizce ölü bir kontrol."""
        missing = {}
        for name, where in _references():
            if not hasattr(self.app_class, name):
                missing.setdefault(name, []).append(where)

        if missing:
            detail = "\n".join(
                f"  app.{name} — {', '.join(sites[:4])}"
                + (f" (+{len(sites) - 4} yer)" if len(sites) > 4 else "")
                for name, sites in sorted(missing.items())
            )
            self.fail(
                "`.kv` içinde `ArchlenceApp`'te KARŞILIĞI OLMAYAN referanslar "
                f"var ({len(missing)} isim). Kivy bunları çalışma zamanında "
                "çözer, yani bu kontroller sessizce hiçbir şey yapmaz:\n"
                + detail
                + "\n\nÇözüm: adı `ArchlenceApp` üzerinde tanımla (metot, "
                "property ya da delege), ya da `.kv`'deki referansı düzelt."
            )

    def test_a_known_missing_name_would_be_caught(self):
        """Kapının bilinen-bozuk duruma karşı doğrulaması.

        Gerçek `.kv`'yi bozmadan aynı mantığı uydurma bir adla çalıştırır:
        `hasattr` kontrolü gerçekten ayırt ediyor mu.
        """
        self.assertFalse(
            hasattr(self.app_class, "kesinlikle_olmayan_bir_metot"),
            "test varsayımı bozuldu: uydurma ad gerçekten var",
        )
        self.assertTrue(
            hasattr(self.app_class, "tr"),
            "`app.tr` bulunamadı — kontrol mekanizması çalışmıyor olabilir",
        )


if __name__ == "__main__":
    unittest.main()
