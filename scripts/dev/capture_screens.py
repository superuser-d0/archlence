"""Geliştirici ekran görüntüsü aracı.

Bu araç aktif Archlence kullanıcı-veri dizinini okur ve giriş ekranını atlar.
Gerçek kullanıcı verisiyle çalıştırmayın; QA için XDG_DATA_HOME/XDG_CACHE_HOME
değişkenlerini geçici bir dizine yönlendirin.
"""
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.core.window import Window
from kivy.clock import Clock
from main import ArchlenceApp


class CaptureApp(ArchlenceApp):
    def __init__(self, output_dir, delay=2.0, **kwargs):
        super().__init__(**kwargs)
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.capture_delay = float(delay)

    def on_start(self):
        super().on_start()
        print("App started; isolated QA login is being bypassed.")
        Clock.schedule_once(self.bypass_login, 1.0)

    def bypass_login(self, dt):
        sm = self.root.ids.screen_manager
        sm.current = "home"
        self.root.ids.login_error_label.text = ""
        self.root.ids.password_input.text = ""
        Clock.schedule_once(self.take_screenshots, 2.0)

    def take_screenshots(self, dt):
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
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception(f"Failed to switch to {tab_name}")

            Clock.schedule_once(
                lambda _dt: do_capture(idx, tab_name),
                self.capture_delay,
            )

        def do_capture(idx, tab_name):
            filepath = self.output_dir / f"{tab_name}.png"
            Window.screenshot(name=str(filepath))
            print(f"Saved {filepath}")
            capture_tab(idx + 1)

        capture_tab(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "docs" / "screenshots"),
        help="PNG çıktı dizini",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Sekme değişiminden görüntüye kadar beklenecek saniye",
    )
    args = parser.parse_args()
    app = CaptureApp(args.output, args.delay)
    app.run()
