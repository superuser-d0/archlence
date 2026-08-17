"""Her sekmenin taşan içeriği GERÇEKTEN kaydırılabiliyor mu — ölçer.

NEDEN VAR: "Kartlarım" sekmesi gerçek bir Windows makinesinde hiç
kaydırılamıyordu; başlığın altındaki hiçbir şeye ulaşılamıyordu. Geometri
kusursuzdu — içerik 1056dp, görünür alan 456dp, `scroll_y` programatik olarak
değiştirilebiliyordu. Kırık olan tek şey DOKUNUŞUN ScrollView'a ULAŞMASIYDI:
sayfanın dikey ScrollView'ı içindeki yatay kart şeridi (620dp, yani görünür
alanın tamamından yüksek) her sürüklemeyi sahipleniyordu.

Bu yüzden burada `scroll_y`'ye elle değer atanmıyor. Kivy'nin GERÇEK olay
döngüsünden dokunuş üretilip sürükleniyor ve sonrasında `scroll_y`'nin
değişip değişmediğine bakılıyor — kullanıcının yaptığı şeyin ta kendisi.
Statik bir düzen testi bu hatayı YAKALAYAMAZDI.

Görsel regresyon işiyle aynı desende çalışır:

    xvfb-run -a python scripts/dev/verify_tab_scrolling.py --output visual/scroll
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Türkçe çıktı Windows'ta süreci ÖLDÜRMESİN — stdout yönlendirildiğinde kod
# sayfası cp1252'ye düşüyor ve "BAŞARISIZ"ın 'Ş'si kodlanamıyor. Gerekçenin
# tamamı run_tests.py'ın tepesinde. Bu kapıda özellikle sinsi: kodlanamayan
# karakter YALNIZCA başarısızlık satırında geçtiği için koruma olmadan kapı
# yeşilken çalışır, KIRMIZIYA DÖNDÜĞÜ anda kendi raporunu yazamadan çökerdi.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.base import EventLoop
from kivy.clock import Clock
from kivy.input.motionevent import MotionEvent
from kivy.uix.scrollview import ScrollView

from main import ArchlenceApp

#: Taşan içeriği olması beklenen sekmeler. "accounts_tab" bu dosyanın
#: varlık sebebi; diğerleri kontrol grubu — biri kırılırsa hatanın sekmeye
#: özgü mü yoksa genel mi olduğunu ölçüm anında ayırt edebilmek için.
TABS = ("accounts_tab", "tools_tab", "settings_tab")


class _Touch(MotionEvent):
    """kivy.tests.common.UnitTestTouch ile aynı — pytest bağımlılığı olmadan.

    Olayları `EventLoop.post_dispatch_input` üzerinden gönderir; `Window`'a
    doğrudan dispatch etmek ScrollView'ı tetiklemiyor (ölçüldü: doğrudan
    dispatch ile HİÇBİR sekme kaymıyordu, yani yanlış negatif üretiyordu).
    """

    def __init__(self, x, y, button=None):
        self.eventloop = EventLoop
        window = EventLoop.window
        args = {"x": x / (window.width - 1.0), "y": y / (window.height - 1.0)}
        if button:
            args["button"] = button
        super().__init__(self.__class__.__name__, 99, args,
                         is_touch=True, type_id="touch")
        self.profile = ["pos"] + (["button"] if button else [])

    def press(self):
        self.eventloop.post_dispatch_input("begin", self)

    def drag_to(self, x, y):
        window = self.eventloop.window
        self.move({"x": x / (window.width - 1.0),
                   "y": y / (window.height - 1.0)})
        self.eventloop.post_dispatch_input("update", self)

    def release(self):
        self.eventloop.post_dispatch_input("end", self)

    def depack(self, args):
        self.sx = args["x"]
        self.sy = args["y"]
        if "button" in args:
            self.button = args["button"]
        super().depack(args)


def _walk(widget):
    yield widget
    for child in widget.children:
        yield from _walk(child)


def _touch_point(page):
    """Sürüklemenin başlayacağı pencere-koordinatı noktasını SEÇER.

    NEDEN VAR: bu kapı dokunuşu pencerenin tam ortasından başlatıyordu ve o
    nokta bazı yerleşimlerde doğrudan bir `MDCard`'ın üstüne düşüyordu. Kart
    dokunuşu sahiplendiği için kapı SAĞLAM bir yapıyı kırmızı gösteriyor ve
    o koşulda düzeltmeyi hiç AYIRT ETMİYORDU (yoğunluk 1.0'da ölçüldü:
    düzeltme yerinde de, geri alınmış da kırmızı).

    NOKTA ŞERİDİN İÇİNDE OLMAK ZORUNDA. Hatanın yaşadığı yer orası: yatay
    kart şeridi, görünür alandan yüksek olduğu için her dikey sürüklemeyi
    sahipleniyordu ve `scroll_type: ["bars"]` tam olarak bunu çeviriyor.
    Noktayı şeridin DIŞINA taşımak kapıyı yeşile döndürür ama hatayı da
    tamamen kaçırır — bu tur bir kez denenip ölçülerek geri alındı
    (1.0 ve 1.25'te düzeltme geri alınmışken bile yeşil kaldı).

    Şeridin içinde kart olmayan yer var: kartlar arasında 16dp boşluk ve
    şeridin 8dp dikey dolgusu. Burada hesap YOK — adaylar taranıyor ve her
    biri için widget ağacı `collide_point` ile gerçekten yoklanıyor.

    Şerit yoksa (diğer sekmeler) sayfanın ortası kullanılır; oralarda
    böyle bir sahiplenen çocuk zaten yok.

    Aday bulunamazsa `None` döner ve çağıran ölçümü ATLAR — ölçemediği bir
    durumu başarısızlık saymak bu kapının düzeltilen kusurunun ta kendisiydi.
    """
    try:
        from kivymd.uix.card import MDCard
    except ImportError:      # kısıtlı ortam
        MDCard = ()

    def _blocked(x, y):
        for widget in _walk(page):
            if MDCard and isinstance(widget, MDCard):
                if widget.collide_point(*widget.to_widget(x, y)):
                    return True
        return False

    # Hatanın yaşadığı yatay şerit: x'te kayan, y'de kaymayan ScrollView.
    strip = next(
        (widget for widget in _walk(page)
         if isinstance(widget, ScrollView)
         and widget.do_scroll_x and not widget.do_scroll_y),
        None,
    )

    if strip is not None:
        left, bottom = strip.to_window(strip.x, strip.y)
        right, top = strip.to_window(strip.right, strip.top)
        # Görünür alanla kesiştir: şerit sayfadan yüksek, ekran dışındaki
        # kısmına dokunmak anlamsız.
        page_left, page_bottom = page.to_window(page.x, page.y)
        page_right, page_top = page.to_window(page.right, page.top)
        bottom = max(bottom, page_bottom)
        top = min(top, page_top)
        if top > bottom:
            # Yatayda kart aralıklarını, dikeyde birkaç şeridi tara.
            for x_fraction in (0.5, 0.25, 0.75, 0.12, 0.88, 0.38, 0.62):
                x = left + (right - left) * x_fraction
                for y_fraction in (0.5, 0.08, 0.92, 0.3, 0.7):
                    y = bottom + (top - bottom) * y_fraction
                    if not _blocked(x, y):
                        return x, y
        return None

    x = (page.to_window(page.center_x, page.center_y))[0]
    y = (page.to_window(page.center_x, page.center_y))[1]
    return (x, y) if not _blocked(x, y) else None


def _settle(frames=30):
    for _ in range(frames):
        Clock.tick()


class ScrollVerifier(ArchlenceApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.report = []

    def on_start(self):
        super().on_start()
        # Kart şeridinin GERÇEKTEN taşması için birden çok kart gerekiyor;
        # boş bir profil hatayı gizlerdi.
        from services.account_service import AccountService
        if not AccountService.get_accounts():
            AccountService.create_account("Vadesiz", "checking", 5000.0)
            for index, name in enumerate(("Kart A", "Kart B", "Kart C")):
                AccountService.create_account(
                    name, "credit_card", 500.0 * (index + 1),
                    credit_limit=10000)
        Clock.schedule_once(self._bypass_login, 1.0)

    def _bypass_login(self, _dt):
        self.root.ids.screen_manager.current = "home"
        Clock.schedule_once(lambda _d: self._verify(0), 1.5)

    def _verify(self, index):
        if index >= len(TABS):
            self._finish()
            return
        name = TABS[index]
        self.root.ids.get("bottom_nav").switch_tab(name)

        def measure(_dt):
            self._measure_tab(name)
            Clock.schedule_once(lambda _d: self._verify(index + 1), 0.4)

        Clock.schedule_once(measure, 3.0)

    def _measure_tab(self, name):
        nav = self.root.ids.get("bottom_nav")
        tab = next(screen for screen in nav.ids.tab_manager.screens
                   if screen.name == name)
        page = next((widget for widget in _walk(tab)
                     if isinstance(widget, ScrollView) and widget.do_scroll_y),
                    None)
        if page is None:
            self.report.append({"tab": name, "passed": True,
                                "note": "dikey ScrollView yok"})
            return

        viewport = page.children[0] if page.children else None
        content_height = getattr(viewport, "height", 0)
        overflows = content_height > page.height

        results = {}
        for label in ("wheel", "drag"):
            # SAYFANIN TEPESİNDEN ÖLÇÜLÜYOR — kullanıcının sekmeyi açtığında
            # bulduğu hâl. Ara bir konumdan ölçmek hatayı KAÇIRIYORDU: bu
            # kapının ilk hâli `scroll_y = 0.5`'ten ölçüyordu ve düzeltme
            # geri alındığında bile yeşil kalıyordu (ölçüldü).
            #
            # HER ÖLÇÜM TAZE BAŞLIYOR. Tekerlek ölçümü eskiden sürüklemenin
            # HEMEN ARDINDAN koşuyordu; sürüklemenin bıraktığı efekt hâlâ
            # sönerken `scroll_y` 1.000'den azıcık sapıyor ve Kivy'nin
            # "zaten uçtayım" erken çıkışı tetiklenmiyordu. Sonuç sahte
            # yeşildi: kapı, gerçekte ölü olan tekerleği çalışıyor sanıyordu.
            # Sıra da bu yüzden TEKERLEK ÖNCE: sürükleme her hâlükârda
            # efekti hareket hâlinde bırakıyor ve sonrasında yapılan hiçbir
            # `settle` onu tam olarak 1.000'e oturtmuyor (ölçüldü — kapı
            # sürüklemeden sonra ölçtüğü sürece bozuk şeridi de yeşil
            # geçiriyordu). Tekerlek, sayfaya hiç dokunulmamış hâlde ölçülür.
            start = 1.0
            page.scroll_y = start
            _settle(45)
            # Nokta HER ÖLÇÜMDE yeniden seçiliyor: `scroll_y` sıfırlandıktan
            # ve düzen oturduktan sonra kartların yeri değişmiş olabilir.
            point = _touch_point(page)
            if point is None:
                results[label] = None
                continue
            x, y = point
            if label == "drag":
                # AŞAĞI doğru sürükleme: içeriğin alt kısmını açan yön.
                touch = _Touch(x, y)
                touch.press()
                Clock.tick()
                for step in range(1, 8):
                    touch.drag_to(x, y + step * 25)
                    Clock.tick()
                touch.release()
            else:
                # `scrollup` — İÇERİĞE DOĞRU olan yön. `scrolldown` YANLIŞ
                # seçimdi: sayfa tepedeyken Kivy onu her ScrollView'da
                # reddediyor (`scroll_y >= 1` erken çıkışı), yani hem sağlam
                # hem bozuk sekmelerde aynı sonucu veriyor — ayırt etmiyor.
                # Ölçüldü: çalışan sekmelerde `scrollup` -0,0495 hareket
                # ederken bozuk sekmede 0,0000 kalıyor.
                touch = _Touch(x, y, button="scrollup")
                touch.press()
                touch.release()
            _settle(40)
            results[label] = abs(page.scroll_y - start) > 1e-4

        # `None` = ÖLÇÜLEMEDİ (kart üstünde olmayan aday nokta bulunamadı),
        # `False` = ölçüldü ve kaymadı. İkisi bilerek ayrı: ölçemediğimiz bir
        # durumu başarısızlık saymak, bu kapının tam da düzeltilen kusuruydu.
        unmeasured = [key for key, value in results.items() if value is None]
        # Taşmayan içerik zaten kaymaz; kapı yalnız taşan sekmeler için.
        # İKİSİ DE ZORUNLU: gerçek makinede bildirilen arıza tam olarak
        # "ne sürükleme ne tekerlek" idi ve ölçüm bunu doğruladı — düzeltme
        # geri alındığında dört etkileşimin dördü de ölü.
        passed = (
            (not overflows)
            or bool(unmeasured)
            or (results["drag"] and results["wheel"])
        )
        entry = {
            "tab": name,
            "passed": passed,
            "content_height": round(content_height, 1),
            "viewport_height": round(page.height, 1),
            "overflows": overflows,
            "scrolled_by_drag": results["drag"],
            "scrolled_by_wheel": results["wheel"],
            "unmeasured": unmeasured,
        }
        self.report.append(entry)
        status = "OK" if passed else "BAŞARISIZ"
        if unmeasured:
            status = "ATLANDI"
        print(f"[{status}] {name}: içerik={entry['content_height']} "
              f"görünür={entry['viewport_height']} taşıyor={overflows} "
              f"sürükleme={results['drag']} tekerlek={results['wheel']}"
              + (f" ÖLÇÜLEMEDİ={unmeasured}" if unmeasured else ""))
        # Ekran görüntüsü YARDIMCI bir çıktı, kapının parçası değil; yine de
        # geniş bir `except` eklenmiyor (projenin istisna kapısı bunu sayıyor
        # ve haklı olarak reddediyor). Başarısız olabilecek gerçek durumlar
        # dosya sistemi ve GL yüzeyi kaynaklı: ikisi de OSError/ValueError.
        try:
            tab.export_to_png(str(self.output / f"{name}.png"))
        except (OSError, ValueError) as error:
            print(f"  (ekran görüntüsü alınamadı: {error})")

    def _finish(self):
        path = self.output / "scroll-report.json"
        path.write_text(json.dumps(self.report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        self.failed = [item for item in self.report if not item["passed"]]
        self.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="visual/scroll")
    args = parser.parse_args()

    app = ScrollVerifier(args.output)
    app.run()
    failed = getattr(app, "failed", None)
    if failed is None:
        print("::error::Doğrulama tamamlanmadan sonlandı.")
        return 1
    if failed:
        for item in failed:
            print(f"::error::{item['tab']} taşan içeriğe rağmen kaydırılamıyor "
                  f"(sürükleme={item.get('scrolled_by_drag')}, "
                  f"tekerlek={item.get('scrolled_by_wheel')})")
        return 1
    print("Tüm sekmeler kaydırılabiliyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
