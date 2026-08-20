"""What-if sandbox arayüzü; hesaplama services.projection_service içindedir."""

from kivy.metrics import dp
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.segmentedcontrol import (
    MDSegmentedControl, MDSegmentedControlItem,
)
from kivymd.uix.textfield import MDTextField

from services.projection_service import simulate_scenario
from ui.charts import ScenarioComparisonChart
from ui.i18n import tr as _t, trf as _tf
import ui.theme as ftheme


def _fmt(value):
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _number(text, default=0.0):
    raw = str(text or "").strip().replace(",", ".")
    return float(raw) if raw else float(default)


class ScenarioMixin:
    """Taban metrikleri kullanıcı deltalarıyla karşılaştıran diyalog."""

    _scenario_days = 30
    _scenario_dialog = None

    def open_scenario_sandbox(self):
        base = getattr(self, "_scenario_base_metrics", None)
        if not base:
            toast(_t("Projeksiyon verileri henüz hazır değil."))
            return

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(8), dp(4), dp(8), dp(4)],
            size_hint_y=None,
            height=dp(455),
        )
        self.scenario_income_input = MDTextField(
            text="0",
            hint_text=_t("Gelir değişimi (%)"),
            helper_text=_t("Artış için pozitif, azalış için negatif değer"),
            helper_text_mode="on_focus",
            input_filter="float",
        )
        self.scenario_expense_input = MDTextField(
            text="0",
            hint_text=_t("Gider değişimi (%)"),
            helper_text=_t("Azalış için negatif değer"),
            helper_text_mode="on_focus",
            input_filter="float",
        )
        self.scenario_adjustment_input = MDTextField(
            text="0",
            hint_text=_t("Tek seferlik gelir/gider (₺)"),
            helper_text=_t("Gelir pozitif, gider negatif girilir"),
            helper_text_mode="on_focus",
            input_filter="float",
        )

        self.scenario_horizon = MDSegmentedControl(
            size_hint_y=None, height=dp(42),
        )
        for days in (30, 90, 365):
            self.scenario_horizon.add_widget(
                MDSegmentedControlItem(text=_tf("{days} Gün", days=days))
            )
        self._scenario_days = 30
        self.scenario_horizon.bind(on_active=self._on_scenario_horizon)

        self.scenario_chart = ScenarioComparisonChart(
            size_hint_y=None, height=dp(135),
        )
        self.scenario_summary = MDLabel(
            text=_t("Senaryoyu görmek için HESAPLA'ya basın."),
            font_style="Caption",
            theme_text_color="Secondary",
            halign="center",
            size_hint_y=None,
            height=dp(50),
        )
        self.scenario_summary.bind(
            size=self.scenario_summary.setter("text_size")
        )

        content.add_widget(self.scenario_income_input)
        content.add_widget(self.scenario_expense_input)
        content.add_widget(self.scenario_adjustment_input)
        content.add_widget(self.scenario_horizon)
        content.add_widget(self.scenario_chart)
        content.add_widget(self.scenario_summary)

        self._scenario_dialog = MDDialog(
            title=_t("What-If Sandbox"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("KAPAT"),
                    theme_text_color="Custom",
                    text_color=ftheme.accent(
                        self.theme_cls.theme_style, "muted"
                    ),
                    on_release=lambda _button: self._scenario_dialog.dismiss(),
                ),
                MDRaisedButton(
                    text=_t("HESAPLA"),
                    md_bg_color=self.theme_cls.primary_color,
                    elevation=0,
                    on_release=self.calculate_scenario,
                ),
            ],
        )
        self._scenario_dialog.open()

    def _on_scenario_horizon(self, _control, item):
        try:
            self._scenario_days = int(str(item.text).split()[0])
        except (TypeError, ValueError):
            self._scenario_days = 30

    def calculate_scenario(self, *args):
        try:
            base = self._scenario_base_metrics
            result = simulate_scenario(
                **base,
                income_delta_pct=_number(self.scenario_income_input.text),
                expense_delta_pct=_number(self.scenario_expense_input.text),
                days=self._scenario_days,
                one_time_adjustment=_number(
                    self.scenario_adjustment_input.text
                ),
            )
        except (TypeError, ValueError):
            from utils.logging_config import get_logger
            get_logger().exception("What-if girdileri geçersiz")
            toast(_t("Lütfen geçerli sayılar girin!"))
            return
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("What-if senaryosu hesaplanamadı")
            toast(_t("Senaryo hesaplanamadı."))
            return

        self._apply_scenario_result(result)

    def _apply_scenario_result(self, result):
        """Servis sonucunu grafik ve özet metnine uygular."""
        self.scenario_chart.set_series(
            result["base_series"], result["scenario_series"]
        )
        difference = result["difference"]
        sign = "+" if difference >= 0 else ""
        warning = (
            _t("\nDikkat: Bu senaryoda varlık negatife düşüyor.")
            if result["goes_negative"] else ""
        )
        self.scenario_summary.text = (
            f"{result['days']} {_t('gün sonra')}: "
            f"{_fmt(result['scenario_final'])}\n"
            f"{_t('Taban senaryoya göre')}: {sign}{_fmt(difference)}"
            f"{warning}"
        )
