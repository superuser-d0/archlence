#!/usr/bin/env python3
"""Capture the README's eight screenshots from an isolated sample profile.

Run this only with a profile created by ``seed_readme_profile.py``. The marker
check prevents the tool from opening a normal user profile, and the output
directory must be empty so an old screenshot can never be mistaken for a new
capture.

Example (use Xvfb on headless Linux):
    ARCHLENCE_HOME=/tmp/archlence-readme-profile \
      xvfb-run -a ../.venv/bin/python scripts/dev/capture_readme_screens.py \
      --output /tmp/archlence-readme-screens
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_MARKER = ".archlence-readme-sample"
SCREEN_NAMES = (
    "dashboard.png",
    "portfolio-overview.png",
    "asset-history.png",
    "mycards.png",
    "subscriptions.png",
    "debts-and-payments.png",
    "financial-tools.png",
    "settings.png",
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--delay", type=float, default=1.8,
        help="Seconds allowed for each target view to settle",
    )
    return parser.parse_args()


def require_isolated_profile() -> Path:
    raw = os.environ.get("ARCHLENCE_HOME")
    if not raw:
        raise SystemExit("ARCHLENCE_HOME must point to a generated sample profile.")
    profile = Path(raw).expanduser().resolve()
    if not (profile / SAMPLE_MARKER).is_file():
        raise SystemExit(f"Sample-profile marker not found: {profile / SAMPLE_MARKER}")
    return profile


def require_empty_output(path: Path) -> Path:
    output = path.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    return output


ARGS = parse_args()
PROFILE = require_isolated_profile()
OUTPUT = require_empty_output(ARGS.output)

os.environ["KIVY_NO_ARGS"] = "1"
os.environ.setdefault("KIVY_METRICS_DENSITY", "0.86")
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from kivy.config import Config

Config.set("graphics", "width", "1920")
Config.set("graphics", "height", "1080")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "fullscreen", "0")

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView

# Match the seed tool's strictly profile-local key provider. This prevents the
# GUI process from selecting a desktop keyring backend that differs from the
# headless seed process or from touching a real Archlence keyring entry.
from utils import key_provider


def isolated_key_provider(data_directory, *, keyring_module=None):
    fallback = key_provider.FileKeyProvider(
        os.path.join(str(data_directory), "encryption.key")
    )
    return key_provider.MigratingKeyProvider(
        None,
        fallback,
        key_provider.KeyProtectionStatus(
            "owner-only file", False,
            "OS key store unavailable; key kept in a local file with 0600 permissions.",
        ),
    )


key_provider.create_platform_key_provider = isolated_key_provider

from main import ArchlenceApp


class ReadmeCaptureApp(ArchlenceApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._capture_index = 0
        self._captures = [
            ("dashboard.png", "home_tab", self.prepare_dashboard),
            ("portfolio-overview.png", "assets_tab", self.prepare_portfolio),
            ("asset-history.png", "assets_tab", self.prepare_asset_history),
            ("mycards.png", "accounts_tab", self.prepare_accounts),
            ("subscriptions.png", "home_tab", self.prepare_subscriptions),
            ("debts-and-payments.png", "home_tab", self.prepare_debts),
            ("financial-tools.png", "tools_tab", self.prepare_tools),
            ("settings.png", "settings_tab", self.prepare_settings),
        ]

    def on_start(self):
        super().on_start()
        Window.size = (1920, 1080)
        Clock.schedule_once(self._enter_sample_profile, 1.0)

    def _enter_sample_profile(self, _dt):
        manager = self.root.ids.screen_manager
        manager.current = "home"
        self.root.ids.login_error_label.text = ""
        self.root.ids.password_input.text = ""
        self.change_home_filter(self.tr("1 Yıl"))
        Clock.schedule_once(self._capture_next, 2.5)

    def _capture_next(self, _dt=0):
        if self._capture_index >= len(self._captures):
            print(f"Captured {len(self._captures)} README screenshots from {PROFILE}")
            self.stop()
            return

        filename, tab_name, prepare = self._captures[self._capture_index]
        print(f"Preparing {filename} ({tab_name})")
        self.root.ids.bottom_nav.switch_tab(tab_name)
        Clock.schedule_once(lambda _ignored: prepare(filename), ARGS.delay)

    def _save(self, filename, extra_delay=0.8):
        def do_save(_dt):
            target = OUTPUT / filename
            saved_name = Window.screenshot(name=str(target))
            saved = Path(saved_name).resolve() if saved_name else target
            if saved != target and saved.exists():
                saved.replace(target)
            print(f"Saved {target}")
            self._capture_index += 1
            Clock.schedule_once(self._capture_next, 0.6)

        Clock.schedule_once(do_save, extra_delay)

    def _find_scroll(self, widget):
        # RecycleView is itself a ScrollView. For section positioning we need
        # the outermost page scroller, not an embedded list or horizontal row.
        current = getattr(widget, "parent", None)
        outermost = None
        seen = set()
        while current is not None and id(current) not in seen and len(seen) < 128:
            seen.add(id(current))
            if isinstance(current, ScrollView):
                outermost = current
            current = getattr(current, "parent", None)
        return outermost

    def _scroll_top(self, anchor_id):
        anchor = self.root.ids.get(anchor_id)
        scroll = self._find_scroll(anchor) if anchor else None
        if scroll:
            scroll.scroll_y = 1
            scroll.effect_y.value = 0
        return scroll

    def _scroll_to(self, target_id, fallback_y=0.5, padding=42):
        target = self.root.ids.get(target_id)
        scroll = self._find_scroll(target) if target else None
        if scroll and target:
            scroll.scroll_to(target, padding=padding, animate=False)
        elif scroll:
            scroll.scroll_y = fallback_y
        return scroll

    def prepare_dashboard(self, filename):
        self.change_home_filter(self.tr("1 Yıl"))
        self.refresh_dashboard_data(list_filter="1 Yıl")
        self._scroll_top("chart_master_box")
        self._save(filename, 1.5)

    def prepare_portfolio(self, filename):
        self.load_active_assets()
        self.load_asset_history()
        # Use a known top-content anchor; bottom-navigation items are not root ids.
        anchor = self.root.ids.get("active_assets_container")
        scroll = self._find_scroll(anchor) if anchor else None
        if scroll:
            scroll.scroll_y = 1
        self._save(filename, 1.5)

    def prepare_asset_history(self, filename):
        self.load_asset_history()
        self._scroll_to("asset_history_list", fallback_y=0.32, padding=70)
        self._save(filename, 1.2)

    def prepare_accounts(self, filename):
        self.render_accounts()
        anchor = self.root.ids.get("cards_container") or self.root.ids.get("accounts_container")
        scroll = self._find_scroll(anchor) if anchor else None
        if scroll:
            scroll.scroll_y = 1
        self._save(filename, 1.0)

    def prepare_subscriptions(self, filename):
        self.refresh_insights()
        self._scroll_to("active_subscriptions_rv", fallback_y=0.56, padding=54)
        self._save(filename, 1.4)

    def prepare_debts(self, filename):
        self.load_active_debts()
        self.refresh_insights()
        self._scroll_to("active_debts_container", fallback_y=0.24, padding=54)
        self._save(filename, 1.4)

    def prepare_tools(self, filename):
        # Keep the complete tool set in frame: budget, calendar, calculators,
        # savings goals, scenarios and data reset are all represented by the
        # real navigation cards on this page.
        anchor = self.root.ids.get("budget_tool_card")
        scroll = self._find_scroll(anchor) if anchor else None
        if scroll:
            scroll.scroll_y = 1
        self._save(filename, 1.0)

    def prepare_settings(self, filename):
        anchor = self.root.ids.get("settings_list")
        scroll = self._find_scroll(anchor) if anchor else None
        if scroll:
            scroll.scroll_y = 1
        self._save(filename, 0.9)


if __name__ == "__main__":
    ReadmeCaptureApp().run()
