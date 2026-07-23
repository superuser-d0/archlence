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
import unicodedata
from ui.i18n import tr as _t


def is_read_only_asset_account(account):
    """Ana aktif-varlık/vadesiz-varlık hesabını tek noktadan tanır.

    Gelecekte servis açık bir `is_read_only_asset` alanı döndürürse ad
    karşılaştırmasına gerek kalmadan çalışır; mevcut veriler için Türkçe adlar
    aksan/büyük-küçük harf duyarsız normalize edilir.
    """
    if bool(account.get("is_read_only_asset", False)):
        return True
    if str(account.get("account_type", "")).strip().casefold() in {
        "asset", "active_asset", "read_only_asset",
    }:
        return True
    raw_name = str(account.get("name", "")).strip().casefold()
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", raw_name)
        if not unicodedata.combining(char)
    ).replace("ı", "i")
    normalized = " ".join(normalized.split())
    return normalized in {
        "aktif varliklarim",
        "aktif varlik",
        "vadesiz varlik",
        "asset",
    }

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
            row.text = _t(cat)

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
                text=_t(cat),
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
            lbl.text = f"{_t(cat)}  {pct:.1f}%"

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
    elevation: 0 if app.theme_cls.theme_style == "Dark" else 1
    radius: [dp(20)]
    style: "outlined"
    md_bg_color: ftheme.card_bg(app.theme_cls.theme_style)
    line_color: ftheme.card_line(app.theme_cls.theme_style)

    # Üst Kısım: Siyah Grafik Kart
    MDFloatLayout:
        size_hint_y: None
        height: "170dp"
        
        canvas.before:
            Color:
                rgba: ftheme.bank_card_bg(app.theme_cls.theme_style)
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [dp(16)]
                
        MDLabel:
            text: "Finora"
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style)
            font_style: "H6"
            bold: True
            pos_hint: {"x": 0.08, "top": 0.90}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDIcon:
            icon: "contactless-payment"
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
            font_size: "24sp"
            pos_hint: {"right": 0.92, "top": 0.90}
            size_hint: None, None
            size: self.texture_size
            
        MDLabel:
            text: root.masked_number
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
            font_style: "Subtitle2"
            pos_hint: {"x": 0.08, "center_y": 0.45}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDLabel:
            text: root.card_name.upper()
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
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
                text: app.tr("Kredi Kartı", app.language)
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: (0.3, 0.3, 0.8, 1) if app.theme_cls.theme_style == "Light" else (0.6, 0.6, 1, 1)
                halign: "center"
                valign: "center"
        MDIconButton:
            icon: "dots-vertical"
            size_hint: None, None
            size: "36dp", "36dp"
            pos_hint: {"center_y": 0.5}
            theme_text_color: "Secondary"
            on_release: app.open_card_settings(self, root.account_id)

    # Limit / Borç Bilgileri
    MDBoxLayout:
        size_hint_y: None
        height: "40dp"
        orientation: "horizontal"
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: app.tr("Kullanılabilir Limit", app.language)
                font_style: "Caption"
                theme_text_color: "Secondary"
            MDLabel:
                text: root.available_limit
                font_style: "Subtitle1"
                bold: True
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: app.tr("Güncel Borç", app.language)
                font_style: "Caption"
                theme_text_color: "Secondary"
                halign: "right"
            MDLabel:
                text: root.current_debt
                font_style: "Subtitle1"
                bold: True
                theme_text_color: "Error"
                halign: "right"

    # Progress bar bound to actual debt ratio
    MDProgressBar:
        value: root.debt_ratio
        color: app.theme_cls.primary_color
        size_hint_y: None
        height: "4dp"

    Widget:
        size_hint_y: None
        height: "8dp"

    MDLabel:
        text: app.tr("Kart Kullanım Özeti", app.language)
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
                text: app.tr("İnternet Alışverişi", app.language)
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
                text: app.tr("Kartı Dondur", app.language)
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
        text: app.tr("Son Hareketler", app.language)
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
            text: app.tr("Ekstre", app.language)
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
            on_release: app.open_card_statement(root.account_id)
        MDFlatButton:
            text: app.tr("Borç Öde", app.language)
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
            on_release: app.open_pay_debt_dialog(root.account_id)
<PremiumDebitCardWidget>:
    size_hint: None, None
    width: "300dp"
    adaptive_height: True
    orientation: "vertical"
    padding: "12dp"
    spacing: "12dp"
    elevation: 0 if app.theme_cls.theme_style == "Dark" else 1
    radius: [dp(20)]
    style: "outlined"
    md_bg_color: ftheme.card_bg(app.theme_cls.theme_style)
    line_color: ftheme.card_line(app.theme_cls.theme_style)

    MDFloatLayout:
        size_hint_y: None
        height: "170dp"
        
        canvas.before:
            Color:
                rgba: ftheme.bank_card_bg(app.theme_cls.theme_style)
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [dp(16)]
                
        MDLabel:
            text: "Finora"
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style)
            font_style: "H6"
            bold: True
            pos_hint: {"x": 0.08, "top": 0.90}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDIcon:
            icon: "contactless-payment"
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
            font_size: "24sp"
            pos_hint: {"right": 0.92, "top": 0.90}
            size_hint: None, None
            size: self.texture_size
            
        MDLabel:
            text: root.masked_number
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
            font_style: "Subtitle2"
            pos_hint: {"x": 0.08, "center_y": 0.45}
            size_hint_x: 0.84
            halign: "left"
            adaptive_height: True
            
        MDLabel:
            text: app.tr("BANKA KARTI", app.language)
            theme_text_color: "Custom"
            text_color: ftheme.bank_card_text(app.theme_cls.theme_style, True)
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
                text: app.tr("Banka Kartı", app.language)
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
            text: app.tr("Güncel Bakiye", app.language)
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
        text: app.tr("Kart Kullanım Özeti", app.language)
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
                text: app.tr("İnternet Alışverişi", app.language)
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
                text: app.tr("Kartı Dondur", app.language)
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
        text: app.tr("Son Hareketler", app.language)
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
    height: "120dp"
    padding: "16dp"
    spacing: "8dp"
    orientation: "vertical"
    style: "outlined"
    radius: [dp(20)]
    md_bg_color: ftheme.elevated_bg(app.theme_cls.theme_style)
    line_color: ftheme.card_line(app.theme_cls.theme_style)

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
        text: app.tr("Bakiye", app.language)
        font_style: "Caption"
        theme_text_color: "Secondary"
        
    MDLabel:
        text: root.balance
        font_style: "H6"
        bold: True
        theme_text_color: "Primary"

<ActiveAssetsBentoWidget>:
    size_hint_y: None
    # 16dp padding (üst+alt) + 88dp metin bloğu = 120dp; içerik tam sığar,
    # taşma/preslenme olmadan dikeyde ortalanır.
    height: "120dp"
    padding: "16dp"
    spacing: "14dp"
    orientation: "horizontal"
    style: "outlined"
    elevation: 0
    radius: [dp(20)]
    md_bg_color: ftheme.tint_bg(app.theme_cls.theme_style, 'green')
    line_color: ftheme.card_line(app.theme_cls.theme_style)

    # Simge kartı: satırın dikey merkezine sabitlenir.
    MDCard:
        size_hint: None, None
        size: "52dp", "52dp"
        pos_hint: {"center_y": 0.5}
        radius: [dp(16)]
        elevation: 0
        md_bg_color: ftheme.elevated_bg(app.theme_cls.theme_style)

        # MDIcon kendi boyutunu texture'a (~27dp) sabitler ve dikey MDCard
        # (BoxLayout) içinde tek çocuk olarak sol-alta düşer — simge tepside
        # 'yamuk' görünürdü. AnchorLayout tepsiyi doldurup glyph'i her iki
        # eksende kusursuz merkezler.
        AnchorLayout:
            anchor_x: "center"
            anchor_y: "center"

            MDIcon:
                icon: "wallet-outline"
                size_hint: None, None
                size: self.texture_size
                theme_text_color: "Custom"
                text_color: ftheme.accent(app.theme_cls.theme_style, 'green')
                font_size: "27sp"

    # Metin bloğu da tam olarak simge ile AYNI eksende (center_y: 0.5)
    # ortalanır; böylece cüzdan simgesi metin bloğunun dikey merkeziyle
    # kusursuz hizalanır (eskiden blok yukarı yaslıydı, simge düşük görünüyordu).
    MDBoxLayout:
        orientation: "vertical"
        spacing: "2dp"
        size_hint_y: None
        adaptive_height: True
        pos_hint: {"center_y": 0.5}

        MDLabel:
            text: app.tr("Aktif Varlıklarım", app.language)
            font_style: "Subtitle1"
            bold: True
            valign: "center"
            shorten: True
            shorten_from: "right"
            theme_text_color: "Primary"
            size_hint_y: None
            height: "28dp"

        MDLabel:
            text: root.status_text
            font_style: "Caption"
            valign: "center"
            theme_text_color: "Secondary"
            shorten: True
            shorten_from: "right"
            size_hint_y: None
            height: "22dp"

        MDLabel:
            text: root.balance
            font_style: "H6"
            bold: True
            valign: "center"
            theme_text_color: "Custom"
            text_color: ftheme.accent(app.theme_cls.theme_style, 'green')
            size_hint_y: None
            height: "34dp"

<PremiumAssetMirrorWidget>:
    size_hint: None, None
    width: "300dp"
    height: "230dp"
    padding: "18dp"
    spacing: "12dp"
    orientation: "vertical"
    elevation: 0
    radius: [dp(20)]
    md_bg_color: 0.025, 0.27, 0.20, 1
    line_color: 0.15, 0.62, 0.45, 0.55

    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "38dp"

        MDIcon:
            icon: "chart-areaspline"
            theme_text_color: "Custom"
            text_color: 0.65, 1.0, 0.83, 1
            font_size: "28sp"
            size_hint_x: None
            width: "38dp"

        Widget:

        MDLabel:
            text: app.tr("SALT OKUNUR", app.language)
            font_style: "Overline"
            bold: True
            halign: "right"
            theme_text_color: "Custom"
            text_color: 0.65, 1.0, 0.83, 1

    MDLabel:
        text: root.account_name
        font_style: "H6"
        bold: True
        shorten: True
        shorten_from: "right"
        theme_text_color: "Custom"
        text_color: 0.96, 1.0, 0.98, 1
        size_hint_y: None
        height: "30dp"

    MDLabel:
        text: app.tr("Güncel Bakiye", app.language)
        font_style: "Caption"
        theme_text_color: "Custom"
        text_color: 0.70, 0.86, 0.79, 1
        size_hint_y: None
        height: "20dp"

    MDLabel:
        text: root.balance
        font_style: "H5"
        bold: True
        theme_text_color: "Custom"
        text_color: 1, 1, 1, 1
        size_hint_y: None
        height: "42dp"

    Widget:

    MDSeparator:
        color: 0.65, 1.0, 0.83, 0.22
        size_hint_y: None
        height: "1dp"

    MDLabel:
        text: app.tr("Gösterge hesabı • Harcama kaynağı değildir", app.language)
        font_style: "Caption"
        theme_text_color: "Custom"
        text_color: 0.70, 0.86, 0.79, 1
        size_hint_y: None
        height: "22dp"

# ── Premium Birikim Hedefi Kartı ────────────────────────────────────────────
# Aktif temaya uyumlu premium yüzey; Light'ta beyaz, Dark'ta gece yüzeyi.
# Bütün metin/ikon/buton boyutları sabit veya adaptive — yatay yamulma yok.
<SavingsGoalCard>:
    size_hint_x: 1
    adaptive_height: True
    padding: 0
    # Flat banking UI: açık temada kirli halo oluşturan KivyMD gölgesi yok.
    # Ayrım Light Mode'da aşağıdaki ince card_line ile sağlanır.
    elevation: 0
    radius: [dp(20)]
    md_bg_color: ftheme.card_bg(app.theme_cls.theme_style)
    line_color: ftheme.card_line(app.theme_cls.theme_style)

    MDBoxLayout:
        orientation: "vertical"
        adaptive_height: True
        padding: "18dp"
        spacing: "14dp"
        radius: [dp(20)]
        md_bg_color: ftheme.card_bg(app.theme_cls.theme_style)

        # ── Başlık: ikon + hedef adı (sola yaslı, keskin) + yüzde ──
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: "34dp"
            spacing: "10dp"

            MDIcon:
                icon: root.goal_icon
                theme_text_color: "Custom"
                text_color: ftheme.accent(app.theme_cls.theme_style, "green")
                font_size: "26sp"
                halign: "center"
                valign: "middle"
                size_hint: None, None
                size: "30dp", "30dp"
                pos_hint: {"center_y": 0.5}

            MDLabel:
                text: root.goal_name
                theme_text_color: "Primary"
                font_style: "H6"
                bold: True
                halign: "left"
                valign: "middle"
                shorten: True
                shorten_from: "right"
                pos_hint: {"center_y": 0.5}

            MDLabel:
                text: root.pct_text
                theme_text_color: "Custom"
                text_color: ftheme.accent(app.theme_cls.theme_style, "green")
                font_style: "Subtitle1"
                bold: True
                halign: "right"
                valign: "middle"
                size_hint_x: None
                width: "78dp"
                pos_hint: {"center_y": 0.5}

            MDIconButton:
                icon: "trash-can-outline"
                tooltip_text: "Hedefi sil"
                theme_text_color: "Custom"
                text_color: ftheme.accent(app.theme_cls.theme_style, "muted")
                size_hint: None, None
                size: "36dp", "36dp"
                pos_hint: {"center_y": 0.5}
                on_release: app.open_delete_savings_goal_dialog(root.goal_index, root)

        # ── İlerleme çubuğu: value = biriken/hedef * 100 ──
        MDProgressBar:
            value: root.progress
            max: 100
            color: ftheme.accent(app.theme_cls.theme_style, "green")
            size_hint_y: None
            height: "6dp"

        # ── Durum / tahmini süre (sönük, tek satır) ──
        MDLabel:
            text: root.status_text
            font_style: "Caption"
            theme_text_color: "Secondary"
            halign: "left"
            valign: "middle"
            shorten: True
            shorten_from: "right"
            size_hint_y: None
            height: "18dp"

        # ── Tutarlar: Toplanan (sol) | Hedef (sağ) ──
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: "42dp"

            MDBoxLayout:
                orientation: "vertical"
                MDLabel:
                    text: app.tr("Toplanan", app.language)
                    font_style: "Caption"
                    theme_text_color: "Secondary"
                    halign: "left"
                MDLabel:
                    text: root.saved_text
                    theme_text_color: "Primary"
                    font_style: "Subtitle1"
                    bold: True
                    halign: "left"

            MDBoxLayout:
                orientation: "vertical"
                MDLabel:
                    text: app.tr("Hedef", app.language)
                    font_style: "Caption"
                    theme_text_color: "Secondary"
                    halign: "right"
                MDLabel:
                    text: root.target_text
                    theme_text_color: "Primary"
                    font_style: "Subtitle1"
                    bold: True
                    halign: "right"

        # ── Tek, sağa yaslı, tema-primary 'Biriktir' butonu ──
        AnchorLayout:
            anchor_x: "right"
            anchor_y: "center"
            size_hint_y: None
            height: "40dp"
            MDRaisedButton:
                text: app.tr("Biriktir", app.language)
                icon: "plus"
                size_hint: None, None
                height: "40dp"
                elevation: 0
                md_bg_color: app.theme_cls.primary_color
                theme_text_color: "Custom"
                text_color: ftheme.on_primary(app.theme_cls.theme_style)
                on_release: app.add_funds_to_goal(root.goal_index)

# ── Mini Kart Önizlemesi (işlem formunda seçili ödeme yöntemi) ───────────────
# Kartlarım estetiğinin küçültülmüş prototipi: koyu yüzey, sol ikon tepsisi,
# ad + son 4 hane, sağda Güncel Limit/Bakiye. Salt bilgilendirme amaçlıdır.
<MiniCardPreviewWidget>:
    size_hint_y: None
    height: "74dp"
    padding: "12dp"
    spacing: "12dp"
    orientation: "horizontal"
    radius: [dp(16)]
    elevation: 0
    md_bg_color: 0.09, 0.10, 0.12, 1
    line_color: 0, 0, 0, 0

    # Sol: ikon tepsisi (glyph AnchorLayout ile kusursuz merkezlenir)
    MDCard:
        size_hint: None, None
        size: "44dp", "44dp"
        pos_hint: {"center_y": 0.5}
        radius: [dp(12)]
        elevation: 0
        md_bg_color: 0.16, 0.18, 0.22, 1

        AnchorLayout:
            anchor_x: "center"
            anchor_y: "center"
            MDIcon:
                icon: root.icon
                size_hint: None, None
                size: self.texture_size
                theme_text_color: "Custom"
                text_color: root.accent_color
                font_size: "22sp"

    # Orta: ad + maskeli numara
    MDBoxLayout:
        orientation: "vertical"
        spacing: "2dp"
        adaptive_height: True
        pos_hint: {"center_y": 0.5}

        MDLabel:
            text: root.card_name
            font_style: "Subtitle2"
            bold: True
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            shorten: True
            shorten_from: "right"
            size_hint_y: None
            height: "22dp"

        MDLabel:
            text: root.masked_text
            font_style: "Caption"
            theme_text_color: "Custom"
            text_color: 0.70, 0.72, 0.78, 1
            shorten: True
            shorten_from: "right"
            size_hint_y: None
            height: "18dp"

    # Sağ: Güncel Limit / Güncel Bakiye
    MDBoxLayout:
        orientation: "vertical"
        spacing: "2dp"
        adaptive_height: True
        size_hint_x: None
        width: "130dp"
        pos_hint: {"center_y": 0.5}

        MDLabel:
            text: root.info_label
            font_style: "Caption"
            halign: "right"
            theme_text_color: "Custom"
            text_color: 0.62, 0.64, 0.70, 1
            size_hint_y: None
            height: "16dp"

        MDLabel:
            text: root.info_value
            font_style: "Subtitle1"
            bold: True
            halign: "right"
            theme_text_color: "Custom"
            text_color: root.accent_color
            size_hint_y: None
            height: "24dp"
''')

class MiniCardPreviewWidget(MDCard):
    card_name = StringProperty("")
    masked_text = StringProperty("")
    info_label = StringProperty("Güncel Bakiye")
    info_value = StringProperty("₺0,00")
    icon = StringProperty("credit-card-outline")
    # Kredi kartı için teal, vadesiz hesap için yeşil vurgular (mixin atar).
    accent_color = ColorProperty((0.30, 0.80, 0.75, 1))

class SavingsGoalCard(MDCard):
    goal_index = NumericProperty(0)
    goal_name = StringProperty("")
    goal_icon = StringProperty("piggy-bank")
    pct_text = StringProperty("%0")
    progress = NumericProperty(0.0)
    status_text = StringProperty("")
    saved_text = StringProperty("₺0,00")
    target_text = StringProperty("₺0,00")

class PremiumCreditCardWidget(MDCard):
    account_id = NumericProperty(0)
    debt_ratio = NumericProperty(0.0)
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

class PremiumAssetMirrorWidget(MDCard):
    account_name = StringProperty("Aktif Varlıklarım")
    balance = StringProperty("₺0,00")

class BentoAccountWidget(MDCard):
    account_name = StringProperty("")
    account_type_label = StringProperty("")
    balance = StringProperty("₺0,00")

class ActiveAssetsBentoWidget(MDCard):
    balance = StringProperty("Hesaplanıyor…")
    status_text = StringProperty("Canlı portföy değeri yükleniyor")
