"""Kategori bazlı aylık bütçe takip arayüzü."""

import datetime
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.button import MDRaisedButton

from ui.i18n import tr as _t
from utils.formatters import attach_amount_mask, read_amount, set_amount


GREEN = (0.18, 0.8, 0.25, 1)
RED = (0.9, 0.2, 0.2, 1)
AMBER = (0.95, 0.6, 0.1, 1)
MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def _fmt(value):
    return (
        f"{float(value):,.2f} ₺"
        .replace(",", "X").replace(".", ",").replace("X", ".")
    )


def planner_month_range(today=None):
    """Planlama ufku: bulunduğumuz aydan yıl sonuna (Aralık) kadar olan aylar.

    Aşama 2, madde 2.1: "Planlama süreci bulunduğumuz aydan başlayıp yıl sonuna
    (Aralık) kadar ilerlemeli. (Örn: Ocak ayındaysak tüm aylar listelenmeli)."
    Geçmiş aylar planlayıcıda gösterilmez — Temmuz'daysak Temmuz–Aralık,
    Ocak'taysak tüm yıl döner. Saf fonksiyon: widget'a dokunmadan test edilir.
    """
    month = (today or datetime.date.today()).month
    return list(range(month, 13))


class BudgetMixin:
    def _planner_ids(self):
        """Planlayıcı bileşeninin id sözlüğünü döndürür.

        Panel artık ızgarada sabit durmuyor; `show_budget_planner` her açılışta
        yeni bir `<BudgetPlannerPanel@MDCard>` (ui/tools.kv) örnekleyip
        `self._budget_planner_panel`'e koyuyor. Dinamik sınıf kuralı içindeki
        id'ler PANELİN KENDİ `ids` sözlüğünde yaşar, uygulamanın `root.ids`'inde
        değil — bu yüzden `projection_label` gibi erişimler buradan geçer.

        Önce canlı panel referansına, sonra (paneli KV'de sabit geri taşımak
        isteyen biri için) `root.ids`'e bakar; hiçbiri yoksa boş sözlük döner —
        widget ağacı kurulmadan çağrılan testlerde güvenli davranış.
        """
        panel = getattr(self, "_budget_planner_panel", None)
        if panel is not None:
            return getattr(panel, "ids", {}) or {}
        root = getattr(self, "root", None)
        if root is None:
            return {}
        root_ids = getattr(root, "ids", {}) or {}
        stray = root_ids.get("budget_planner_panel") if hasattr(root_ids, "get") else None
        if stray is not None:
            return getattr(stray, "ids", {}) or {}
        return root_ids

    def setup_dynamic_months(self):
        now = datetime.date.today()
        self.active_budget_month = now.month
        self.active_budget_year = now.year
        container = self._planner_ids().get("month_selector_container")
        if not container:
            return
        container.clear_widgets()
        from kivymd.uix.button import MDRoundFlatButton
        for month in planner_month_range(now):
            button = MDRoundFlatButton(text=_t(MONTHS[month - 1]))
            button.bind(
                on_release=lambda _button, value=month:
                    self.change_budget_month(value)
            )
            container.add_widget(button)

    def change_budget_month(self, month_index, year=None):
        self.active_budget_month = int(month_index)
        if year is not None:
            self.active_budget_year = int(year)
        elif not hasattr(self, "active_budget_year"):
            self.active_budget_year = datetime.date.today().year
        self.load_budget_list()
        self.generate_next_month_projection()

    # ─── Bütçe özeti (saf hesap) ─────────────────────────────────────────────

    @staticmethod
    def compute_budget_summary(month, year):
        """(harcanan, limit, yüzde) üçlüsünü hesaplar.

        Widget'a DOKUNMAZ: saf veri üretir ki Kivy ağacı kurmadan test
        edilebilsin. Limit = planlanan gider + ayrılmış abonelik gideri;
        harcanan = o ay gerçekleşen (bakiyeye işlenmiş) giderler. Yüzde 100'ü
        aşabilir (aşımı gizlememek için); sıkıştırma çağırana bırakılır.

        Araçlar ızgarasındaki bütçe karesine küçük bir "%X kullanıldı" alt
        satırı eklemek istenirse veri kaynağı budur.
        """
        from services.budget_service import (
            calculate_monthly_budget, get_category_budget_progress,
        )
        totals = calculate_monthly_budget(month, year)
        limit = float(totals["planned_expense"]) + float(
            totals["reserved_recurring"])
        spent = sum(
            float(item["actual"])
            for item in get_category_budget_progress(month, year)
        )
        percent = (spent / limit * 100.0) if limit > 0 else 0.0
        return spent, limit, max(0.0, percent)

    def _budget_period(self):
        today = datetime.date.today()
        return (
            int(getattr(self, "active_budget_month", today.month)),
            int(getattr(self, "active_budget_year", today.year)),
        )

    def generate_next_month_projection(self):
        from services.budget_service import calculate_monthly_budget
        month, year = self._budget_period()
        budget = calculate_monthly_budget(month, year)
        remaining = budget["remaining_budget"]
        reserved = budget["reserved_recurring"]
        advice, icon, color = _t("Bütçeniz dengede."), "check-circle", GREEN
        if remaining < 0:
            advice, icon, color = (
                _t("Dikkat: Planlanan giderler, gelirlerinizi aşıyor. Bütçeniz eksiye düşecek!"),
                "close-circle", RED,
            )
        elif remaining == 0:
            advice, icon, color = (
                _t("Dikkat: Gelir ve gideriniz başa baş. Bütçenizde hiç esneme payı yok."),
                "alert", AMBER,
            )
        planner_ids = self._planner_ids()
        projection_label = planner_ids.get("projection_label")
        if projection_label is not None:
            reserved_text = (
                f"\n{_t('Ayrılmış abonelik gideri:')} {_fmt(reserved)}"
                if reserved else ""
            )
            projection_label.text = (
                f"{_t(MONTHS[month - 1])} {year} · "
                f"{_t('Harcama limitiniz:')} {_fmt(remaining)}"
                f"{reserved_text}\n\n{advice}"
            )
            projection_icon = planner_ids.get("projection_icon")
            if projection_icon is not None:
                projection_icon.icon = icon
                projection_icon.text_color = color
        return {
            "harcanabilir_limit": remaining,
            "ayrilmis_abonelik_gideri": reserved,
            "tavsiye": advice,
            "tavsiye_ikonu": icon,
        }

    # ── Planlayıcı görünümü (Araçlar karesinden açılan diyalog) ──────────────
    def show_budget_planner(self):
        """Bütçe planlayıcı panelini bir diyalog içinde açar.

        Araçlar ızgarasındaki "Aylık Bütçe" karesi ile panelin trend butonu
        buraya gelir. Panel artık ızgarada sabit durmuyor; her açılışta
        ui/tools.kv'deki `<BudgetPlannerPanel@MDCard>` yeniden örneklenir ve
        `self._budget_planner_panel`'e konur (bkz. _planner_ids). Ay seçici,
        projeksiyon ve kalem listesi panel kurulduktan SONRA doldurulur —
        aksi halde diyalog boş ay seçiciyle açılırdı.
        """
        from kivy.factory import Factory
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.dialog import MDDialog

        old = getattr(self, "bp_planner_dialog", None)
        if old is not None:
            try:
                old.dismiss()
            except Exception:
                pass

        panel = Factory.BudgetPlannerPanel()
        self._budget_planner_panel = panel
        # Panelin detay listesini load_budget_list'e bağla (bu bağ olmadan
        # liste hiç dolmuyordu — bp_list_container hiçbir yerde atanmıyordu).
        self.bp_list_container = panel.ids.get("budget_detailed_list")

        self.bp_planner_dialog = MDDialog(
            type="custom", content_cls=panel,
            buttons=[MDFlatButton(
                text=_t("KAPAT"),
                on_release=lambda _b: self.bp_planner_dialog.dismiss(),
            )],
        )

        def _clear_panel_ref(*_args):
            # Diyalog kapanınca canlı panel referansı bayatlar; _planner_ids
            # kapalı bir panele yazmaya çalışmasın.
            if getattr(self, "_budget_planner_panel", None) is panel:
                self._budget_planner_panel = None
                self.bp_list_container = None

        self.bp_planner_dialog.bind(on_dismiss=_clear_panel_ref)
        self.bp_planner_dialog.open()

        # Panel ağaca girdikten sonra doldur (ids şimdi erişilebilir).
        self.setup_dynamic_months()
        self.change_budget_month(
            getattr(self, "active_budget_month", datetime.date.today().month),
            getattr(self, "active_budget_year", datetime.date.today().year),
        )

    # ── "Bunu mevcut planınız olarak kullanmak ister misiniz?" (madde 2.1) ───
    def confirm_plan_as_current(self, *args):
        """Kullanıcı sabit gelir/gider/yatırımlarını girdikten sonra planı
        onaylatır; onaylanırsa bu ayın kalemleri yıl sonuna (Aralık) kadar
        tüm aylara kopyalanır."""
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.dialog import MDDialog

        month, year = self._budget_period()
        month_name = _t(MONTHS[month - 1])

        def _confirm(_button):
            self.plan_confirm_dialog.dismiss()
            self._apply_plan_as_current(month, year)

        self.plan_confirm_dialog = MDDialog(
            title=_t("Planı Onayla"),
            text=_t(
                "Bunu mevcut planınız olarak kullanmak ister misiniz?"
            ) + f"\n\n{month_name} " + _t(
                "ayının kalemleri Aralık'a kadar tüm aylara uygulanacak."
            ),
            buttons=[
                MDFlatButton(
                    text=_t("VAZGEÇ"),
                    on_release=lambda _b: self.plan_confirm_dialog.dismiss(),
                ),
                MDRaisedButton(text=_t("EVET, UYGULA"), on_release=_confirm),
            ],
        )
        self.plan_confirm_dialog.open()

    def _apply_plan_as_current(self, month, year):
        from services.budget_service import apply_plan_to_year_end

        def worker():
            try:
                count = apply_plan_to_year_end(month, year)
            except Exception as exc:
                print("Plan uygulanamadı:", exc)
                count = None
            Clock.schedule_once(
                lambda _dt: self._after_plan_applied(count), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _after_plan_applied(self, count):
        if count is None:
            toast(_t("Plan uygulanırken bir hata oluştu."))
            return
        if count == 0:
            toast(_t("Plan zaten güncel; yeni kalem eklenmedi."))
        else:
            toast(f"{_t('Plan uygulandı')}: {count} "
                  + _t("kalem yıl sonuna kadar eklendi."))
        try:
            self.load_budget_list()
            self.generate_next_month_projection()
        except Exception as exc:
            print("Liste tazelenemedi:", exc)

    # ── Kalem ekleme formu ──────────────────────────────────────────────────
    def open_budget_item_form(self):
        from kivy.uix.gridlayout import GridLayout
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.card import MDCard
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.label import MDIcon, MDLabel
        from kivymd.uix.segmentedcontrol import (
            MDSegmentedControl, MDSegmentedControlItem,
        )
        from kivymd.uix.selectioncontrol import MDSwitch
        from kivymd.uix.textfield import MDTextField
        import ui.theme as ftheme

        self.bp_selected_type = "expense"
        self.bp_selected_category = None
        self.editing_item_id = None
        self.editing_item_is_template = False

        form = MDBoxLayout(
            orientation="vertical", adaptive_height=True,
            spacing=dp(16), padding=[dp(20), 0, dp(20), 0],
        )
        self.bp_outer_scroll = None
        self.bp_form_layout = form

        type_surface = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(48),
            padding=dp(3), radius=[dp(12)],
            elevation=0, md_bg_color=ftheme.muted_bg(self.theme_cls),
        )
        self.bp_type_segment = MDSegmentedControl(
            size_hint_y=None, height=dp(42), radius=dp(10),
            md_bg_color=ftheme.muted_bg(self.theme_cls),
            segment_color=self.theme_cls.primary_color,
            separator_color=(0, 0, 0, 0),
            segment_switching_transition="out_cubic",
        )
        self.bp_type_segment.add_widget(
            MDSegmentedControlItem(text=_t("Gider"))
        )
        self.bp_type_segment.add_widget(
            MDSegmentedControlItem(text=_t("Gelir"))
        )
        self.bp_type_segment.bind(on_active=self._on_budget_type)
        type_surface.add_widget(self.bp_type_segment)

        self.bp_category_button = MDCard(
            orientation="horizontal", size_hint_y=None, height=dp(52),
            padding=[dp(16), 0, dp(10), 0], spacing=dp(12),
            radius=[dp(12)], elevation=0,
            md_bg_color=ftheme.elevated_bg(self.theme_cls),
            line_color=ftheme.card_line(self.theme_cls),
        )
        self.bp_category_button.bind(
            on_release=self.open_budget_category_menu
        )
        self.bp_category_button.add_widget(MDIcon(
            icon="tag-outline", size_hint_x=None, width=dp(24),
            pos_hint={"center_y": 0.5},
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
        ))
        self.bp_category_label = MDLabel(
            text=_t("Kategori seçin"), valign="center",
            pos_hint={"center_y": 0.5},
        )
        self.bp_category_button.add_widget(self.bp_category_label)
        self.bp_category_button.add_widget(MDIcon(
            icon="chevron-down", size_hint_x=None, width=dp(24),
            pos_hint={"center_y": 0.5},
            theme_text_color="Secondary",
        ))

        self.bp_name_input = MDTextField(
            hint_text=_t("Serbest plan adı"),
            size_hint_y=None, height=dp(58),
            opacity=0, disabled=True,
        )
        self.bp_name_container = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=0,
        )
        self.bp_name_container.add_widget(self.bp_name_input)

        amount_row = MDCard(
            orientation="horizontal", size_hint_y=None, height=dp(62),
            spacing=dp(8), padding=[dp(16), 0, dp(8), 0],
            radius=[dp(10)], elevation=0, md_bg_color=(0, 0, 0, 0),
            ripple_behavior=True,
        )
        self.bp_currency_label = MDLabel(
            text="₺", font_style="H5", halign="center", valign="center",
            size_hint_x=None, width=dp(32),
            pos_hint={"center_y": 0.5},
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
        )
        # input_filter maskeleme tarafından kurulur; Kivy'nin "float" filtresi
        # binlik ayraç noktalarıyla çakışıyor (bkz. utils/formatters).
        self.bp_amount_input = attach_amount_mask(MDTextField(
            hint_text=_t("Tutar"),
            size_hint_y=None, height=dp(58),
            padding=[dp(12), dp(12), dp(8), dp(12)],
        ))
        amount_row.bind(on_release=lambda *args: setattr(self.bp_amount_input, 'focus', True))
        amount_row.add_widget(self.bp_currency_label)
        amount_row.add_widget(self.bp_amount_input)

        frequency_surface = MDCard(
            orientation="vertical", size_hint_y=None, height=dp(48),
            padding=dp(3), radius=[dp(12)],
            elevation=0, md_bg_color=ftheme.muted_bg(self.theme_cls),
        )
        self.bp_frequency_segment = MDSegmentedControl(
            size_hint_y=None, height=dp(42), radius=dp(10),
            md_bg_color=ftheme.muted_bg(self.theme_cls),
            segment_color=self.theme_cls.primary_color,
            separator_color=(0, 0, 0, 0),
            segment_switching_transition="out_cubic",
        )
        self.bp_frequency_segment.add_widget(
            MDSegmentedControlItem(text=_t("Tek seferlik"))
        )
        self.bp_frequency_segment.add_widget(
            MDSegmentedControlItem(text=_t("Her ay"))
        )
        self.bp_frequency_segment.bind(on_active=self._on_budget_frequency)
        frequency_surface.add_widget(self.bp_frequency_segment)

        self.bp_rollover_switch, rollover_row = self._switch_row(
            _t("Geçen ayın kalanını/aşımını devret"), MDSwitch, MDLabel
        )
        # Veri katmanıyla uyumu korur; görünür karşılığı frekans seçimidir.
        self.bp_template_switch = MDSwitch()
        self.bp_repeat_switch, repeat_row = self._switch_row(
            _t("Mevcut kalemi diğer aylara da uygula"), MDSwitch, MDLabel
        )
        self.bp_alert_input = MDTextField(
            text="80", hint_text=_t("Uyarı eşiği (%)"),
            input_filter="int", size_hint_y=None, height=dp(52),
        )

        self.months_grid = GridLayout(
            cols=3, spacing=dp(8), size_hint_y=None, height=0, opacity=0,
        )
        month, _year = self._budget_period()
        for month_index in range(1, 13):
            button = MDRaisedButton(
                text=_t(MONTHS[month_index - 1]),
                size_hint=(1, None), height=dp(36), elevation=0,
            )
            button.month_index = month_index
            button.is_selected = month_index == month
            button.bind(on_release=self.toggle_custom_month_button)
            self.months_grid.add_widget(button)
        self.bp_repeat_switch.bind(active=self._toggle_month_grid)

        self.bp_advanced_box = MDBoxLayout(
            orientation="vertical", spacing=dp(16),
            size_hint_y=None, height=0, opacity=0, disabled=True,
        )
        self.bp_advanced_box.bind(
            minimum_height=self._sync_budget_advanced_height
        )
        for widget in (
            MDFlatButton(
                text=_t("Geçmişe göre tutar öner"),
                size_hint_y=None, height=dp(40),
                on_release=self.suggest_budget_amount,
            ),
            rollover_row, self.bp_alert_input, repeat_row, self.months_grid,
        ):
            self.bp_advanced_box.add_widget(widget)

        self.bp_advanced_button = MDCard(
            orientation="horizontal", size_hint_y=None, height=dp(44),
            padding=[dp(12), 0, dp(10), 0], spacing=dp(8),
            radius=[dp(10)], elevation=0,
            md_bg_color=(0, 0, 0, 0),
            ripple_behavior=True,
        )
        self.bp_advanced_button.bind(
            on_release=self._toggle_budget_advanced
        )
        self.bp_advanced_label = MDLabel(
            text=_t("Daha fazla seçenek"), valign="center",
            pos_hint={"center_y": 0.5},
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
        )
        self.bp_advanced_icon = MDIcon(
            icon="chevron-down", size_hint_x=None, width=dp(24),
            pos_hint={"center_y": 0.5},
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
        )
        self.bp_advanced_button.add_widget(self.bp_advanced_label)
        self.bp_advanced_button.add_widget(self.bp_advanced_icon)

        for widget in (
            type_surface, self.bp_category_button,
            self.bp_name_container, amount_row,
            frequency_surface, self.bp_advanced_button,
            self.bp_advanced_box,
        ):
            form.add_widget(widget)

        self.bp_dialog = MDDialog(
            title=_t("Bütçe kalemi ekle"), type="custom", content_cls=form,
            buttons=[
                MDFlatButton(
                    text=_t("İPTAL"),
                    on_release=lambda _button: self.bp_dialog.dismiss(),
                ),
                MDRaisedButton(
                    text=_t("BÜTÇEYE EKLE"), on_release=self.save_budget_item,
                ),
            ],
        )
        self.bp_dialog.open()

    def _switch_row(self, text, switch_cls, label_cls):
        from kivymd.uix.boxlayout import MDBoxLayout
        row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(44), spacing=dp(8),
        )
        label = label_cls(text=text, valign="center")
        switch = switch_cls(size_hint_x=None, width=dp(56))
        row.add_widget(label)
        row.add_widget(switch)
        return switch, row

    def _on_budget_type(self, _segment, item):
        self.bp_selected_type = (
            "expense" if item.text == _t("Gider") else "income"
        )
        self.bp_selected_category = None
        self.bp_category_label.text = _t("Kategori seçin")
        self.bp_name_input.text = ""
        self.bp_name_input.disabled = True
        self.bp_name_input.opacity = 0
        self.bp_name_container.height = 0

    def _on_budget_frequency(self, _segment, item):
        self.bp_template_switch.active = item.text == _t("Her ay")

    def _toggle_budget_advanced(self, *args):
        expanded = self.bp_advanced_box.height == 0
        self.bp_advanced_box.height = (
            self.bp_advanced_box.minimum_height if expanded else 0
        )
        self.bp_advanced_box.opacity = 1 if expanded else 0
        self.bp_advanced_box.disabled = not expanded
        self.bp_advanced_label.text = _t(
            "Daha az seçenek" if expanded else "Daha fazla seçenek"
        )
        self.bp_advanced_icon.icon = (
            "chevron-up" if expanded else "chevron-down"
        )
        self._refresh_budget_dialog_height()

    def _sync_budget_advanced_height(self, _box, minimum_height):
        if self.bp_advanced_box.opacity:
            self.bp_advanced_box.height = minimum_height
            self._refresh_budget_dialog_height()

    def _refresh_budget_dialog_height(self, *args):
        dialog = getattr(self, "bp_dialog", None)
        if not dialog:
            return

        def apply_size(_dt):
            from kivy.core.window import Window

            dialog.height = min(
                dialog.ids.container.height, Window.height - dp(32)
            )
            dialog.center = Window.center

        def update(_dt):
            dialog.update_height()
            # MDDialog container'ı yeni içerik yüksekliğini bir sonraki layout
            # turunda hesaplar; modal boyutunu o hesap tamamlanınca uygula.
            Clock.schedule_once(apply_size, 0.05)

        Clock.schedule_once(update, 0)

    def open_budget_category_menu(self, *args):
        """TransactionMixin'in aranabilir kategori diyaloğu deseni."""
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.list import MDList, OneLineListItem
        from services.queries import CategoryService
        import ui.theme as ftheme

        categories = [
            str(row["name"])
            for row in CategoryService.get_categories(self.bp_selected_type)
        ]
        search = ftheme.make_text_field(
            _t("Kategori ara..."), self.theme_cls,
            size_hint_y=None, height=dp(48),
        )
        listing = MDList()
        self.bp_category_search = search
        self.bp_category_list = listing
        scroll = ScrollView()
        scroll.add_widget(listing)
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None,
            height=dp(390), spacing=dp(8),
        )
        content.add_widget(search)
        content.add_widget(scroll)

        def populate(query=""):
            listing.clear_widgets()
            free = OneLineListItem(text=_t("Serbest metin gir"))
            free.bind(on_release=lambda _item: self._select_budget_category(None))
            listing.add_widget(free)
            needle = query.strip().casefold()
            for category in categories:
                if needle and needle not in category.casefold() and needle not in _t(category).casefold():
                    continue
                item = OneLineListItem(text=_t(category))
                item.bind(
                    on_release=lambda _item, value=category:
                        self._select_budget_category(value)
                )
                listing.add_widget(item)

        search.bind(text=lambda _field, value: populate(value))
        populate()
        self.bp_category_dialog = MDDialog(
            title=_t("Kategori Seç"), type="custom", content_cls=content,
        )
        self.bp_category_dialog.open()

    def _select_budget_category(self, category):
        self.bp_selected_category = category
        if category is None:
            self.bp_category_label.text = _t("Serbest metin gir")
            self.bp_name_input.disabled = False
            self.bp_name_input.opacity = 1
            self.bp_name_container.height = dp(58)
        else:
            self.bp_category_label.text = _t(category)
            self.bp_name_input.text = category
            self.bp_name_input.disabled = True
            self.bp_name_input.opacity = 0
            self.bp_name_container.height = 0
        self._refresh_budget_dialog_height()
        if getattr(self, "bp_category_dialog", None):
            self.bp_category_dialog.dismiss()

    def suggest_budget_amount(self, *args):
        category = getattr(self, "bp_selected_category", None)
        if not category:
            toast(_t("Öneri için önce kategori seçin."))
            return
        from services.budget_service import suggest_category_budget

        def worker():
            value = suggest_category_budget(category)
            Clock.schedule_once(lambda _dt: self._apply_budget_suggestion(value), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_budget_suggestion(self, value):
        if value is None:
            toast(_t("Bu kategori için yeterli geçmiş yok."))
            return
        # set_amount ZORUNLU: ham "1500.00" yazmak maskede "150.000" olurdu.
        set_amount(self.bp_amount_input, value)

    def _toggle_month_grid(self, _switch, active):
        self.months_grid.height = dp(164) if active else 0
        self.months_grid.opacity = 1 if active else 0
        self._refresh_budget_dialog_height()

    # ── Liste ────────────────────────────────────────────────────────────────
    def load_budget_list(self):
        container = getattr(self, "bp_list_container", None)
        if container is None:
            return
        container.clear_widgets()
        from kivy.uix.widget import Widget
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDFlatButton, MDIconButton
        from kivymd.uix.label import MDLabel
        from kivymd.uix.progressbar import MDProgressBar
        from services.budget_service import (
            get_category_budget_progress, get_effective_limit,
            get_effective_plan_items, get_reserved_recurring_items,
        )

        month, year = self._budget_period()
        recurring = get_reserved_recurring_items(month, year)
        self._section_title(container, "Sabit Giderler (Abonelikler)")
        if recurring:
            for payment in recurring:
                row = MDBoxLayout(
                    orientation="horizontal", size_hint_y=None, height=dp(48),
                )
                row.add_widget(MDLabel(
                    text=f"{payment['name']} · {_fmt(payment['reserved_amount'])}",
                    font_style="Body2",
                ))
                row.add_widget(MDFlatButton(
                    text=_t("YÖNET"), size_hint_x=None, width=dp(85),
                    on_release=lambda _button: self.open_subscription_management(),
                ))
                container.add_widget(row)
        else:
            container.add_widget(MDLabel(
                text=_t("Bu ay için ayrılmış abonelik gideri yok."),
                font_style="Caption", theme_text_color="Secondary",
                size_hint_y=None, height=dp(34),
            ))

        self._section_title(container, "Planlanan Kalemler")
        progress_map = {
            item["category"]: item
            for item in get_category_budget_progress(month, year)
        }
        rows = get_effective_plan_items(month, year)
        if not rows:
            container.add_widget(MDLabel(
                text=_t("Henüz planlanan kalem yok."),
                font_style="Caption", theme_text_color="Secondary",
                size_hint_y=None, height=dp(34),
            ))
            return

        for item in rows:
            category = item.get("category_name")
            progress = progress_map.get(category) if category else None
            height = dp(92 if progress else 60)
            row = MDBoxLayout(
                orientation="horizontal", size_hint_y=None, height=height,
                spacing=dp(6), padding=[dp(8), dp(5), dp(4), dp(5)],
            )
            text_col = MDBoxLayout(
                orientation="vertical", size_hint_x=1,
            )
            text_col.add_widget(MDLabel(
                text=item["name"], font_style="Body1",
                size_hint_y=None, height=dp(24),
            ))
            text_col.add_widget(MDLabel(
                text=f"{_t('Gelir' if item['type'] == 'income' else 'Gider')} · {_fmt(item['amount'])}"
                     + (_t(" · Şablon") if item.get("is_template") else ""),
                font_style="Caption", theme_text_color="Secondary",
                size_hint_y=None, height=dp(20),
            ))
            if progress:
                effective = get_effective_limit(category, month, year)
                carry = effective - progress["planned"]
                pct = (
                    progress["actual"] / effective * 100
                    if effective else None
                )
                threshold = int(item.get("alert_threshold_pct") or 80)
                color = GREEN if pct is not None and pct < threshold else (
                    AMBER if pct is not None and pct < 100 else RED
                )
                carry_text = (
                    f" ({carry:+.2f} TL {_t('geçen aydan devir')})"
                    if carry else ""
                )
                text_col.add_widget(MDLabel(
                    text=(
                        f"{_t('Gerçekleşen')}: {_fmt(progress['actual'])} / "
                        f"{_fmt(effective)}{carry_text}"
                    ),
                    font_style="Caption", size_hint_y=None, height=dp(20),
                    theme_text_color="Custom", text_color=color,
                ))
                bar = MDProgressBar(
                    value=min(100, max(0, pct or 0)),
                    color=color, size_hint_y=None, height=dp(6),
                )
                text_col.add_widget(bar)
            row.add_widget(text_col)
            row.add_widget(MDIconButton(
                icon="pencil", size_hint=(None, None), size=(dp(38), dp(38)),
                on_release=lambda _button, iid=item["id"]:
                    self.edit_budget_item(iid),
            ))
            row.add_widget(MDIconButton(
                icon="trash-can", theme_text_color="Custom", text_color=RED,
                size_hint=(None, None), size=(dp(38), dp(38)),
                on_release=lambda _button, iid=item["id"]:
                    self.delete_budget_item(iid),
            ))
            container.add_widget(row)
            container.add_widget(Widget(size_hint_y=None, height=dp(1)))

    def _section_title(self, container, text):
        from kivymd.uix.label import MDLabel
        container.add_widget(MDLabel(
            text=_t(text), bold=True, font_style="Subtitle2",
            size_hint_y=None, height=dp(34),
        ))

    # `open_subscription_management` artık mixins/subscription_mixin.py'de
    # gerçek bir yönetim diyaloğu olarak yaşıyor (iptal/iade/zam). Buradaki
    # yalnız toast gösteren stub kaldırıldı; MRO'da BudgetMixin önce geldiği
    # için burada durması gerçek uygulamayı gölgeliyordu.

    # ── CRUD ─────────────────────────────────────────────────────────────────
    def save_budget_item(self, *args):
        category = getattr(self, "bp_selected_category", None)
        name = (
            category or self.bp_name_input.text.strip()
        )
        if not name:
            toast(_t("Kalem adı boş olamaz!"))
            return
        try:
            # read_amount kanonik değeri okur; maskelenmiş "1.500" metnini
            # float() 1.5 diye okurdu.
            amount = read_amount(self.bp_amount_input)
            threshold = int(self.bp_alert_input.text or 80)
            if amount <= 0 or not 1 <= threshold <= 100:
                raise ValueError
        except (ValueError, TypeError):
            toast(_t("Tutar pozitif, uyarı eşiği 1-100 arasında olmalıdır."))
            return

        month, year = self._budget_period()
        template = bool(self.bp_template_switch.active)
        propagate = bool(self.bp_repeat_switch.active)
        if template and propagate:
            toast(_t("Şablon seçildi; belirli aylara kopyalama uygulanmadı."))
            propagate = False

        values = (
            self.bp_selected_type, name, amount, month, year, category,
            int(self.bp_rollover_switch.active), int(template), threshold,
        )

        editing_id = getattr(self, "editing_item_id", None)
        editing_item_is_template = getattr(self, "editing_item_is_template", False)

        propagate_targets = []
        if propagate:
            for child in self.months_grid.children:
                if getattr(child, "is_selected", False) and int(child.month_index) != month:
                    propagate_targets.append(int(child.month_index))

        def db_task():
            from database.db import get_connection
            conn = get_connection()
            try:
                if editing_id and not editing_item_is_template:
                    conn.execute(
                        """UPDATE monthly_budget_plan SET
                           type=?, name=?, amount=?, target_month=?, target_year=?,
                           category_name=?, rollover_enabled=?, is_template=?,
                           alert_threshold_pct=?
                           WHERE id=? AND target_month=? AND target_year=?""",
                        values + (editing_id, month, year),
                    )
                else:
                    insert_values = list(values)
                    if editing_id and editing_item_is_template:
                        insert_values[7] = 0
                    conn.execute(
                        """INSERT INTO monthly_budget_plan
                           (type,name,amount,target_month,target_year,category_name,
                            rollover_enabled,is_template,alert_threshold_pct)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        tuple(insert_values),
                    )
                if propagate:
                    for target in propagate_targets:
                        copied = list(values)
                        copied[3] = target
                        copied[7] = 0
                        conn.execute(
                            """INSERT INTO monthly_budget_plan
                               (type,name,amount,target_month,target_year,category_name,
                                rollover_enabled,is_template,alert_threshold_pct)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            tuple(copied),
                        )
                conn.commit()
            finally:
                conn.close()

            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self.on_save_success(category))

        import threading
        threading.Thread(target=db_task, daemon=True).start()

    def on_save_success(self, category):
        """Kayıt sonrası formu sıfırlar ve listeyi/özeti tazeler.

        DONMA KORUMASI: hafif state sıfırlama hemen yapılır, AĞIR iş (kalem
        listesinin baştan çizilmesi + projeksiyon + özet kartı) sonraki
        karelere dağıtılır. Hepsi tek karede koşarsa kullanıcı formu hızlıca
        kapatıp yeniden açtığında Kivy ana thread'i bir kare boyunca bloklanıp
        tıklamalara tepkisiz kalıyordu.

        Widget'lar diyalog kapandıysa artık başka bir forma ait olabilir, o
        yüzden her erişim tolere edilir.
        """
        # Başarı bildirimi (Aşama 2, madde 1.9): tek seferlik bütçe kalemi
        # eklendiğinde/güncellendiğinde kullanıcı hiçbir geri bildirim almıyordu.
        # editing_item_id sıfırlanmadan ÖNCE okunur; mesaj ekleme/güncelleme
        # ayrımını yansıtsın.
        was_edit = getattr(self, "editing_item_id", None) is not None
        toast(_t("Bütçe kalemi güncellendi!" if was_edit
                 else "Bütçe kalemi eklendi!"))
        self.editing_item_id = None
        self.editing_item_is_template = False
        for field_name in ("bp_amount_input", "bp_name_input"):
            if field_name == "bp_name_input" and category is not None:
                continue
            field = getattr(self, field_name, None)
            if field is not None:
                try:
                    field.text = ""
                except Exception:
                    pass

        def rebuild_list(_dt):
            try:
                self.load_budget_list()
            except Exception as exc:
                print("Bütçe listesi tazelenemedi:", exc)

        def rebuild_projection(_dt):
            try:
                self.generate_next_month_projection()
            except Exception as exc:
                print("Bütçe projeksiyonu tazelenemedi:", exc)

        Clock.schedule_once(rebuild_list, 0)
        Clock.schedule_once(rebuild_projection, 0.05)

    def toggle_custom_month_button(self, button):
        button.is_selected = not getattr(button, "is_selected", False)
        button.opacity = 1 if button.is_selected else 0.55

    def delete_budget_item(self, item_id):
        from database.db import get_connection
        month, year = self._budget_period()
        conn = get_connection()
        conn.execute(
            "DELETE FROM monthly_budget_plan "
            "WHERE id = ? AND (is_template = 1 OR "
            "(target_month = ? AND target_year = ?))",
            (item_id, month, year),
        )
        conn.commit()
        conn.close()
        self.load_budget_list()
        self.generate_next_month_projection()
        toast(_t("Kalem silindi."))

    def edit_budget_item(self, item_id):
        from database.db import get_connection
        month, year = self._budget_period()
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM monthly_budget_plan "
            "WHERE id = ? AND (is_template = 1 OR "
            "(target_month = ? AND target_year = ?))",
            (item_id, month, year),
        ).fetchone()
        conn.close()
        if not row:
            return
        self.editing_item_id = item_id
        self.editing_item_is_template = bool(row["is_template"])
        self.bp_selected_type = row["type"]
        self._select_budget_category(row["category_name"])
        self.bp_name_input.text = row["name"]
        set_amount(self.bp_amount_input, row["amount"])
        self.bp_rollover_switch.active = bool(row["rollover_enabled"])
        self.bp_template_switch.active = bool(row["is_template"])
        self.bp_alert_input.text = str(row["alert_threshold_pct"] or 80)

    # ── Trend ────────────────────────────────────────────────────────────────
    def show_budget_trend(self, *args):
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.label import MDLabel
        from services.budget_service import get_budget_trend
        from ui.charts import ScenarioComparisonChart

        data = get_budget_trend(6)
        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8),
            size_hint_y=None, height=dp(300),
        )
        chart = ScenarioComparisonChart(size_hint_y=None, height=dp(220))
        chart.set_series(
            [(index, item["planned"]) for index, item in enumerate(data)],
            [(index, item["actual"]) for index, item in enumerate(data)],
        )
        labels = MDLabel(
            text="   ".join(item["label"] for item in data),
            font_style="Caption", halign="center",
            size_hint_y=None, height=dp(35),
        )
        legend = MDLabel(
            text=_t("Gri: Planlanan · Renkli: Gerçekleşen"),
            font_style="Caption", halign="center",
            size_hint_y=None, height=dp(30),
        )
        content.add_widget(chart)
        content.add_widget(labels)
        content.add_widget(legend)
        self.budget_trend_dialog = MDDialog(
            title=_t("6 Aylık Bütçe Trendi"),
            type="custom", content_cls=content,
            buttons=[MDFlatButton(
                text=_t("KAPAT"),
                on_release=lambda _button: self.budget_trend_dialog.dismiss(),
            )],
        )
        self.budget_trend_dialog.open()
