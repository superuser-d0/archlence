"""Insights UI eylemlerinin pencere açmadan çalışan ince entegrasyon testleri."""

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
    pass


class _Clock:
    @staticmethod
    def schedule_once(callback, timeout=0):
        return callback(0)


# Mixin'in iş mantığını test ederken KivyMD widget importlarının SDL penceresi
# istemesine gerek yok. Yalnız modül yüklenirken kullanılan adları sağla;
# patch bağlamı bitince sys.modules eski hâline döner.
_stubs = {
    "kivy": _module("kivy"),
    "kivy.clock": _module("kivy.clock", Clock=_Clock),
    "kivymd": _module("kivymd"),
    "kivymd.toast": _module("kivymd.toast", toast=lambda *args: None),
    "kivymd.uix": _module("kivymd.uix"),
    "kivymd.uix.boxlayout": _module("kivymd.uix.boxlayout", MDBoxLayout=_Widget),
    "kivymd.uix.button": _module(
        "kivymd.uix.button", MDFlatButton=_Widget, MDIconButton=_Widget,
    ),
    "kivymd.uix.card": _module("kivymd.uix.card", MDCard=_Widget),
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget),
    "ui.theme": _module(
        "ui.theme", accent=lambda *args: [0, 0, 0, 1],
        apply_card_theme=lambda card, *args, **kwargs: card,
    ),
    "ui.i18n": _module(
        "ui.i18n", tr=lambda text, language=None: text,
        get_language=lambda: "tr",
    ),
}
with mock.patch.dict(sys.modules, _stubs):
    import mixins.insights_mixin as insights_module
    InsightsMixin = insights_module.InsightsMixin


class _ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


class InsightsMixinActionTest(unittest.TestCase):

    def setUp(self):
        self.host = mock.Mock()
        self.host.refresh_insights = mock.Mock()

    @mock.patch("services.insights_service.dismiss_anomaly")
    def test_dismiss_anomaly_action_persists_and_refreshes(self, dismiss_service):
        with (
            mock.patch.object(insights_module.Clock, "schedule_once",
                              side_effect=lambda callback, timeout=0: callback(0)),
            mock.patch.object(insights_module.threading, "Thread", _ImmediateThread),
        ):
            InsightsMixin.dismiss_anomaly(self.host, {"id": 42})

        dismiss_service.assert_called_once_with(42)
        self.host.refresh_insights.assert_called_once_with()

    @mock.patch("database.db.insert_recurring_payment")
    @mock.patch("database.db.has_active_recurring_payment", return_value=False)
    def test_track_weekly_candidate_uses_existing_db_flow(
            self, has_active, insert_payment):
        candidate = {
            "name": "Haftalik Kahve",
            "average_amount": 100.0,
            "category": "Dışarıda Yemek",
            "frequency": "weekly",
            "next_due_date": "2026-07-30",
        }

        with (
            mock.patch.object(insights_module.Clock, "schedule_once",
                              side_effect=lambda callback, timeout=0: callback(0)),
            mock.patch.object(insights_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(insights_module, "toast"),
        ):
            InsightsMixin.track_recurring_candidate(self.host, candidate)

        has_active.assert_called_once_with("Haftalik Kahve")
        insert_payment.assert_called_once_with(
            name="Haftalik Kahve",
            amount=100.0,
            category="Dışarıda Yemek",
            frequency="weekly",
            next_due_date="2026-07-30",
            auto_deduct=0,
        )
        self.host.refresh_insights.assert_called_once_with()

    def test_render_health_score_shows_insufficient_data_state(self):
        score_value = mock.Mock()
        score_label = mock.Mock()
        score_bar = mock.Mock()
        breakdown = mock.Mock()
        self.host.root.ids = types.SimpleNamespace(
            health_score_value=score_value,
            health_score_label=score_label,
            health_score_bar=score_bar,
            health_breakdown_text=breakdown,
        )
        self.host.theme_cls.theme_style = "Light"
        self.host.render_health_insufficient_data = types.MethodType(
            InsightsMixin.render_health_insufficient_data, self.host
        )

        InsightsMixin.render_health_score(
            self.host,
            {
                "score": None,
                "breakdown": {},
                "insufficient_data": True,
                "computed_at": "2026-07-23 12:00:00",
            },
        )

        self.assertEqual(score_value.text, "--")
        self.assertEqual(score_label.text, "Yeterli veri yok")
        self.assertEqual(
            breakdown.text,
            "Skor hesaplamak için henüz yeterli veri yok. "
            "Birkaç işlem ekleyince burada görünecek.",
        )
        self.assertEqual(score_bar.value, 0)
        self.assertEqual(score_bar.opacity, 0)


if __name__ == "__main__":
    unittest.main()
