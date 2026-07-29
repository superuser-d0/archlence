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
    "kivymd.uix.label": _module("kivymd.uix.label", MDLabel=_Widget, MDIcon=_Widget),
    "kivymd.uix.fitimage": _module("kivymd.uix.fitimage", FitImage=_Widget),
    "kivy.metrics": _module("kivy.metrics", dp=lambda v: v),
    "ui.theme": _module(
        # Gerçek ftheme.accent bir renk (RGBA) döndürür; burada bilerek
        # SEÇİLEN accent adının kendisini döndürüyoruz ki testler
        # _score_accent'in doğru bandı (green/amber/red) seçtiğini
        # doğrudan assert edebilsin — gerçek renk değerini değil.
        "ui.theme", accent=lambda style, name: name,
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
        # _score_accent(85) -> "green" (>=60); ui.theme stub'ı accent adını
        # olduğu gibi geri döndürüyor, bu yüzden doğrudan assert edilebiliyor.
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
        # DÜZELTME öncesi hata durumunda bar opacity=0 (görünmez) kalıyordu,
        # aynı "insufficient data" ile aynı görünüyordu; artık ayrı: bar
        # görünür (opacity=1) ama değeri 0 ve kırmızı.
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
        self.host.root.ids = types.SimpleNamespace(
            recurring_candidates_container=container,
        )
        self.host._active_subscriptions = []
        # self.host bir Mock() — self._empty_label(...) çağrısının gerçek
        # InsightsMixin._empty_label'a gitmesi için (yoksa Mock kendi sahte
        # attribute'unu üretir) diğer testlerdeki desenle aynı şekilde
        # gerçek metoda bağlanıyor.
        self.host._empty_label = types.MethodType(InsightsMixin._empty_label, self.host)

        InsightsMixin.render_recurring_candidates(self.host, [])

        self.assertEqual(len(container.children), 1)
        self.assertEqual(container.children[0].text, "Aktif aboneliğiniz bulunmuyor.")

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
