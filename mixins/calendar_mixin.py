"""Takvim görünümü: ay ızgarası + seçili günün işlem listesi.

Öncesi: main.py::show_calendar_view yalnızca bir tarih seçici açıp seçilen
günün işlem SAYISINI toast ile gösteriyordu (Aşama 2, madde 1.9'un ilk,
eksik hâli). Bu mixin onun yerine geçiyor: gerçek bir ay-grid ekranı, hangi
günlerde işlem olduğunu görsel olarak işaretliyor, bir güne dokununca o
günün işlemlerini aynı diyalog içinde listeliyor.

Hesaplama services/calendar_service.py'de (Kivy'den bağımsız, şifreleme
kısıtına uyar — bkz. o dosyanın docstring'i); burada yalnızca arayüz kurulumu
var. Diyalog her açılışta yeniden kurulur (scenario_mixin.py'deki what-if
sandbox'la aynı desen), bu yüzden açıkken tema değişimi ayrıca ele alınmıyor
— dialog kapanıp yeniden açıldığında zaten güncel temayla kurulur.
"""
import calendar as _calendar_module
import datetime
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel

import ui.theme as ftheme
from ui.i18n import tr as _t

_MONTH_NAMES = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
# Pazartesi başlangıçlı, Türkçe kısaltmalar — calendar.monthcalendar de
# varsayılan olarak haftayı Pazartesi'den başlatır (calendar.setfirstweekday
# hiç çağrılmadığı sürece), ikisi aynı sırada.
_WEEKDAY_HEADERS = ["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pz"]


def _fmt(value):
    """main.py::_fmt_tr ile aynı kural — Türkçe binlik/ondalık ayracı."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CalendarMixin:
    """Takvim diyaloğunu açan ve ay/gün durumunu yöneten mixin."""

    _calendar_dialog = None
    _calendar_year = None
    _calendar_month = None
    _calendar_selected_date = None

    # ─── Giriş noktası ───────────────────────────────────────────────────────

    def open_calendar_view(self):
        """Takvim diyaloğunu yükleniyor ekranı gösterip ardından açar."""
        from kivymd.uix.dialog import MDDialog
        self._calendar_loading_dialog = MDDialog(
            title=_t("Lütfen Bekleyin"),
            text=_t("Takvim yükleniyor..."),
            auto_dismiss=False,
        )
        self._calendar_loading_dialog.open()
        
        # UI'ın çizilmesine izin verip takvim oluşturmayı biraz erteliyoruz
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self._build_calendar_view(), 0)

    def _build_calendar_view(self):
        """Asıl takvim diyaloğunu kurar ve gösterir."""
        if getattr(self, "_calendar_loading_dialog", None):
            self._calendar_loading_dialog.dismiss()
            self._calendar_loading_dialog = None

        today = datetime.date.today()
        self._calendar_year = today.year
        self._calendar_month = today.month
        self._calendar_selected_date = today

        self._calendar_month_label = MDLabel(
            font_style="Subtitle1", bold=True, halign="center",
            size_hint_y=None, height=dp(32),
        )
        self._calendar_grid_container = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None,
        )
        self._calendar_selected_label = MDLabel(
            font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(24),
        )
        self._calendar_tx_container = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None, adaptive_height=True,
        )

        header = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40),
        )
        prev_btn = MDFlatButton(
            text="<", size_hint_x=None, width=dp(48),
            on_release=lambda _b: self._change_calendar_month(-1),
        )
        next_btn = MDFlatButton(
            text=">", size_hint_x=None, width=dp(48),
            on_release=lambda _b: self._change_calendar_month(1),
        )
        header.add_widget(prev_btn)
        header.add_widget(self._calendar_month_label)
        header.add_widget(next_btn)

        weekday_row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(24),
        )
        for name in _WEEKDAY_HEADERS:
            weekday_row.add_widget(MDLabel(
                text=_t(name), font_style="Caption",
                theme_text_color="Secondary", halign="center",
            ))

        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8),
            padding=[dp(8), dp(4), dp(8), dp(4)],
            size_hint_y=None,
            height=dp(420),
        )
        content.add_widget(header)
        content.add_widget(weekday_row)
        content.add_widget(self._calendar_grid_container)
        content.add_widget(self._calendar_selected_label)
        content.add_widget(self._calendar_tx_container)

        self._calendar_dialog = MDDialog(
            title=_t("Takvim"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("KAPAT"),
                    theme_text_color="Custom",
                    text_color=ftheme.accent(self.theme_cls.theme_style, "muted"),
                    on_release=lambda _b: self._calendar_dialog.dismiss(),
                ),
            ],
        )
        self._calendar_dialog.open()

        self._render_calendar_month()
        self._select_calendar_day(today)

    def _change_calendar_month(self, delta):
        month = self._calendar_month + delta
        year = self._calendar_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self._calendar_year = year
        self._calendar_month = month
        self._render_calendar_month()

    # ─── Ay ızgarası ─────────────────────────────────────────────────────────

    def _render_calendar_month(self):
        """Seçili ay/yıl için ızgarayı yeniden kurar.

        Gün-sayısı sorgusu decrypt gerektirmiyor (yalnız COUNT(*)) — main.py
        eski on_calendar_date_save'deki gibi senkron çalıştırılabilecek kadar
        hafif, ayrı bir thread'e gerek yok.
        """
        from services.calendar_service import get_month_transaction_days

        year, month = self._calendar_year, self._calendar_month
        try:
            days_with_tx = get_month_transaction_days(year, month)
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Takvim ay verisi okunamadı")
            days_with_tx = {}

        self._calendar_month_label.text = _t(
            f"{_t(_MONTH_NAMES[month - 1])} {year}"
        )

        weeks = _calendar_module.monthcalendar(year, month)
        self._calendar_grid_container.height = dp(40) * len(weeks)
        self._calendar_grid_container.clear_widgets()
        # Gün hücrelerini tarihe göre sakla: seçim değiştiğinde ızgarayı baştan
        # kurmak yerine yalnızca ETKİLENEN iki hücre yeniden boyanır
        # (bkz. _select_calendar_day).
        self._calendar_day_cells = {}

        today = datetime.date.today()
        selected = self._calendar_selected_date
        for week in weeks:
            row = MDBoxLayout(
                orientation="horizontal", spacing=dp(3),
                size_hint_y=None, height=dp(36),
            )
            for day in week:
                if day == 0:
                    row.add_widget(MDBoxLayout())  # ay dışı boş hücre
                    continue
                cell_date = datetime.date(year, month, day)
                cell = self._build_calendar_day_cell(
                    cell_date,
                    has_tx=day in days_with_tx,
                    is_selected=(cell_date == selected),
                    is_today=(cell_date == today),
                )
                self._calendar_day_cells[cell_date] = cell
                row.add_widget(cell)
            self._calendar_grid_container.add_widget(row)

    def _build_calendar_day_cell(self, cell_date, has_tx, is_selected, is_today):
        card = MDCard(
            orientation="vertical", radius=[10], padding=0,
        )
        label = MDLabel(
            text=str(cell_date.day),
            halign="center",
            theme_text_color="Custom",
        )
        card.add_widget(label)
        # Yeniden boyama için gereken sabit bilgiler hücrenin üzerinde taşınır;
        # aksi halde her seferinde ay sorgusunu tekrar çalıştırmak gerekirdi.
        card._archlence_label = label
        card._archlence_has_tx = has_tx
        card._archlence_is_today = is_today
        self._style_calendar_day_cell(card, is_selected)
        ftheme.bind_card_tap(card, lambda d=cell_date: self._select_calendar_day(d))
        return card

    def _style_calendar_day_cell(self, card, is_selected):
        """Tek hücrenin seçili/seçili değil görünümünü uygular.

        Kurulum ve seçim değişimi AYNI yolu kullanır; iki ayrı boyama kodu
        olsaydı seçim vurgusu ile ilk çizim zamanla ayrışabilirdi.
        """
        style = self.theme_cls.theme_style
        has_tx = getattr(card, "_archlence_has_tx", False)
        is_today = getattr(card, "_archlence_is_today", False)

        if is_selected:
            card.md_bg_color = self.theme_cls.primary_color
            card.line_color = self.theme_cls.primary_color
            text_color = ftheme.on_primary(self.theme_cls)
        else:
            ftheme.apply_card_theme(
                card, self.theme_cls, tint="green" if has_tx else None)
            text_color = (
                ftheme.accent(style, "green") if has_tx
                else ftheme.inactive_control_text(style)
            )

        label = getattr(card, "_archlence_label", None)
        if label is not None:
            label.bold = is_today or is_selected
            label.text_color = text_color

    # ─── Seçili günün işlemleri ──────────────────────────────────────────────

    def _select_calendar_day(self, date_obj):
        """Bir gün hücresine dokunulduğunda o günün işlemlerini yükler.

        PERFORMANS SÖZLEŞMESİ (v0.0.1'de düzeltildi): bu fonksiyon hızlı ve
        tekrarlı dokunuşlara dayanmak ZORUNDA. Eski hâli her dokunuşta iki
        pahalı iş yapıyordu ve ikisi de dokunuş sayısıyla doğrusal büyüyordu:

          1. `_render_calendar_month()` ile 42 hücrelik ızgaranın TAMAMINI
             (her biri yeni MDCard + MDLabel + tema + dokunma bağlaması)
             UI thread'inde senkron yeniden kuruyordu — üstelik ay sorgusunu
             da tekrar çalıştırarak.
          2. Her dokunuşta SINIRSIZ yeni `threading.Thread` açıp her birinde
             ayrı bir SQLite bağlantısı kuruyordu.

        Sonuç: hızlı tıklamada arayüz kilitleniyor ve eşzamanlı bağlantı
        yığılması uygulamayı çökertebiliyordu (kullanıcı raporu, Windows).

        Şimdi: (1) yalnızca ETKİLENEN iki hücre yeniden boyanır, (2) DB okuması
        debounce edilir — art arda dokunuşlarda yalnız SONUNCUSU thread açar.
        """
        previous = self._calendar_selected_date
        self._calendar_selected_date = date_obj

        # Seçim vurgusu: ızgarayı yeniden kurmadan, yalnız eski ve yeni hücre.
        cells = getattr(self, "_calendar_day_cells", None) or {}
        if previous is not None and previous != date_obj:
            old_cell = cells.get(previous)
            if old_cell is not None:
                self._style_calendar_day_cell(old_cell, False)
        new_cell = cells.get(date_obj)
        if new_cell is not None:
            self._style_calendar_day_cell(new_cell, True)

        self._calendar_selected_label.text = _t(
            f"{date_obj.strftime('%d.%m.%Y')} işlemleri yükleniyor..."
        )
        self._calendar_tx_container.clear_widgets()

        generation = getattr(self, "_calendar_generation", 0) + 1
        self._calendar_generation = generation

        def work():
            from services.calendar_service import get_day_transactions
            try:
                items = get_day_transactions(date_obj)
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Takvim gün verisi okunamadı")
                items = None

            def apply(_dt):
                if generation != getattr(self, "_calendar_generation", 0):
                    return
                self._apply_calendar_day(date_obj, items)

            Clock.schedule_once(apply, 0)

        # Debounce: bekleyen okuma varsa iptal et. Aynı kalıp bu codebase'de
        # zaten kullanılıyor (asset_mixin BIST/kripto araması, budget_mixin
        # kategori araması); takvime uygulanmamıştı.
        pending = getattr(self, "_calendar_load_event", None)
        if pending is not None:
            pending.cancel()

        def launch(_dt):
            self._calendar_load_event = None
            if generation != getattr(self, "_calendar_generation", 0):
                return  # bu istek eskidi, thread'i hiç açma
            threading.Thread(target=work, daemon=True).start()

        self._calendar_load_event = Clock.schedule_once(launch, 0.12)

    def _apply_calendar_day(self, date_obj, items):
        if items is None:
            self._calendar_selected_label.text = _t(
                f"{date_obj.strftime('%d.%m.%Y')}: işlemler okunamadı."
            )
            return

        if not items:
            self._calendar_selected_label.text = _t(
                f"{date_obj.strftime('%d.%m.%Y')}: işlem yok."
            )
            return

        self._calendar_selected_label.text = _t(
            f"{date_obj.strftime('%d.%m.%Y')} — {len(items)} işlem"
        )
        for item in items:
            self._calendar_tx_container.add_widget(
                self._build_calendar_transaction_row(item)
            )

    def _build_calendar_transaction_row(self, item):
        row = MDBoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint_y=None, height=dp(32),
        )
        row.add_widget(MDLabel(
            text=_t(f"{item['time']}  {_t(item['category'])}"),
            font_style="Caption",
        ))
        is_income = item["type"] in ("income", "Gelir")
        sign = "+" if is_income else "-"
        color = ftheme.accent(self.theme_cls.theme_style, "green" if is_income else "red")
        row.add_widget(MDLabel(
            text=f"{sign} {_fmt(item['amount'])}",
            font_style="Caption",
            halign="right",
            size_hint_x=None,
            width=dp(110),
            theme_text_color="Custom",
            text_color=color,
        ))
        return row
