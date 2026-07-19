import os, sys
# Proje kökünü path'e ekle ve oraya geç: main hem kökten import edilir hem de
# ui/dashboard.kv gibi göreli yolları çalışma dizininden yükler.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from kivy.clock import Clock
import main
app = main.FinoraApp()
def switch_tab(dt):
    app.root.ids.bottom_nav.switch_tab("assets_tab")
    print("Switched to assets_tab")

def stop_app(dt):
    # app.run() self.stop() çağrılmadan asla dönmez; test_ids.py'deki
    # self.stop() kalıbının burada da olmaması unittest discover'ı
    # sonsuza kadar bu modülün import'unda asılı bırakıyordu.
    app.stop()

Clock.schedule_once(switch_tab, 2)
Clock.schedule_once(stop_app, 2.5)
app.run()
