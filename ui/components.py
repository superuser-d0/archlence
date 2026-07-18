from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import TwoLineAvatarIconListItem, IRightBodyTouch
from kivy.properties import StringProperty, NumericProperty, ListProperty, ColorProperty, BooleanProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.label import MDLabel

class CategorySettingItem(MDBoxLayout):
    cat_name = StringProperty("")
    cat_type = StringProperty("")
    cat_importance = StringProperty("")


class RightButtonsContainer(IRightBodyTouch, MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Sabit genişlik şart: adaptive_width açık kalırsa KivyMD, liste öğesi
        # ilk çizildiğinde container'ı 0 genişliğe daraltıp butonları gizliyor.
        self.adaptive_width = False
        self.size_hint_x = None
        self.width = dp(120)
        self.spacing = dp(8)
        # Sağdan 24dp boşluk: silme (çöp kutusu) butonu ekran kenarına yapışmasın
        # ve liste öğesinin kendi dokunma alanıyla çakışmasın diye.
        self.padding = [0, 0, dp(24), 0]


class BudgetListItem(TwoLineAvatarIconListItem):
    item_id = NumericProperty(0)


class LegendItem(MDBoxLayout):
    text = StringProperty("")
    color = ColorProperty((1, 1, 1, 1))
    is_selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_selected = not self.is_selected
            self.opacity = 1.0 if self.is_selected else 0.5

            app = MDApp.get_running_app()
            if app and app.root:
                selected_targets = []
                # Find the owning LegendWidget — could be inside chart_master_box or via ids
                legend_widget = None
                if 'chart_master_box' in app.root.ids:
                    cmb = app.root.ids.chart_master_box
                    if hasattr(cmb, 'legend_widget'):
                        legend_widget = cmb.legend_widget
                if legend_widget is None and 'pie_legend' in app.root.ids:
                    legend_widget = app.root.ids.pie_legend

                if legend_widget:
                    for column in legend_widget.children:
                        for child in column.children:
                            if isinstance(child, LegendItem) and child.is_selected:
                                selected_targets.append(child.text)
                    # If nothing selected, restore full opacity
                    if not selected_targets:
                        for column in legend_widget.children:
                            for child in column.children:
                                if isinstance(child, LegendItem):
                                    child.opacity = 1.0

                if 'chart_master_box' in app.root.ids:
                    pie = getattr(app.root.ids.chart_master_box, 'pie_widget', None)
                    if pie:
                        pie.highlight_slice(selected_targets)
                elif 'pie_chart' in app.root.ids:
                    app.root.ids.pie_chart.highlight_slice(selected_targets)
            return True
        return super().on_touch_down(touch)


class LegendWidget(MDBoxLayout):
    """Static 4-category legend. Built once in __init__. Call update_percentages() to refresh text."""

    # Fixed palette — must match PieChart.category_colors
    CATEGORY_COLORS = {
        'Ana Gelir':    '#00C853',
        'Ek Gelir':     '#2979FF',
        'Temel Gider':  '#FF5252',
        'Ekstra Gider': '#FFD600',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.spacing = dp(20)
        self.padding = [dp(8), dp(4), dp(8), dp(4)]
        self.labels = {}   # cat -> MDLabel reference for text updates
        self._built = False
        # Build on next frame so the widget tree is stable
        Clock.schedule_once(self._build, 0)

    def _build(self, *args):
        if self._built:
            return
        self._built = True
        from kivy.utils import get_color_from_hex

        left_box = MDBoxLayout(orientation='vertical', size_hint_x=0.5, spacing=dp(4))
        right_box = MDBoxLayout(orientation='vertical', size_hint_x=0.5, spacing=dp(4))

        for cat, hex_color in self.CATEGORY_COLORS.items():
            row = LegendItem(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(26),
                spacing=dp(12),
            )
            row.text = cat

            from kivymd.uix.label import MDIcon
            dot = MDIcon(
                icon='circle',
                theme_text_color='Custom',
                text_color=get_color_from_hex(hex_color),
                font_size='12sp',
                size_hint=(None, None),
                size=(dp(12), dp(12)),
                pos_hint={'center_y': 0.5}
            )
            lbl = MDLabel(
                text=cat,
                theme_text_color='Primary',
                font_style='Caption',
                pos_hint={'center_y': 0.5}
            )
            self.labels[cat] = lbl
            row.add_widget(dot)
            row.add_widget(lbl)

            if cat in ('Ana Gelir', 'Ek Gelir'):
                left_box.add_widget(row)
            else:
                right_box.add_widget(row)

        self.add_widget(left_box)
        self.add_widget(right_box)

    def update_percentages(self, data_dict):
        """data_dict: {cat: amount, ...}. Updates each label to 'Cat  X.X%'."""
        total = sum(data_dict.values())
        for cat, lbl in self.labels.items():
            val = data_dict.get(cat, 0)
            pct = (val / total * 100) if total > 0 else 0.0
            lbl.text = f"{cat}  {pct:.1f}%"

    # Legacy compatibility shim
    def update_legend(self, new_data):
        self.update_percentages(new_data)

