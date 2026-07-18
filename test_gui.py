from kivy.clock import Clock
import main
app = main.FinoraApp()
def switch_tab(dt):
    app.root.ids.bottom_nav.switch_tab("assets_tab")
    print("Switched to assets_tab")

Clock.schedule_once(switch_tab, 2)
app.run()
