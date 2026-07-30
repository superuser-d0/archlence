"""Repeatable SDL visual check for search seam, caret, theme and resizing."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ["KIVY_NO_ARGS"] = "1"

from kivy.clock import Clock
from kivy.core.window import Window
from PIL import Image

from main import ArchlenceApp


def analyze_image(path, bounds):
    image = Image.open(path).convert("RGB")
    x, y, width, height = (int(round(value)) for value in bounds)
    top = image.height - (y + height)
    pixels = image.load()
    cap_center = x + width - height // 2
    sample_y = range(top + 4, top + height - 4)

    def column_mean(column):
        values = [
            sum(pixels[column, row]) / 3
            for row in sample_y
        ]
        return sum(values) / len(values)

    seam = column_mean(cap_center)
    neighbors = (
        column_mean(cap_center - 3) + column_mean(cap_center + 3)
    ) / 2
    seam_delta = abs(seam - neighbors)
    right_edge_delta = max(
        abs(column_mean(image.width - offset) - column_mean(image.width - 5))
        for offset in (1, 2)
    )
    return {
        "seam_delta": round(seam_delta, 3),
        "right_edge_delta": round(right_edge_delta, 3),
        "passed": seam_delta < 5 and right_edge_delta < 5,
    }


class VisualProbe(ArchlenceApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.steps = [
            ("light-unfocused", "Light", False, (800, 600), False),
            ("light-focused", "Light", True, (800, 600), False),
            ("dark-unfocused", "Dark", False, (800, 600), False),
            ("dark-focused-wide", "Dark", True, (1200, 800), False),
            ("dark-unfocused-fullscreen", "Dark", False, (1200, 800), True),
        ]

    def on_start(self):
        super().on_start()
        self.root.ids.screen_manager.current = "home"
        Clock.schedule_once(lambda _dt: self.run_step(0), 2)

    def run_step(self, index):
        if index == len(self.steps):
            report = self.output / "search-visual-report.json"
            report.write_text(
                json.dumps(self.results, indent=2), encoding="utf-8"
            )
            self.exit_code = 0 if all(
                result["passed"] for result in self.results
            ) else 1
            self.stop()
            return
        name, theme, focus, size, fullscreen = self.steps[index]
        Window.fullscreen = fullscreen
        Window.size = size
        self.theme_cls.theme_style = theme
        field = self.root.ids.home_search_input
        field.focus = focus
        field.text = "bütçe" if focus else ""
        Clock.schedule_once(
            lambda _dt: self.capture(index, name), 1
        )

    def capture(self, index, name):
        field = self.root.ids.home_search_input
        bar = field.parent
        requested = self.output / f"{name}.png"
        actual = Path(Window.screenshot(name=str(requested)))
        result = analyze_image(
            actual, (*bar.pos, *bar.size)
        )
        result.update(
            {
                "scenario": name,
                "image": str(actual),
                "density": float(getattr(__import__(
                    "kivy.metrics", fromlist=["Metrics"]
                ).Metrics, "density", 1)),
                "caret_expected": bool(field.focus),
                "caret_x": round(float(field._cursor_visual_pos[0]), 2),
                "field_left": round(float(field.x), 2),
                "field_right": round(float(field.right), 2),
            }
        )
        result["passed"] = (
            result["passed"]
            and (
                not field.focus
                or field.x <= field._cursor_visual_pos[0] <= field.right
            )
        )
        self.results.append(result)
        self.run_step(index + 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    app = VisualProbe(args.output)
    app.exit_code = 1
    app.run()
    raise SystemExit(app.exit_code)
