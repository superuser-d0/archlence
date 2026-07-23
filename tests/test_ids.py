import os, sys
# ui/dashboard.kv göreli yolla yüklendiği için proje köküne geçilir
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

def main():
    from kivy.lang import Builder
    from kivymd.app import MDApp
    from kivy.properties import ColorProperty, StringProperty

    class IdsApp(MDApp):
        home_circle_color = ColorProperty((0, 0, 0, 0))
        active_category_type = StringProperty("income")

        def build(self):
            return Builder.load_file("ui/dashboard.kv")

        def on_start(self):
            print("IDS:", list(self.root.ids.keys()))
            self.stop()

    IdsApp().run()


if __name__ == "__main__":
    main()
