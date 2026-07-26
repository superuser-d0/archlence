import os
import sys

# Change dir so app finds kv files and assets correctly
os.chdir('/home/cem/Documents/archlence')
sys.path.insert(0, '/home/cem/Documents/archlence')

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.core.window import Window
from kivy.clock import Clock
import time

from main import ArchlenceApp

class CaptureApp(ArchlenceApp):
    def on_start(self):
        super().on_start()
        print("App started, waiting 1s before bypassing login...")
        Clock.schedule_once(self.bypass_login, 1.0)
        
    def bypass_login(self, dt):
        print("Bypassing login and forcing home screen...")
        
        # Force screen manager to 'home'
        sm = self.root.ids.screen_manager
        sm.current = "home"
        
        # Also clear the login errors just in case
        self.root.ids.login_error_label.text = ""
        self.root.ids.password_input.text = ""
        
        # Now schedule the screenshots
        Clock.schedule_once(self.take_screenshots, 2.0)
        
    def take_screenshots(self, dt):
        out_dir = "/home/cem/Desktop/archlence fotoğrafları"
        
        nav = self.root.ids.get('bottom_nav')
        if not nav:
            print("bottom_nav not found!")
            self.stop()
            return
            
        tabs = ["home_tab", "assets_tab", "accounts_tab", "tools_tab", "settings_tab"]
        
        def capture_tab(idx):
            if idx >= len(tabs):
                print("Done capturing.")
                self.stop()
                return
                
            tab_name = tabs[idx]
            print(f"Switching to {tab_name}...")
            
            try:
                nav.switch_tab(tab_name)
            except Exception as e:
                print(f"Failed to switch to {tab_name}: {e}")
            
            Clock.schedule_once(lambda dt: do_capture(idx, tab_name), 2.0)
            
        def do_capture(idx, tab_name):
            filepath = os.path.join(out_dir, f"{tab_name}.png")
            Window.screenshot(name=filepath)
            print(f"Saved {filepath}")
            capture_tab(idx + 1)

        capture_tab(0)

if __name__ == '__main__':
    app = CaptureApp()
    app.run()
