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

Clock.schedule_once(switch_tab, 2)
app.run()
