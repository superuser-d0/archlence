"""What-if mixin veri akışının pencere gerektirmeyen testleri."""

import sys
import types
import unittest
from unittest import mock


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


class _Widget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


_stubs = {
    "kivy": _module("kivy"),
    "kivy.metrics": _module("kivy.metrics", dp=lambda value: value),
    "kivymd": _module("kivymd"),
    "kivymd.toast": _module("kivymd.toast", toast=lambda *args: None),
    "kivymd.uix": _module("kivymd.uix"),
    "kivymd.uix.boxlayout": _module("kivymd.uix.boxlayout", MDBoxLayout=_Widget),
    "kivymd.uix.button": _module(
        "kivymd.uix.button", MDFlatButton=_Widget, MDRaisedButton=_Widget,
    ),
    "kivymd.uix.dialog": _module("kivymd.uix.dialog", MDDialog=_Widget),
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget),
    "kivymd.uix.segmentedcontrol": _module(
        "kivymd.uix.segmentedcontrol",
        MDSegmentedControl=_Widget,
        MDSegmentedControlItem=_Widget,
    ),
    "kivymd.uix.textfield": _module(
        "kivymd.uix.textfield", MDTextField=_Widget,
    ),
    "ui.charts": _module("ui.charts", ScenarioComparisonChart=_Widget),
    "ui.i18n": _module("ui.i18n", tr=lambda text: text),
    "ui.theme": _module("ui.theme", accent=lambda *args: [0, 0, 0, 1]),
}
with mock.patch.dict(sys.modules, _stubs):
    import mixins.scenario_mixin as scenario_module
    ScenarioMixin = scenario_module.ScenarioMixin


class ScenarioMixinTest(unittest.TestCase):

    def setUp(self):
        self.host = mock.Mock()
        self.host._scenario_base_metrics = {
            "base_balance": 1000.0,
            "base_daily_income": 100.0,
            "base_daily_expense": 80.0,
        }
        self.host.scenario_income_input.text = "20"
        self.host.scenario_expense_input.text = "-25"
        self.host.scenario_adjustment_input.text = "-100"
        self.host._scenario_days = 30
        self.host.scenario_chart = mock.Mock()
        self.host.scenario_summary = mock.Mock()
        self.host._apply_scenario_result = (
            lambda result: ScenarioMixin._apply_scenario_result(self.host, result)
        )

    def test_inputs_produce_comparison_series_and_summary(self):
        ScenarioMixin.calculate_scenario(self.host)

        base_series, scenario_series = (
            self.host.scenario_chart.set_series.call_args.args
        )
        self.assertEqual(len(base_series), 31)
        self.assertEqual(len(scenario_series), 31)
        self.assertEqual(base_series[0], (0, 1000.0))
        self.assertEqual(scenario_series[0], (0, 900.0))
        self.assertIn("30 gün sonra", self.host.scenario_summary.text)
        self.assertIn("Taban senaryoya göre", self.host.scenario_summary.text)

    def test_horizon_callback_selects_365_days(self):
        item = types.SimpleNamespace(text="365 Gün")

        ScenarioMixin._on_scenario_horizon(self.host, None, item)

        self.assertEqual(self.host._scenario_days, 365)


if __name__ == "__main__":
    unittest.main()
