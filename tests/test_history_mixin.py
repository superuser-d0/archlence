"""Bakiye zaman makinesi UI orkestrasyonunun headless testleri."""

import datetime
import re
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
        self.children = []
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_widget(self, widget):
        self.children.append(widget)

    def clear_widgets(self):
        self.children.clear()

    def bind(self, **kwargs):
        return None

    def setter(self, name):
        return lambda _instance, value: setattr(self, name, value)


class _Clock:
    @staticmethod
    def schedule_once(callback, timeout=0):
        return callback(0)


class _ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


_stubs = {
    "kivy": _module("kivy"),
    "kivy.clock": _module("kivy.clock", Clock=_Clock),
    "kivy.metrics": _module("kivy.metrics", dp=lambda value: value),
    "kivymd": _module("kivymd"),
    "kivymd.uix": _module("kivymd.uix"),
    "kivymd.uix.boxlayout": _module("kivymd.uix.boxlayout", MDBoxLayout=_Widget),
    "kivymd.uix.button": _module("kivymd.uix.button", MDFlatButton=_Widget),
    "kivymd.uix.dialog": _module("kivymd.uix.dialog", MDDialog=_Widget),
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget),
    "kivymd.uix.pickers": _module("kivymd.uix.pickers", MDDatePicker=_Widget),
    "ui.theme": _module("ui.theme", accent=lambda *args: [0, 0, 0, 1]),
    "ui.i18n": _module(
        "ui.i18n", tr=lambda text: text,
        trf=lambda template, language=None, **params: re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), template),
    ),
}
with mock.patch.dict(sys.modules, _stubs):
    import mixins.history_mixin as history_module
    HistoryMixin = history_module.HistoryMixin


class HistoryMixinTest(unittest.TestCase):

    def setUp(self):
        self.host = mock.Mock()
        self.host._history_dialog = mock.Mock()
        self.container = _Widget()

    @mock.patch("services.history_service.diff_between")
    def test_custom_range_calls_diff_and_renders(self, diff_between):
        result = {"from": "2026-01-01", "to": "2026-02-01"}
        diff_between.return_value = result
        self.host._render_history = mock.Mock()

        with (
            mock.patch.object(history_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(history_module.Clock, "schedule_once",
                              side_effect=lambda callback, timeout=0: callback(0)),
        ):
            HistoryMixin._load_history_range(
                self.host, self.container, "2026-01-01", "2026-02-01"
            )

        diff_between.assert_called_once_with("2026-01-01", "2026-02-01")
        self.host._render_history.assert_called_once_with(self.container, result)

    @mock.patch("services.history_service.get_balance_at")
    def test_point_in_time_calls_service_and_renders(self, get_balance_at):
        result = {"date": "2026-02-01", "total_balance": 1234.0}
        get_balance_at.return_value = result
        self.host._render_balance_at = mock.Mock()

        with (
            mock.patch.object(history_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(history_module.Clock, "schedule_once",
                              side_effect=lambda callback, timeout=0: callback(0)),
        ):
            HistoryMixin._load_balance_at(
                self.host, self.container, "2026-02-01"
            )

        get_balance_at.assert_called_once_with("2026-02-01")
        self.host._render_balance_at.assert_called_once_with(self.container, result)

    def test_custom_picker_collects_start_then_end(self):
        selected_dates = iter((
            datetime.date(2026, 1, 5),
            datetime.date(2026, 2, 20),
        ))

        def open_picker(_initial, callback):
            callback(None, next(selected_dates), [])

        self.host._open_date_picker = mock.Mock(side_effect=open_picker)
        self.host._load_history_range = mock.Mock()

        HistoryMixin.open_custom_history_range(self.host, self.container)

        self.assertEqual(self.host._open_date_picker.call_count, 2)
        self.host._load_history_range.assert_called_once_with(
            self.container, "2026-01-05", "2026-02-20"
        )

    def test_before_ledger_point_in_time_is_explained(self):
        result = {
            "date": "2020-01-01",
            "basis": "before_ledger",
            "ledger_start": "2026-01-01",
        }

        HistoryMixin._render_balance_at(self.host, self.container, result)

        self.assertEqual(len(self.container.children), 1)
        self.assertIn("2020-01-01 için kayıt yok", self.container.children[0].text)


if __name__ == "__main__":
    unittest.main()
