import os, sys


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

def main():
    from kivy.clock import Clock
    import main as app_module

    app = app_module.ArchlenceApp()

    def switch_tab(dt):
        app.root.ids.bottom_nav.switch_tab("assets_tab")
        print("Switched to assets_tab")

    def stop_app(dt):
        app.stop()

    Clock.schedule_once(switch_tab, 2)
    Clock.schedule_once(stop_app, 2.5)
    app.run()


if __name__ == "__main__":
    main()
