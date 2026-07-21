from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import (
    TwoLineAvatarIconListItem, TwoLineIconListItem, IRightBodyTouch,
    IconLeftWidget, ImageLeftWidget,
)
from kivy.properties import StringProperty, NumericProperty, ListProperty, ColorProperty, BooleanProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivymd.app import MDApp
from kivymd.uix.label import MDLabel

class RecycleListRow(RecycleDataViewBehavior, TwoLineIconListItem):
    """Varlık Geçmişi ve Son İşlemler listelerinin RecycleView satırı.

    TwoLineIconListItem'ı birebir kullanır (aynı font/renk/divider davranışı);
    tek fark, sol ikon slotunun (_left_container) her satır yeniden
    kullanıldığında verideki icon_source/icon_name'e göre imperatif olarak
    yeniden kurulmasıdır — RecycleView satırları geri dönüştürdüğü için
    IconLeftWidget/ImageLeftWidget kv'de statik olarak tanımlanamaz.
    """
    icon_source = StringProperty("")
    icon_name = StringProperty("")
    icon_color = ListProperty([0.08, 0.72, 0.42, 1])

    def refresh_view_attrs(self, rv, index, data):
        super().refresh_view_attrs(rv, index, data)
        self._sync_left_widget()

    def _sync_left_widget(self):
        self.ids._left_container.clear_widgets()
        self._touchable_widgets = []
        if self.icon_source:
            self.add_widget(ImageLeftWidget(
                source=self.icon_source,
                radius=[dp(12)] * 4,
            ))
        else:
            self.add_widget(IconLeftWidget(
                icon=self.icon_name or "help-circle-outline",
                theme_text_color="Custom",
                text_color=self.icon_color,
            ))


class CategorySettingItem(MDBoxLayout):
    """Kategori ayarları listesindeki her bir öğeyi (kategori adı, türü, önemi) temsil eden bileşen."""
    cat_name = StringProperty("")
    cat_type = StringProperty("")
    cat_importance = StringProperty("")


class RightButtonsContainer(IRightBodyTouch, MDBoxLayout):
    """Liste öğelerinin sağ tarafında hizalanan buton grubunu (düzenle/sil) tutan taşıyıcı bileşen."""
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
    """Bütçe planlayıcı listesindeki her bir gelir/gider kalemini temsil eden bileşen."""
    item_id = NumericProperty(0)


class LegendItem(MDBoxLayout):
    """Grafik lejantında yer alan ve tıklandığında ilgili dilimi vurgulayan (highlight) tekil öğe."""
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
    """Statik 4 kategorili lejant bileşeni. Başlangıçta oluşturulur, 'update_percentages()' ile güncellenir."""

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


from kivy.lang import Builder
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.card import MDCard

Builder.load_string('''
<PremiumCreditCardWidget>:
    size_hint: None, None
    width: "300dp"
    adaptive_height: True
    orientation: "vertical"
    padding: "12dp"
    spacing: "12dp"
    elevation: 1
    radius: [dp(20)]
    style: "outlined"
    md_bg_color: app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else (1, 1, 1, 1)

    # Üst Kısım: Siyah Grafik Kart
    MDFloatLayout:
        size_hint_y: None
        height: "170dp"
        
        canvas.before:
            Color:
                rgba: 0.1, 0.11, 0.13, 1
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [dp(16)]
                
        MDLabel:
            text: "Finora"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            font_style: "H6"
            bold: True
            pos_hint: {"x": 0.08, "top": 0.90}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDIcon:
            icon: "contactless-payment"
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_size: "24sp"
            pos_hint: {"right": 0.92, "top": 0.90}
            size_hint: None, None
            size: self.texture_size
            
        MDLabel:
            text: root.masked_number
            theme_text_color: "Custom"
            text_color: 0.7, 0.7, 0.7, 1
            font_style: "Subtitle2"
            pos_hint: {"x": 0.08, "center_y": 0.45}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDLabel:
            text: root.card_name.upper()
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_style: "Caption"
            pos_hint: {"x": 0.08, "y": 0.15}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True

        # Sabit en-boy oranı ile Visa/Mastercard Logosu
        Image:
            source: root.network_logo if root.network_logo else "assets/blank.png"
            opacity: 1 if root.network_logo else 0
            keep_ratio: True
            allow_stretch: True
            size_hint: None, None
            size: "40dp", "24dp"
            pos_hint: {"right": 0.92, "y": 0.12}

    # Orta Kısım: Başlık ve Rozet
    MDBoxLayout:
        size_hint_y: None
        height: "30dp"
        orientation: "horizontal"
        MDLabel:
            text: root.card_name
            font_style: "Subtitle1"
            bold: True
        MDCard:
            size_hint: None, None
            size: "80dp", "24dp"
            md_bg_color: (0.9, 0.9, 1, 1) if app.theme_cls.theme_style == "Light" else (0.2, 0.2, 0.3, 1)
            radius: [dp(8)]
            elevation: 0
            MDLabel:
                text: "Kredi Kartı"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: (0.3, 0.3, 0.8, 1) if app.theme_cls.theme_style == "Light" else (0.6, 0.6, 1, 1)
                halign: "center"
                valign: "center"

    # Limit / Borç Bilgileri
    MDBoxLayout:
        size_hint_y: None
        height: "40dp"
        orientation: "horizontal"
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: "Kullanılabilir Limit"
                font_style: "Caption"
                theme_text_color: "Secondary"
            MDLabel:
                text: root.available_limit
                font_style: "Subtitle1"
                bold: True
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: "Güncel Borç"
                font_style: "Caption"
                theme_text_color: "Secondary"
                halign: "right"
            MDLabel:
                text: root.current_debt
                font_style: "Subtitle1"
                bold: True
                theme_text_color: "Error"
                halign: "right"

    # Progress bar (mock)
    MDProgressBar:
        value: 40
        color: app.theme_cls.primary_color
        size_hint_y: None
        height: "4dp"

    Widget:
        size_hint_y: None
        height: "8dp"

    MDLabel:
        text: "Kart Kullanım Özeti"
        font_style: "Overline"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: "16dp"

    MDBoxLayout:
        size_hint_y: None
        height: "84dp"
        orientation: "vertical"
        spacing: "4dp"

        MDBoxLayout:
            size_hint_y: None
            height: "40dp"
            orientation: "horizontal"
            spacing: "8dp"
            padding: 0, 0, "14dp", 0
            MDIcon:
                icon: "web"
                size_hint: None, None
                size: "18dp", "18dp"
                font_size: "15sp"
                pos_hint: {"center_y": 0.5}
                theme_text_color: "Secondary"
            MDLabel:
                text: "İnternet Alışverişi"
                font_style: "Caption"
                size_hint_x: 1
                halign: "left"
                valign: "center"
                pos_hint: {"center_y": 0.5}
            MDSwitch:
                active: True
                widget_style: "ios"
                size_hint: None, None
                size: "40dp", "24dp"
                pos_hint: {"center_y": 0.5}

        MDBoxLayout:
            size_hint_y: None
            height: "40dp"
            orientation: "horizontal"
            spacing: "8dp"
            padding: 0, 0, "14dp", 0
            MDIcon:
                icon: "snowflake"
                size_hint: None, None
                size: "18dp", "18dp"
                font_size: "15sp"
                pos_hint: {"center_y": 0.5}
                theme_text_color: "Secondary"
            MDLabel:
                text: "Kartı Dondur"
                font_style: "Caption"
                size_hint_x: 1
                halign: "left"
                valign: "center"
                pos_hint: {"center_y": 0.5}
            MDSwitch:
                active: False
                widget_style: "ios"
                size_hint: None, None
                size: "40dp", "24dp"
                pos_hint: {"center_y": 0.5}

    MDSeparator:
        size_hint_y: None
        height: "1dp"

    MDLabel:
        text: "Son Hareketler"
        font_style: "Overline"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: "16dp"

    # AccountMixin._fill_card_recent dolduruyor (tarih · açıklama · tutar).
    MDBoxLayout:
        id: recent_container
        orientation: "vertical"
        adaptive_height: True
        spacing: "2dp"

    Widget:
        size_hint_y: 1

    # Butonlar
    MDBoxLayout:
        size_hint_y: None
        height: "36dp"
        spacing: "8dp"
        orientation: "horizontal"
        MDFlatButton:
            text: "Ekstre"
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
        MDFlatButton:
            text: "Borç Öde"
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
<PremiumDebitCardWidget>:
    size_hint: None, None
    width: "300dp"
    adaptive_height: True
    orientation: "vertical"
    padding: "12dp"
    spacing: "12dp"
    elevation: 1
    radius: [dp(20)]
    style: "outlined"
    md_bg_color: app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else (1, 1, 1, 1)

    MDFloatLayout:
        size_hint_y: None
        height: "170dp"
        
        canvas.before:
            Color:
                rgba: 0.1, 0.11, 0.13, 1
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [dp(16)]
                
        MDLabel:
            text: "Finora"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            font_style: "H6"
            bold: True
            pos_hint: {"x": 0.08, "top": 0.90}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDIcon:
            icon: "contactless-payment"
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_size: "24sp"
            pos_hint: {"right": 0.92, "top": 0.90}
            size_hint: None, None
            size: self.texture_size
            
        MDLabel:
            text: root.masked_number
            theme_text_color: "Custom"
            text_color: 0.7, 0.7, 0.7, 1
            font_style: "Subtitle2"
            pos_hint: {"x": 0.08, "center_y": 0.45}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDLabel:
            text: "BANKA KARTI"
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_style: "Caption"
            pos_hint: {"x": 0.08, "y": 0.15}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True

        Image:
            source: root.network_logo if root.network_logo else "assets/blank.png"
            opacity: 1 if root.network_logo else 0
            keep_ratio: True
            allow_stretch: True
            size_hint: None, None
            size: "40dp", "24dp"
            pos_hint: {"right": 0.92, "y": 0.12}

    MDBoxLayout:
        size_hint_y: None
        height: "30dp"
        orientation: "horizontal"
        MDLabel:
            text: root.card_name
            font_style: "Subtitle1"
            bold: True
        MDCard:
            size_hint: None, None
            size: "80dp", "24dp"
            md_bg_color: (0.9, 0.9, 1, 1) if app.theme_cls.theme_style == "Light" else (0.2, 0.2, 0.3, 1)
            radius: [dp(8)]
            elevation: 0
            MDLabel:
                text: "Banka Kartı"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: (0.3, 0.3, 0.8, 1) if app.theme_cls.theme_style == "Light" else (0.6, 0.6, 1, 1)
                halign: "center"
                valign: "center"

    MDBoxLayout:
        size_hint_y: None
        height: "40dp"
        orientation: "vertical"
        MDLabel:
            text: "Güncel Bakiye"
            font_style: "Caption"
            theme_text_color: "Secondary"
        MDLabel:
            text: root.balance
            font_style: "Subtitle1"
            bold: True

    Widget:
        size_hint_y: None
        height: "8dp"

    MDLabel:
        text: "Kart Kullanım Özeti"
        font_style: "Overline"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: "16dp"

    MDBoxLayout:
        size_hint_y: None
        height: "84dp"
        orientation: "vertical"
        spacing: "4dp"

        MDBoxLayout:
            size_hint_y: None
            height: "40dp"
            orientation: "horizontal"
            spacing: "8dp"
            padding: 0, 0, "14dp", 0
            MDIcon:
                icon: "web"
                size_hint: None, None
                size: "18dp", "18dp"
                font_size: "15sp"
                pos_hint: {"center_y": 0.5}
                theme_text_color: "Secondary"
            MDLabel:
                text: "İnternet Alışverişi"
                font_style: "Caption"
                size_hint_x: 1
                halign: "left"
                valign: "center"
                pos_hint: {"center_y": 0.5}
            MDSwitch:
                active: True
                widget_style: "ios"
                size_hint: None, None
                size: "40dp", "24dp"
                pos_hint: {"center_y": 0.5}

        MDBoxLayout:
            size_hint_y: None
            height: "40dp"
            orientation: "horizontal"
            spacing: "8dp"
            padding: 0, 0, "14dp", 0
            MDIcon:
                icon: "snowflake"
                size_hint: None, None
                size: "18dp", "18dp"
                font_size: "15sp"
                pos_hint: {"center_y": 0.5}
                theme_text_color: "Secondary"
            MDLabel:
                text: "Kartı Dondur"
                font_style: "Caption"
                size_hint_x: 1
                halign: "left"
                valign: "center"
                pos_hint: {"center_y": 0.5}
            MDSwitch:
                active: False
                widget_style: "ios"
                size_hint: None, None
                size: "40dp", "24dp"
                pos_hint: {"center_y": 0.5}

    MDSeparator:
        size_hint_y: None
        height: "1dp"

    MDLabel:
        text: "Son Hareketler"
        font_style: "Overline"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: "16dp"

    # AccountMixin._fill_card_recent dolduruyor (tarih · açıklama · tutar).
    MDBoxLayout:
        id: recent_container
        orientation: "vertical"
        adaptive_height: True
        spacing: "2dp"

    Widget:
        size_hint_y: 1

<BentoAccountWidget>:
    size_hint_y: None
    height: "100dp"
    padding: "16dp"
    spacing: "8dp"
    orientation: "vertical"
    style: "outlined"
    radius: [dp(20)]
    md_bg_color: app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else (0.96, 0.97, 1.0, 1.0)
    line_color: (0.8, 0.85, 0.95, 1) if app.theme_cls.theme_style == "Light" else (0.3, 0.3, 0.4, 1)

    MDBoxLayout:
        orientation: "horizontal"
        MDLabel:
            text: root.account_name
            font_style: "Subtitle1"
            bold: True
        MDLabel:
            text: root.account_type_label
            font_style: "Caption"
            theme_text_color: "Secondary"
            halign: "right"
            
    MDLabel:
        text: "Bakiye"
        font_style: "Caption"
        theme_text_color: "Secondary"
        
    MDLabel:
        text: root.balance
        font_style: "H6"
        bold: True
        theme_text_color: "Primary"
''')

class PremiumCreditCardWidget(MDCard):
    card_name = StringProperty("")
    masked_number = StringProperty("**** **** **** 0000")
    network_logo = StringProperty("")
    available_limit = StringProperty("₺0,00")
    current_debt = StringProperty("₺0,00")

class PremiumDebitCardWidget(MDCard):
    card_name = StringProperty("")
    masked_number = StringProperty("**** **** **** 0000")
    network_logo = StringProperty("")
    balance = StringProperty("₺0,00")

class BentoAccountWidget(MDCard):
    account_name = StringProperty("")
    account_type_label = StringProperty("")
    balance = StringProperty("₺0,00")

