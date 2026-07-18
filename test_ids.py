from kivy.lang import Builder
from kivymd.app import MDApp
from kivy.properties import ColorProperty
class TestApp(MDApp):
    home_circle_color = ColorProperty((0,0,0,0))
    def build(self):
        return Builder.load_file("ui/dashboard.kv")
    def on_start(self):
        print("IDS:", list(self.root.ids.keys()))
        self.stop()
TestApp().run()
