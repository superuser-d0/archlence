"""Takvim mixin'inin pencere açmadan çalışan ince entegrasyon testleri.

tests/test_insights_mixin.py ile aynı desen: gerçek kivymd yerine yeterince
yetenekli sahte widget'lar (kwargs kabul eden, add_widget/clear_widgets/bind
destekleyen `_Widget`), modül ilk kez import edilirken sys.modules'a
patch'lenir.
"""
import datetime
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
    """test_insights_mixin.py'deki ile aynı ölçüde yetenekli sahte widget."""

    def __init__(self, *args, **kwargs):
        self.children = []
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_widget(self, widget):
        self.children.append(widget)

    def clear_widgets(self):
        self.children = []

    def bind(self, **kwargs):
        pass

    def setter(self, name):
        return lambda instance, value: None

    def open(self):
        pass


class _Clock:
    @staticmethod
    def schedule_once(callback, timeout=0):
        return callback(0)


_bind_card_tap_calls = []


def _fake_bind_card_tap(card, callback):
    _bind_card_tap_calls.append((card, callback))


_stubs = {
    "kivy": _module("kivy"),
    "kivy.clock": _module("kivy.clock", Clock=_Clock),
    "kivy.metrics": _module("kivy.metrics", dp=lambda v: v),
    "kivymd": _module("kivymd"),
    "kivymd.uix": _module("kivymd.uix"),
    "kivymd.uix.boxlayout": _module("kivymd.uix.boxlayout", MDBoxLayout=_Widget),
    "kivymd.uix.button": _module("kivymd.uix.button", MDFlatButton=_Widget),
    "kivymd.uix.card": _module("kivymd.uix.card", MDCard=_Widget),
    "kivymd.uix.dialog": _module("kivymd.uix.dialog", MDDialog=_Widget),
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget),
    "ui.theme": _module(
        "ui.theme",
        accent=lambda style, name: name,
        apply_card_theme=lambda card, *args, **kwargs: card,
        bind_card_tap=_fake_bind_card_tap,
        on_primary=lambda theme_cls: "on_primary",
        inactive_control_text=lambda style: "muted",
    ),
    "ui.i18n": _module("ui.i18n", tr=lambda text, language=None: text),
}
with mock.patch.dict(sys.modules, _stubs):
    import mixins.calendar_mixin as calendar_module
    CalendarMixin = calendar_module.CalendarMixin


class _ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


def _make_host():
    host = mock.Mock()
    host.theme_cls = mock.Mock(theme_style="Light", primary_color=(0, 0, 0, 1))
    return host


class CalendarMonthNavigationTest(unittest.TestCase):
    """Ay ileri/geri gezinme aritmetiği — yıl sınırları dahil."""

    def setUp(self):
        self.host = _make_host()
        self.host._render_calendar_month = mock.Mock()

    def test_next_month_within_same_year(self):
        self.host._calendar_year = 2026
        self.host._calendar_month = 3

        CalendarMixin._change_calendar_month(self.host, 1)

        self.assertEqual(self.host._calendar_year, 2026)
        self.assertEqual(self.host._calendar_month, 4)
        self.host._render_calendar_month.assert_called_once_with()

    def test_december_rolls_over_to_next_january(self):
        self.host._calendar_year = 2026
        self.host._calendar_month = 12

        CalendarMixin._change_calendar_month(self.host, 1)

        self.assertEqual(self.host._calendar_year, 2027)
        self.assertEqual(self.host._calendar_month, 1)

    def test_january_rolls_back_to_previous_december(self):
        self.host._calendar_year = 2026
        self.host._calendar_month = 1

        CalendarMixin._change_calendar_month(self.host, -1)

        self.assertEqual(self.host._calendar_year, 2025)
        self.assertEqual(self.host._calendar_month, 12)


class CalendarMonthRenderTest(unittest.TestCase):
    """Ay ızgarasının kurulması: satır sayısı, günlerin işaretlenmesi."""

    def setUp(self):
        self.host = _make_host()
        self.host._calendar_month_label = calendar_module.MDLabel()
        self.host._calendar_grid_container = calendar_module.MDBoxLayout()

    @mock.patch("services.calendar_service.get_month_transaction_days")
    def test_march_2026_has_five_weeks_and_marks_transaction_days(
            self, get_days):
        get_days.return_value = {5: 2, 17: 1}
        self.host._calendar_year = 2026
        self.host._calendar_month = 3
        self.host._calendar_selected_date = datetime.date(2026, 3, 5)

        CalendarMixin._render_calendar_month(self.host)

        get_days.assert_called_once_with(2026, 3)
        # calendar.monthcalendar(2026, 3) -> Mart 2026 tam olarak 5 hafta sürer.
        import calendar as _cal
        expected_weeks = len(_cal.monthcalendar(2026, 3))
        self.assertEqual(
            len(self.host._calendar_grid_container.children), expected_weeks)
        self.assertIn("Mart", self.host._calendar_month_label.text)
        self.assertIn("2026", self.host._calendar_month_label.text)

    @mock.patch("services.calendar_service.get_month_transaction_days")
    def test_query_failure_does_not_crash_render(self, get_days):
        get_days.side_effect = Exception("db patladı")
        self.host._calendar_year = 2026
        self.host._calendar_month = 3
        self.host._calendar_selected_date = datetime.date(2026, 3, 1)

        CalendarMixin._render_calendar_month(self.host)  # patlamamalı

        self.assertGreater(len(self.host._calendar_grid_container.children), 0)


class CalendarDaySelectionTest(unittest.TestCase):
    """Bir güne dokununca işlem listesinin yüklenmesi."""

    def setUp(self):
        self.host = _make_host()
        self.host._calendar_selected_date = datetime.date(2026, 3, 1)
        self.host._calendar_selected_label = calendar_module.MDLabel()
        self.host._calendar_tx_container = calendar_module.MDBoxLayout()
        self.host._render_calendar_month = mock.Mock()
        # self.host bir Mock() — getattr(mock, "_calendar_generation", 0)
        # varsayılanı hiç DÖNMEZ, Mock her eksik attribute'u kendiliğinden
        # üretir. Sayaç mantığının gerçek int ile çalışması için baştan set.
        self.host._calendar_generation = 0
        # AYNI GEREKÇE: _select_calendar_day içeride self._apply_calendar_day(...)
        # çağırıyor — self bir Mock() olduğundan bağlanmamış bırakılırsa bu,
        # gerçek metot yerine sessizce hiçbir şey yapmayan bir sahte Mock'a
        # gider (tests/test_insights_mixin.py'deki _empty_label ile aynı tuzak).
        self.host._apply_calendar_day = types.MethodType(
            CalendarMixin._apply_calendar_day, self.host
        )

    def _select(self, date_obj):
        with (
            mock.patch.object(calendar_module.Clock, "schedule_once",
                              side_effect=lambda cb, timeout=0: cb(0)),
            mock.patch.object(calendar_module.threading, "Thread", _ImmediateThread),
        ):
            CalendarMixin._select_calendar_day(self.host, date_obj)

    @mock.patch("services.calendar_service.get_day_transactions")
    def test_populated_day_renders_a_row_per_transaction(self, get_day):
        get_day.return_value = [
            {"type": "income", "category": "Maaş", "amount": 40000.0,
             "description": "maaş", "time": "09:00"},
            {"type": "expense", "category": "Market", "amount": 250.5,
             "description": "market", "time": "18:30"},
        ]

        self._select(datetime.date(2026, 3, 5))

        get_day.assert_called_once_with(datetime.date(2026, 3, 5))
        self.assertEqual(len(self.host._calendar_tx_container.children), 2)
        self.assertIn("2", self.host._calendar_selected_label.text)

    @mock.patch("services.calendar_service.get_day_transactions")
    def test_empty_day_shows_no_transactions_message(self, get_day):
        get_day.return_value = []

        self._select(datetime.date(2026, 3, 6))

        self.assertEqual(len(self.host._calendar_tx_container.children), 0)
        self.assertIn("işlem yok", self.host._calendar_selected_label.text)

    @mock.patch("services.calendar_service.get_day_transactions")
    def test_query_error_shows_honest_error_message_not_empty_state(
            self, get_day):
        get_day.side_effect = Exception("db patladı")

        self._select(datetime.date(2026, 3, 7))

        self.assertEqual(len(self.host._calendar_tx_container.children), 0)
        self.assertIn("okunamadı", self.host._calendar_selected_label.text)
        self.assertNotIn("işlem yok", self.host._calendar_selected_label.text)

    def test_selecting_a_day_in_the_same_month_refreshes_grid_for_highlight(
            self):
        """Seçim değişince ızgara yeniden çizilmeli ki seçili gün vurgusu
        (is_selected) güncellensin — aksi halde eski gün seçili görünür."""
        with mock.patch(
                "services.calendar_service.get_day_transactions",
                return_value=[]):
            self._select(datetime.date(2026, 3, 10))

        self.host._render_calendar_month.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
