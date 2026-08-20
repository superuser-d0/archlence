"""Bir ikonun glifi, yanındaki yazının üstüne biniyor mu — ölçer.

NEDEN VAR: bu kusur bu depoda ÜÇ KEZ ayrı ayrı çıktı ve üçünde de kullanıcı
tarafından bildirildi:

  1. "Aktif Borçlarım" / "Yaklaşan Ödemeler" / "Bekleyen İşlemler" /
     "Varlık Geçmişi" kart başlıkları,
  2. "Algoritmik Öngörü" kartının robot ikonu,
  3. Ayarlar → "Çıkış Yap" satırı (bu betikle bulundu).

Üçünde de sebep aynı: yatay bir kutudaki `MDIcon`'a `size_hint_x: None` +
`width` verilmemiş. O zaman ikonun kutusu 0px'e yakın kalıyor ama glif kendi
boyutunda çiziliyor ve yanındaki `MDLabel`'ın üstüne taşıyor. Komşu kartlarda
genişlik verildiği için hata gözden kaçıyor.

ÖLÇÜLEN İMZA: `icon.texture_size[0] > icon.width`. Sadece "kutular çakışıyor
mu" diye bakmak YETMİYOR — kutu 0px olduğunda çakışma yok gibi görünür,
taşan şey gliftir.

Bu ayrım pahalıya öğrenildi: bu betiğin ilk hâli genişliği 0 olan ikonları
"ölçülemez" diye ATLIYORDU, yani tam da yakalaması gereken durumu eliyordu.
Bilinen-bozuk duruma karşı koşturulup kırmızıya döndüğü doğrulandı.

Ölçek duyarlı olduğu için birden çok `KIVY_METRICS_DENSITY` değeriyle
koşturulabilir; %125/%150 Windows ölçeğinin uygulama tarafındaki karşılığı
budur.

    xvfb-run -a python scripts/dev/verify_icon_label_layout.py --output visual/icons
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Türkçe çıktı Windows'ta süreci ÖLDÜRMESİN — stdout yönlendirildiğinde kod
# sayfası cp1252'ye düşüyor ve 'ı' kodlanamıyor. Gerekçenin tamamı
# run_tests.py'ın tepesinde.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import NoTransition
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDIcon, MDLabel

from main import ArchlenceApp

#: Her sekme tek tek dolaşılır: ekran yöneticisinde yalnız AKTİF ekranın
#: widget'ları ağaçta bulunur, hepsini birden taramak mümkün değil.
TABS = ("home_tab", "assets_tab", "accounts_tab", "tools_tab", "settings_tab")


def _walk(widget):
    yield widget
    for child in widget.children:
        yield from _walk(child)


class IconLayoutVerifier(ArchlenceApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.findings = []
        self.pairs_checked = 0
        self.exit_code = 1

    def on_start(self):
        super().on_start()
        Clock.schedule_once(self._enter, 1.5)

    def _enter(self, _dt):
        self.root.ids.screen_manager.transition = NoTransition()
        self.root.ids.screen_manager.current = "home"
        nav = self.root.ids.bottom_nav
        nav.ids.tab_manager.transition = NoTransition()
        self._index = 0
        Clock.schedule_once(self._step, 1.5)

    def _step(self, _dt):
        if self._index >= len(TABS):
            self._finish()
            return
        tab = TABS[self._index]
        self.root.ids.bottom_nav.switch_tab(tab)
        Clock.schedule_once(lambda _d: self._scan(tab), 1.2)

    def _scan(self, tab):
        for box in [w for w in _walk(self.root) if isinstance(w, MDBoxLayout)]:
            if getattr(box, "orientation", "") != "horizontal":
                continue
            children = list(reversed(box.children))
            for i in range(len(children) - 1):
                icon, label = children[i], children[i + 1]
                if not isinstance(icon, MDIcon):
                    continue
                if not isinstance(label, MDLabel) or isinstance(label, MDIcon):
                    continue
                self.pairs_checked += 1
                glyph = icon.texture_size[0]
                if glyph > icon.width + 1:
                    self.findings.append({
                        "tab": tab,
                        "icon": icon.icon,
                        "label": str(label.text)[:40],
                        "glyph_width": round(float(glyph), 1),
                        "box_width": round(float(icon.width), 1),
                        "reason": "glif ayrılan kutudan geniş — yazıya biner",
                    })
                elif label.width > 0 and (label.x - (icon.x + icon.width)) < 0:
                    self.findings.append({
                        "tab": tab,
                        "icon": icon.icon,
                        "label": str(label.text)[:40],
                        "overlap_px": round(
                            float(label.x - (icon.x + icon.width)), 1),
                        "reason": "ikon ve etiket kutuları çakışıyor",
                    })
        self._index += 1
        Clock.schedule_once(self._step, 0.3)

    def _finish(self):
        report = {
            "density": round(float(dp(1)), 3),
            "pairs_checked": self.pairs_checked,
            "findings": self.findings,
        }
        (self.output / "icon-label-layout.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"incelenen ikon+etiket çifti: {self.pairs_checked} "
              f"(1dp = {dp(1):.2f}px)", flush=True)

        # SIFIR ÇİFT = ÖLÇÜM YAPILMADI demektir, "temiz" demek DEĞİL.
        # Bu betiğin bir ara sürümü ekran yöneticisi yüzünden hiçbir çift
        # bulamıyor ve yeşil dönüyordu.
        if self.pairs_checked == 0:
            print("::error::Hiç ikon+etiket çifti bulunamadı — ölçüm geçersiz",
                  flush=True)
            self.exit_code = 1
        elif self.findings:
            for item in self.findings:
                print(f"[BULGU] {item['tab']}: '{item['icon']}' -> "
                      f"'{item['label']}' — {item['reason']}", flush=True)
            print(f"::error::{len(self.findings)} ikon yanındaki yazıya biniyor",
                  flush=True)
            self.exit_code = 1
        else:
            print("Hiçbir ikon yanındaki yazıya binmiyor.", flush=True)
            self.exit_code = 0
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    app = IconLayoutVerifier(args.output)
    app.run()
    raise SystemExit(app.exit_code)
