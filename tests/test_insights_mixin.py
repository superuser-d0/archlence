"""Insights UI eylemlerinin pencere açmadan çalışan ince entegrasyon testleri."""

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
    """Gerçek KivyMD widget'ının test için yeterli ölçüde sahtesi.

    render_* metodları `MDCard(...)`/`MDLabel(...)` gibi kwargs'lı kurucular,
    `container.add_widget(...)`/`clear_widgets()` ve `label.bind(size=
    label.setter("text_size"))` çağırıyor — pencere açmadan bunları
    çalıştırmak için üçünü de taklit ediyor. `bind()` hiçbir şey yapmıyor
    (testte gerçek bir property değişimi hiç tetiklenmiyor), `setter()` de
    yalnızca AttributeError'a düşmesin diye var.
    """

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


class _Clock:
    @staticmethod
    def schedule_once(callback, timeout=0):
        return callback(0)


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
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget, MDIcon=_Widget),
    "kivymd.uix.fitimage": _module("kivymd.uix.fitimage", FitImage=_Widget),
    "kivy.metrics": _module("kivy.metrics", dp=lambda v: v),
    "ui.theme": _module(


        "ui.theme", accent=lambda style, name: name,
        apply_card_theme=lambda card, *args, **kwargs: card,
    ),
    "ui.i18n": _module(
        "ui.i18n", tr=lambda text, language=None: text,
        trf=lambda template, language=None, **params: re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), template),
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

    def test_render_health_score_happy_path_uses_green_band_and_breakdown(self):
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

        InsightsMixin.render_health_score(
            self.host,
            {
                "score": 85.0,
                "insufficient_data": False,
                "breakdown": {
                    "savings_rate": 0.42,
                    "debt_ratio": 0.10,
                    "expense_volatility": 0.05,
                },
            },
        )

        self.assertEqual(score_value.text, "85")


        self.assertEqual(score_value.text_color, "green")
        self.assertEqual(score_bar.color, "green")
        self.assertEqual(score_bar.value, 85.0)
        self.assertEqual(score_bar.opacity, 1)
        self.assertIn("%42", breakdown.text)
        self.assertIn("%10", breakdown.text)
        self.assertIn("%5", breakdown.text)

    def test_render_health_score_low_band_uses_red_accent(self):
        score_value = mock.Mock()
        self.host.root.ids = types.SimpleNamespace(
            health_score_value=score_value,
            health_score_label=mock.Mock(),
            health_score_bar=mock.Mock(),
            health_breakdown_text=mock.Mock(),
        )
        self.host.theme_cls.theme_style = "Light"

        InsightsMixin.render_health_score(
            self.host,
            {"score": 15.0, "insufficient_data": False, "breakdown": {}},
        )

        self.assertEqual(score_value.text_color, "red")

    def test_render_health_error_shows_error_state_not_stale_loading(self):
        """Hesaplama/çizim hatasında kart sonsuza kadar 'Hesaplanıyor...'da
        kalmamalı — açıkça hata durumuna geçmeli (score_label.text kontrolü
        bunun 'insufficient data' ile karıştırılmadığını da doğruluyor)."""
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
        self.host.theme_cls.theme_style = "Dark"

        InsightsMixin.render_health_error(self.host)

        self.assertEqual(score_value.text, "--")
        self.assertEqual(score_value.text_color, "red")
        self.assertEqual(score_label.text, "Hesaplanamadı")
        self.assertNotEqual(score_label.text, "Yeterli veri yok")
        self.assertEqual(score_bar.value, 0)
        self.assertEqual(score_bar.color, "red")


        self.assertEqual(score_bar.opacity, 1)

    @mock.patch("services.insights_service.dismiss_recurring_candidate")
    def test_dismiss_recurring_candidate_action_persists_and_refreshes(
            self, dismiss_service):
        candidate = {"key": "dijital platformlar|netflix", "name": "Netflix"}

        with (
            mock.patch.object(insights_module.Clock, "schedule_once",
                              side_effect=lambda callback, timeout=0: callback(0)),
            mock.patch.object(insights_module.threading, "Thread", _ImmediateThread),
        ):
            InsightsMixin.dismiss_recurring_candidate(self.host, candidate)

        dismiss_service.assert_called_once_with("dijital platformlar|netflix")
        self.host.refresh_insights.assert_called_once_with()

    def test_render_recurring_candidates_empty_state_shows_message(self):
        container = insights_module.MDBoxLayout()
        recycler = _Widget()
        self.host.root.ids = types.SimpleNamespace(
            active_subscriptions_rv=recycler,
            recurring_candidates_container=container,
        )
        self.host._active_subscriptions = []


        self.host._empty_label = types.MethodType(InsightsMixin._empty_label, self.host)

        InsightsMixin.render_recurring_candidates(self.host, [])

        self.assertEqual(recycler.data, [])
        self.assertEqual(len(container.children), 1)
        self.assertEqual(container.children[0].text, "Aktif aboneliğiniz bulunmuyor.")

    def test_active_subscriptions_go_to_recycleview_as_data_not_widgets(self):
        """REGRESYON KORUMASI: abonelik kartları eskiden tek karede widget
        olarak kuruluyordu ve maliyet abonelik sayısıyla büyüyordu. Artık
        RecycleView'e VERİ verilmeli — hiçbir kart widget'ı kurulmamalı."""
        container = insights_module.MDBoxLayout()
        recycler = _Widget()
        self.host.root.ids = types.SimpleNamespace(
            active_subscriptions_rv=recycler,
            recurring_candidates_container=container,
        )
        payments = [
            {"name": "Netflix", "amount": 229.99, "frequency": "monthly",
             "next_due_date": "2026-09-15", "recurrence_day": 15},
            {"name": "Spotify", "amount": 59.99, "frequency": "monthly",
             "next_due_date": "2026-09-03", "recurrence_day": 3},
        ]
        self.host._active_subscriptions = payments
        self.host._subscription_row_data = types.MethodType(
            InsightsMixin._subscription_row_data, self.host)
        self.host._empty_label = types.MethodType(
            InsightsMixin._empty_label, self.host)

        InsightsMixin.render_recurring_candidates(self.host, [])

        self.assertEqual(len(recycler.data), 2)
        self.assertEqual(
            [row["name"] for row in recycler.data], ["Netflix", "Spotify"])

        self.assertIs(recycler.data[0]["payment"], payments[0])

        self.assertEqual(container.children, [])

    def test_icon_prefetch_refresh_does_not_wipe_active_incomes(self):
        """REGRESYON: ikon indirmesi başarılı olunca liste tazeleniyor ve
        `render_subscription_overview` gelen listeyi transaction_type'a göre
        YENİDEN bölüyor. Tazelemeye yalnızca abonelikler geçilirse (gelirler
        zaten ayıklanmış olduğu için) 'Aktif Gelirlerim' kartı sessizce
        boşalıyordu."""
        subs = [{"name": "Netflix", "amount": 229.99, "frequency": "monthly",
                 "next_due_date": "2026-09-15", "recurrence_day": 15}]
        incomes = [{"name": "Maaş", "amount": 50000.0, "frequency": "monthly",
                    "next_due_date": "2026-09-01", "recurrence_day": 1,
                    "transaction_type": "income"}]
        self.host._active_subscriptions = list(subs)
        self.host._active_incomes = list(incomes)
        self.host._recurring_candidates = []

        captured = {}

        def fake_overview(active_subscriptions, candidates):
            captured["subs"] = active_subscriptions

        self.host.render_subscription_overview = fake_overview

        class _Clock:
            @staticmethod
            def schedule_once(callback, _timeout=0):
                callback(0)

        with (
            mock.patch.object(
                insights_module, "threading",
                types.SimpleNamespace(Thread=_ImmediateThread)),
            mock.patch.object(insights_module, "Clock", _Clock),
            mock.patch(
                "services.brand_icon_service.fetch_and_cache_brand_icon",
                return_value=True),
        ):
            InsightsMixin._prefetch_candidate_brand_icons(self.host, {"Netflix"})

        names = [row["name"] for row in captured["subs"]]
        self.assertIn("Netflix", names)
        self.assertIn("Maaş", names, "gelirler tazelemede kaybolmamalı")

    def test_render_anomalies_empty_state_shows_message(self):
        container = insights_module.MDBoxLayout()
        self.host.root.ids = types.SimpleNamespace(anomalies_container=container)
        self.host._empty_label = types.MethodType(InsightsMixin._empty_label, self.host)

        InsightsMixin.render_anomalies(self.host, [])

        self.assertEqual(len(container.children), 1)
        self.assertEqual(
            container.children[0].text, "Olağandışı harcama tespit edilmedi.")


if __name__ == "__main__":
    unittest.main()
