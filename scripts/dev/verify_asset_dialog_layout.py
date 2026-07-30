"""Capture small-window asset dialogs and fail when title/actions are clipped."""

import argparse
import json
import os
import sys
from pathlib import Path
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kivy.clock import Clock
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from mixins.asset_mixin import AssetMixin


class DialogHarness(AssetMixin, MDApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.report = []

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Amber"
        return MDScreen()

    def on_start(self):
        Window.size = (562, 521)
        Clock.schedule_once(self._gold, 0.2)

    def _capture(self, name, dialog):
        path = self.output / f"{name}.png"
        dialog.export_to_png(str(path))
        container = dialog.ids.container
        actions = dialog.ids.root_button_box
        passed = (
            dialog.top <= Window.height
            and dialog.y >= 0
            and actions.y >= dialog.y
            and actions.top <= dialog.top
            and container.height <= Window.height
        )
        self.report.append({
            "scenario": name,
            "passed": passed,
            "window": list(Window.size),
            "dialog": [dialog.x, dialog.y, dialog.width, dialog.height],
            "actions": [actions.x, actions.y, actions.width, actions.height],
            "image": str(path),
        })

    def _gold(self, _dt):
        self._asset_selected_type = "Altın"
        self._show_other_asset_dialog()
        Clock.schedule_once(self._gold_done, 0.5)

    def _gold_done(self, _dt):
        self._capture("gold-small-window", self.asset_dialog)
        self.asset_dialog.dismiss()
        Clock.schedule_once(self._bist, 0.6)

    def _bist(self, _dt):
        with mock.patch(
            "services.asset_service.fetch_bist100_prices"
        ):
            self._show_bist100_picker()
        Clock.schedule_once(self._bist_done, 0.8)

    def _bist_done(self, _dt):
        self._capture("bist-small-window", self._bist_dialog)
        self._bist_dialog.dismiss()
        report = self.output / "asset-dialog-report.json"
        report.write_text(json.dumps(self.report, indent=2), encoding="utf-8")
        self.stop()
        if not all(item["passed"] for item in self.report):
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    DialogHarness(args.output).run()


if __name__ == "__main__":
    main()
