"""
Finora KivyMD Application - Main Entry Point
"""

# =========================================================================
# 1. STANDARD LIBRARY IMPORTS
# =========================================================================
import os
import sys
import csv
import math
import logging
import datetime
import faulthandler
import traceback as _traceback

# =========================================================================
# 2. CRASH REPORTING & EARLY CONFIGURATION
# =========================================================================
# Crash reporting: Kivy'nin stderr yakalamasını susturduğu için çökmelerin loglanması
_CRASH_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
_crash_log_file = open(_CRASH_LOG_PATH, "a", encoding="utf-8")
faulthandler.enable(file=_crash_log_file)

def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    """Yakalanmamış Python istisnalarını crash.log'a zaman damgasıyla yazar."""
    try:
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n===== Unhandled exception at {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            _traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _log_unhandled_exception

# Configure Kivy window setup (for headless / environments without SDL2)
if not os.environ.get("KIVY_NO_ARGS"):
    os.environ["KIVY_NO_ARGS"] = "1"
if not os.environ.get("KIVY_WINDOW"):
    os.environ["KIVY_WINDOW"] = "mock" if not os.environ.get("DISPLAY") else "sdl2"

if os.environ.get("KIVY_WINDOW") == "mock":
    os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
    os.environ.setdefault("KIVY_DPI", "96")

# =========================================================================
# 3. KIVY / KIVYMD IMPORTS
# =========================================================================
from kivy.config import Config
Config.set('kivy', 'log_level', 'error') # Only log errors
Config.set('kivy', 'log_maxfiles', 2)    # Keep only 2 log files

from kivy.metrics import dp
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.storage.jsonstore import JsonStore
from kivy.properties import StringProperty, NumericProperty, ColorProperty, BooleanProperty

from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView

# Graceful Window Mocking
try:
    from kivy.core.window import Window as _KivyWindow
    from kivy.core.window import Window
except BaseException:
    _KivyWindow = None
    class Window(object):
        size = (800, 600)
        @staticmethod
        def bind(*args, **kwargs): return None
        @staticmethod
        def unbind(*args, **kwargs): return None

# Graceful KivyMD Mocking
try:
    from kivymd.app import MDApp
    from kivymd.toast import toast
    from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
    from kivymd.uix.dialog import MDDialog
    from kivymd.uix.menu import MDDropdownMenu
    from kivymd.uix.textfield import MDTextField
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.gridlayout import MDGridLayout
    from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
    from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget, TwoLineAvatarIconListItem, IRightBodyTouch
    from kivymd.uix.label import MDLabel, MDIcon
    from kivymd.uix.screen import MDScreen
except BaseException as exc:
    from kivy.app import App
    import warnings
    warnings.warn(f"KivyMD import failed; using fallback UI classes: {exc}")

    class MDApp(App):
        def run(self):
            print("KivyMD is unavailable in this environment; skipping GUI startup.")
            return None

    class MDRaisedButton(Widget): pass
    class MDFlatButton(Widget): pass
    class MDIconButton(Widget): pass
    class MDTextField(Widget): pass
    class MDBoxLayout(BoxLayout): pass
    class MDGridLayout(GridLayout): pass
    class MDSegmentedControl(Widget): pass
    class MDSegmentedControlItem(Widget): pass
    class TwoLineIconListItem(Widget): pass
    class IconLeftWidget(Widget): pass
    class MDLabel(Widget): pass
    class MDIcon(Widget): pass
    class TwoLineAvatarIconListItem(Widget): pass
    class IRightBodyTouch(object): pass
    class MDScreen(Widget): pass

    class MDDialog(object):
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
        def open(self, *args, **kwargs): return None
        def dismiss(self, *args, **kwargs): return None

    class MDDropdownMenu(object):
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
        def open(self, *args, **kwargs): return None
        def dismiss(self, *args, **kwargs): return None

    def toast(*args, **kwargs): return None

# =========================================================================
# 4. LOCAL MODULE IMPORTS
# =========================================================================
from utils.crypto import encrypt, decrypt
from database.init_db import initialize_database
from database.db import get_connection, ACCOUNT, record_balance_event
from services.transaction_service import TransactionService
from services.queries import CategoryService

from ui.charts import CurvedTrendChart, HorizontalBarChart, LiquidWaveWidget, PieChart, DashboardChartManager, ConfettiWidget
from ui.components import CategorySettingItem, RightButtonsContainer, BudgetListItem, LegendItem, LegendWidget
from ui.theme import (
    apply_premium_theme, apply_standard_theme, refresh_card_theme,
    apply_dark_surface_tokens, restyle_text_fields, _refresh,
)
from screens.admin_screen import AdminScreen

from mixins.asset_mixin import AssetMixin
from mixins.debt_mixin import DebtMixin
from mixins.calculator_mixin import CalculatorMixin
from mixins.transaction_mixin import TransactionMixin
from mixins.budget_mixin import BudgetMixin
from mixins.savings_mixin import SavingsMixin
from mixins.recurring_mixin import RecurringMixin
from mixins.migration_mixin import MigrationMixin
from mixins.account_mixin import AccountMixin
from mixins.insights_mixin import InsightsMixin
from mixins.history_mixin import HistoryMixin
from security.security_service import SecurityService
from services.history_service import write_daily_snapshot

# =========================================================================
# 5. CONSTANTS
# =========================================================================
SECRET_KEY = 'finora_secure_2026'
ADMIN_HASH = "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"


# =========================================================================
# 6. MAIN APPLICATION CLASS
# =========================================================================
class FinoraApp(
    MDApp, AssetMixin, DebtMixin, CalculatorMixin, TransactionMixin, 
    BudgetMixin, SavingsMixin, RecurringMixin, MigrationMixin, AccountMixin, 
    InsightsMixin, HistoryMixin
):
    
    # -------------------------------------------------------------------------
    # Properties & State
    # -------------------------------------------------------------------------
    dialog = None
    selected_type = "income"
    active_category_type = StringProperty("income")
    selected_category = "Kategori Seç" 
    home_filter = "Bugün"
    home_circle_color = ColorProperty((0.5, 0.5, 0.5, 0.2))
    savings_goals = []
    theme_name = StringProperty("standard")
    
    _wealth_visible = True
    _liquid_balance_cache = 0.0
    _assets_cache = []

    # -------------------------------------------------------------------------
    # Lifecycle & Initialization
    # -------------------------------------------------------------------------
    def build(self):
        initialize_database()
        self.store = JsonStore('savings_goals.json')
        if self.store.exists('goals'):
            self.savings_goals = self.store.get('goals')['data']
            
        # KivyMD 1.2'nin tema renk animasyonları hızlı geçişlerde üst üste
        # binerek bazı label'ları eski zemin rengine/şeffaflığa bırakabiliyor.
        # Uygulamanın kendi geçişi yeterli; metin renkleri atomik güncellenir.
        self.theme_cls.theme_style_switch_animation = False
        self.theme_cls.theme_style = "Light"
        self.config_store = JsonStore('finora_config.json')
        
        pref = "standard"
        if self.config_store.exists('theme'):
            pref = self.config_store.get('theme').get('name', 'standard')
            
        self.apply_theme(pref, persist=False)
        return Builder.load_file("ui/dashboard.kv")

    def on_start(self):
        self._normalize_card_shadows()
        
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("peewee").setLevel(logging.CRITICAL)
        
        self.purge_logs()
        self.vacuum_database()
        self.write_daily_balance_snapshot()
        self.setup_dynamic_months()
        self.safe_refresh_charts()
        self.load_recent_transactions("Günlük")
        self.generate_financial_advice()
        self.load_active_debts()
        self.load_active_assets()
        self.load_asset_history()
        self.process_due_auto_deductions()

    # -------------------------------------------------------------------------
    # Theming & Visuals
    # -------------------------------------------------------------------------
    def apply_theme(self, theme_name, persist=True):
        theme_name = "premium" if theme_name == "premium" else "standard"
        self.theme_name = theme_name
        
        if theme_name == "premium":
            apply_premium_theme(self.theme_cls)
        else:
            apply_standard_theme(self.theme_cls)

        self._normalize_card_shadows()

        if persist:
            try:
                if not hasattr(self, 'config_store'):
                    self.config_store = JsonStore('finora_config.json')
                self.config_store.put('theme', name=theme_name)
            except Exception as e:
                print("Tema tercihi kaydedilemedi:", e)

    def toggle_theme(self, is_active):
        # KV'de giriş ve uygulama ayarlarında aynı theme_style'a bağlı birden
        # fazla switch var. theme_style değişince bu switch'lerin on_active
        # olayları da çalışır; bunlar kullanıcıdan gelen yeni bir istek değildir.
        if getattr(self, "_applying_theme_style", False):
            return

        desired_style = "Dark" if is_active else "Light"
        pending = getattr(self, "_pending_theme_switch", None)
        if pending is not None:
            pending.cancel()
            self._pending_theme_switch = None
        if self.theme_cls.theme_style == desired_style:
            return

        def _switch_theme(dt):
            self._pending_theme_switch = None
            if self.theme_cls.theme_style == desired_style:
                return
            apply_dark_surface_tokens()
            self._applying_theme_style = True
            try:
                self.theme_cls.theme_style = desired_style
                Clock.schedule_once(self._after_theme_switch, 0)
            finally:
                self._applying_theme_style = False
        # Switch'in kendi kısa animasyonu bitsin; yeni bir kullanıcı seçimi
        # gelirse yukarıdaki iptal sayesinde eski seçim sonradan uygulanmaz.
        self._pending_theme_switch = Clock.schedule_once(_switch_theme, 0.12)

    def _after_theme_switch(self, *args):
        try:
            _refresh(self.theme_cls)
        except Exception:
            pass
        self._normalize_card_shadows()
        self._resync_text_fields()
        # Premium kartlar çok katmanlı canvas + adaptive label içeriyor.
        # KivyMD 1.2 bunları Dark -> Light dönüşünde eski stencil/canvas
        # durumuyla bırakabiliyor; sonuç metin dokusu tam olsa bile yalnız ilk
        # karakterin görünmesi. Kart ağacını güncel veriden yeniden kurmak hem
        # güvenli hem deterministik (veritabanında yazma yapmaz).
        # Dinamik oluşturulmuş MDLabel/MDIcon örnekleri KV bağlaması taşımayabilir.
        # Aktif theme_text_color rolünü yeniden uygulatmak görünmez metinleri
        # önler; Custom renkler olduğu gibi korunur.
        for widget in self._all_widgets():
            if isinstance(widget, MDLabel):
                try:
                    widget.on_theme_text_color(widget, widget.theme_text_color)
                except Exception:
                    pass
        # Kivy 2.3 / KivyMD 1.2'de özellikle Custom renkli, adaptive boyutlu
        # label'ların font texture'ı Dark -> Light dönüşünde bazen tek karakter
        # genişliğinde kalıyor. Renk geçişi tamamlandıktan sonraki frame'de
        # texture'ları yeniden üretmek metnin kırpılmasını/kaybolmasını önler.
        Clock.schedule_once(self._rebuild_after_theme_layout, 0.2)

    def _rebuild_after_theme_layout(self, *args):
        """Tema ve navigation yerleşimi oturduktan sonra dinamik kartları kur."""
        if hasattr(self, "render_accounts"):
            try:
                self.render_accounts()
            except Exception as exc:
                print("Tema sonrası kartlar yenilenemedi:", exc)
        self._normalize_card_shadows()
        Clock.schedule_once(self._refresh_text_textures, 0.05)

    def _refresh_text_textures(self, *args):
        for widget in self._all_widgets():
            if isinstance(widget, MDLabel):
                try:
                    # Bu metot tema değişiminden 150 ms sonra çağrılır; o anda
                    # FloatLayout/ScrollView ölçüleri sabittir. Senkron yenileme
                    # hem font dokusunu hem ona bağlı canvas Rectangle'ını aynı
                    # ölçüye getirir (yalnız _trigger_texture Rectangle'ı eski
                    # genişlikte bırakabiliyor).
                    widget.texture_update()
                    widget.canvas.ask_update()
                except Exception:
                    pass

    def _normalize_card_shadows(self, *args):
        if not self.root:
            return
        
        from kivymd.uix.card import MDCard
        for widget in self._all_widgets():
            if isinstance(widget, MDCard):
                try:
                    if hasattr(widget, "_finora_tint"):
                        refresh_card_theme(widget, self.theme_cls)
                    widget.elevation = 0
                    if hasattr(widget, 'shadow_softness'):
                        widget.shadow_softness = 0
                    if hasattr(widget, 'shadow_color'):
                        widget.shadow_color = (0, 0, 0, 0)
                except Exception:
                    pass

    def _resync_text_fields(self):
        if not self.root:
            return
        # set_default_colors(), Finora'nın kontrast renklerini KivyMD
        # varsayılanlarıyla ezebiliyordu. Ortak tema kiti açık diyaloglar dahil
        # tüm alanlara doğru açık/koyu renkleri uygular.
        restyle_text_fields(self.root, self.theme_cls)
        for window_child in list(Window.children):
            if window_child is not self.root:
                restyle_text_fields(window_child, self.theme_cls)

    def _all_widgets(self):
        from kivy.uix.screenmanager import ScreenManager
        
        seen = set()
        stack = [self.root] + list(Window.children)
        while stack:
            widget = stack.pop()
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            yield widget
            stack.extend(widget.children)
            if isinstance(widget, ScreenManager):
                stack.extend(widget.screens)

    # -------------------------------------------------------------------------
    # System Maintenance & Helpers
    # -------------------------------------------------------------------------
    def purge_logs(self):
        import glob
        log_dir = os.path.expanduser('~/.kivy/logs')
        if not os.path.exists(log_dir):
            return
        
        total_size = sum(os.path.getsize(os.path.join(log_dir, f)) 
                         for f in os.listdir(log_dir) 
                         if os.path.isfile(os.path.join(log_dir, f)))
        if total_size > 5 * 1024 * 1024:
            for f in glob.glob(os.path.join(log_dir, "*.txt")):
                try:
                    os.remove(f)
                except Exception:
                    pass
            print("Purged Kivy logs due to size > 5MB")

    def vacuum_database(self):
        try:
            conn = get_connection()
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            print("Database VACUUM completed.")
        except Exception as e:
            print(f"VACUUM failed: {e}")

    def write_daily_balance_snapshot(self):
        try:
            write_daily_snapshot()
        except Exception as e:
            print("Günlük bakiye snapshot'ı yazılamadı:", e)

    # -------------------------------------------------------------------------
    # Financial Engine (ODE)
    # -------------------------------------------------------------------------
    @staticmethod
    def _rk4_wealth_projection(W0, daily_income, daily_expense, days=30, r=0.0001):
        I = daily_income
        E = daily_expense
        dt = 1.0

        def f(t, W):
            return r * W + I - E

        W, t = W0, 0.0
        for _ in range(days):
            k1 = f(t,        W)
            k2 = f(t + dt/2, W + dt/2 * k1)
            k3 = f(t + dt/2, W + dt/2 * k2)
            k4 = f(t + dt,   W + dt   * k3)
            W  = W + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
            t += dt
        return W

    # -------------------------------------------------------------------------
    # Metrics & Dashboard Updates
    # -------------------------------------------------------------------------
    def update_metrics_and_goals(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.amount, t.type, IFNULL(c.importance, 'extra') 
            FROM transactions t
            LEFT JOIN categories c ON t.category = c.name
        """)
        rows = cursor.fetchall()
        conn.close()

        ana_gelir = ek_gelir = temel_gider = ekstra_gider = 0.0
        
        for amount, t_type, importance in rows:
            try:
                decrypted_amount = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                decrypted_amount = 0.0
                
            if t_type in ("income", "Gelir"):
                if importance == "main": ana_gelir += decrypted_amount
                else: ek_gelir += decrypted_amount
            elif t_type in ("expense", "Gider"):
                if importance == "main": temel_gider += decrypted_amount
                else: ekstra_gider += decrypted_amount

        total_income = ana_gelir + ek_gelir
        total_expense = temel_gider + ekstra_gider
        total_balance = total_income - total_expense

        filter_text = getattr(self, "home_filter", "Bugün")

        period_income = period_expense = period_net = 0.0
        try:
            conn2 = get_connection()
            cursor2 = conn2.cursor()
            
            if filter_text == "1 Hafta":
                date_cond = ">= date('now', '-7 days', 'localtime')"
            elif filter_text == "1 Ay":
                date_cond = ">= date('now', '-1 month', 'localtime')"
            elif filter_text == "1 Yıl":
                date_cond = ">= date('now', '-1 year', 'localtime')"
            elif filter_text == "Hayat Boyu":
                date_cond = "> '2000-01-01'"
            else:
                date_cond = "= date('now', 'localtime')"

            cursor2.execute(f"SELECT amount, type FROM transactions WHERE date(transaction_date) {date_cond}")
            for t_amt, t_typ in cursor2.fetchall():
                try:
                    val = float(decrypt(str(t_amt), SECRET_KEY))
                except Exception:
                    val = 0.0
                    
                if t_typ in ("income", "Gelir"):
                    period_income += val
                    period_net += val
                elif t_typ in ("expense", "Gider"):
                    period_expense += val
                    period_net -= val
            conn2.close()
        except Exception:
            pass

        if self.root:
            try:
                def _fmt(v): return f"₺{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                self.root.ids.period_income_label.text  = _fmt(period_income)
                self.root.ids.period_expense_label.text = _fmt(period_expense)
                
                net_lbl = self.root.ids.period_net_label
                net_lbl.text = ("+ " if period_net >= 0 else "- ") + _fmt(abs(period_net))
                if period_net > 0: net_lbl.text_color = (0.06, 0.55, 0.18, 1)
                elif period_net < 0: net_lbl.text_color = (0.78, 0.1, 0.1, 1)
                else: net_lbl.text_color = (0.5, 0.5, 0.5, 1)

                formatted_balance = f"{total_balance:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
                self.root.ids.home_total_balance.text = formatted_balance
                self.root.ids.total_card_amount.text  = formatted_balance

                try:
                    warning_row = self.root.ids.negative_balance_warning
                    if total_balance < 0:
                        warning_row.height = "22dp"
                        warning_row.opacity = 1
                    else:
                        warning_row.height = 0
                        warning_row.opacity = 0
                except Exception:
                    pass

                self.root.ids.home_change_title.text = f"Değişim ({filter_text})"
                self.root.ids.today_card_title.text  = filter_text

                prefix = "+" if period_net > 0 else ""
                formatted_period = f"{period_net:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
                self.root.ids.today_card_amount.text = f"{prefix}{formatted_period}"

                if total_balance > 0:   self.home_circle_color = (0.18, 0.8, 0.25, 1)
                elif total_balance < 0: self.home_circle_color = (0.9,  0.2,  0.2,  1)
                else:                   self.home_circle_color = (0.5,  0.5,  0.5,  0.2)

                if hasattr(self.root.ids, 'balance_circle'):
                    self.root.ids.balance_circle.canvas.ask_update()

                try:
                    self._liquid_balance_cache = total_balance
                    if not hasattr(self, '_assets_cache') or not self._assets_cache:
                        self._update_wealth_label(total_balance, None)
                except Exception:
                    pass

                self.render_savings_goals(total_balance)

            except Exception:
                pass
                
            try:
                conn_pred = get_connection()
                cursor_pred = conn_pred.cursor()
                cursor_pred.execute("""
                    SELECT type, amount 
                    FROM transactions
                    WHERE date(transaction_date) >= date('now', '-30 days', 'localtime')
                """)
                rows = cursor_pred.fetchall()
                conn_pred.close()

                inc_30 = exp_30 = 0.0
                for t_type, amount in rows:
                    try:
                        val = float(decrypt(str(amount), SECRET_KEY))
                    except Exception:
                        val = 0.0
                    if t_type in ('income', 'Gelir'): inc_30 += val
                    elif t_type in ('expense', 'Gider'): exp_30 += val

                daily_income  = inc_30 / 30.0
                daily_expense = exp_30 / 30.0
                W0 = total_balance

                projected_wealth = self._rk4_wealth_projection(
                    W0=W0,
                    daily_income=daily_income,
                    daily_expense=daily_expense,
                    days=30,
                    r=0.0001,
                )

                def _fmt(val):
                    return f"{val:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

                net_change = projected_wealth - W0

                ode_label = (
                    f"ODE Simülasyonu: Mevcut ivme ve %3,65 yıllık parametre ile "
                    f"30 gün sonraki beklenen varlık: {_fmt(projected_wealth)}"
                )

                if self.root:
                    pred_icon = self.root.ids.prediction_icon
                    pred_text = self.root.ids.prediction_text

                    if projected_wealth < 0:
                        pred_icon.icon  = "alert-circle-outline"
                        pred_icon.text_color = (0.9, 0.2, 0.2, 1)
                        pred_text.text = f"{ode_label}\nDikkat: ODE modeli varlığınızın eksiye düşeceğini gösteriyor. Harcamalarınızı acilen gözden geçirin!"
                    elif net_change < 0:
                        pred_icon.icon  = "trending-down"
                        pred_icon.text_color = (0.95, 0.75, 0.1, 1)
                        pred_text.text = f"{ode_label}\nGider ivmeniz gelirinizi aşıyor; varlığınız {_fmt(abs(net_change))} azalabilir."
                    else:
                        pred_icon.icon  = "trending-up"
                        pred_icon.text_color = (0.18, 0.8, 0.25, 1)
                        pred_text.text = f"{ode_label}\nMevcut gelir-gider dengesiyle varlığınız {_fmt(net_change)} artış gösterebilir."

            except Exception:
                pass

        if self.root and 'metric_val_income' in self.root.ids:
            self.root.ids.metric_val_income.text = f"{total_income:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            self.root.ids.metric_val_expense.text = f"{total_expense:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

            if total_income > 0:
                savings_rate = ((total_income - total_expense) / total_income) * 100
                self.root.ids.metric_val_savings.text = f"%{savings_rate:.1f}".replace(".", ",")
            else:
                self.root.ids.metric_val_savings.text = "%0,0"

            if 'metric_val_trend' in self.root.ids:
                aim_text = f"{total_income:,.0f} ₺".replace(",", ".") if total_income > 0 else "Veri Yok"
                self.root.ids.metric_val_trend.text = aim_text

            cards = [
                self.root.ids.metric_card_income,
                self.root.ids.metric_card_expense,
                self.root.ids.metric_card_savings,
                self.root.ids.metric_card_trend
            ]

            for i, card in enumerate(cards):
                card.opacity = 0
                def animate_card(dt, c=card):
                    orig_y = c.y
                    c.y = orig_y - dp(40)
                    Animation(opacity=1, y=orig_y, d=0.6, t='out_cubic').start(c)
                Clock.schedule_once(animate_card, 0.1 + (i * 0.15))

    def _fmt_tr(self, value: float) -> str:
        return f"₺{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _update_wealth_label(self, total_wealth: float, today_pnl):
        try:
            lbl  = self.root.ids.wealth_amount_label
            pnl  = self.root.ids.wealth_daily_pnl_label
            eye  = self.root.ids.wealth_eye_btn

            if not self._wealth_visible:
                lbl.text = "₺***.***,**"
                pnl.text = ""
                eye.icon = "eye-off-outline"
                return

            eye.icon   = "eye-outline"
            lbl.text   = self._fmt_tr(total_wealth)

            if today_pnl is None:
                pnl.text       = "Varlık fiyatları hesaplanıyor..."
                pnl.text_color = (0.5, 0.5, 0.5, 1)
            else:
                pct = (today_pnl / (total_wealth - today_pnl) * 100) if (total_wealth - today_pnl) != 0 else 0.0
                sign = "+" if today_pnl >= 0 else "-"
                c_sign = "+" if pct >= 0 else "-"
                pnl.text = f"{sign}{self._fmt_tr(abs(today_pnl))} ({c_sign}{abs(pct):.2f}%) Bugün"
                
                if today_pnl > 0: pnl.text_color = (0.06, 0.86, 0.29, 1)
                elif today_pnl < 0: pnl.text_color = (0.95, 0.22, 0.22, 1)
                else: pnl.text_color = (0.5, 0.5, 0.5, 1)
        except Exception:
            pass

    def toggle_wealth_visibility(self):
        self._wealth_visible = not self._wealth_visible
        self.update_wealth_card(self._assets_cache)

    def update_wealth_card(self, enriched_assets):
        liquid_cash = getattr(self, '_liquid_balance_cache', 0.0)

        portfolio_live = sum(a['total_value'] for a in enriched_assets if a.get('total_value') is not None)
        total_wealth = liquid_cash + portfolio_live

        asset_pnl = sum(a['pnl_amount'] for a in enriched_assets if a.get('pnl_amount') is not None)
        today_liquid_delta = 0.0
        
        try:
            conn_t = get_connection()
            cur_t  = conn_t.cursor()
            cur_t.execute(
                "SELECT amount, type FROM transactions "
                "WHERE date(transaction_date) = date('now', 'localtime')"
            )
            for t_amt, t_typ in cur_t.fetchall():
                try:
                    val = float(decrypt(str(t_amt), SECRET_KEY))
                except Exception:
                    val = 0.0
                if t_typ in ("income", "Gelir"): today_liquid_delta += val
                elif t_typ in ("expense", "Gider"): today_liquid_delta -= val
            conn_t.close()
        except Exception:
            pass

        today_pnl = asset_pnl + today_liquid_delta
        self._update_wealth_label(total_wealth, today_pnl if enriched_assets else None)

    # -------------------------------------------------------------------------
    # Charting & Calculations
    # -------------------------------------------------------------------------
    def safe_refresh_charts(self):
        self.refresh_dashboard_data()

    def calculate_monthly_change_rate(self):
        now = datetime.datetime.now().date()
        filter_text = getattr(self, "home_filter", "Bugün")

        if filter_text == "1 Hafta":
            current_start = now - datetime.timedelta(days=7)
            prev_start = current_start - datetime.timedelta(days=7)
            prev_end = current_start
        elif filter_text == "1 Ay":
            current_start = now - datetime.timedelta(days=30)
            prev_start = current_start - datetime.timedelta(days=30)
            prev_end = current_start
        elif filter_text == "1 Yıl":
            current_start = now - datetime.timedelta(days=365)
            prev_start = current_start - datetime.timedelta(days=365)
            prev_end = current_start
        else:
            current_start = now
            prev_start = now - datetime.timedelta(days=1)
            prev_end = now

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type, transaction_date FROM transactions")
        rows = cursor.fetchall()
        conn.close()
        
        current_net = prev_net = 0.0
        
        for amount_enc, t_type, t_date in rows:
            if not t_date: continue
            try:
                t_dt = datetime.datetime.strptime(t_date[:10], "%Y-%m-%d").date()
                amount = float(decrypt(amount_enc, SECRET_KEY))
            except:
                continue
                
            val = amount if t_type in ('income', 'Gelir') else -amount if t_type in ('expense', 'Gider') else 0.0

            if current_start <= t_dt <= now: current_net += val
            elif prev_start <= t_dt < prev_end: prev_net += val
                
        if prev_net == 0:
            change_rate = 100.0 if current_net > 0 else -100.0 if current_net < 0 else 0.0
        else:
            change_rate = ((current_net - prev_net) / abs(prev_net)) * 100
            
        return change_rate

    def update_change_rate_ui(self):
        try:
            rate = self.calculate_monthly_change_rate()
            if self.root and 'change_rate_label' in self.root.ids:
                label = self.root.ids.change_rate_label
                if rate > 0:
                    label.text = f"+%{rate:.1f}"
                    label.text_color = (0.18, 0.8, 0.25, 1)
                elif rate < 0:
                    label.text = f"-%{abs(rate):.1f}"
                    label.text_color = (0.9, 0.2, 0.2, 1)
                else:
                    label.text = "%0.0"
                    label.text_color = (0.5, 0.5, 0.5, 1)
        except Exception as e:
            print("Error updating change rate UI:", e)

    # -------------------------------------------------------------------------
    # List & Navigation Interactions
    # -------------------------------------------------------------------------
    def change_home_filter(self, text):
        self.home_filter = text
        self.sync_filter_buttons_ui()
        self.safe_refresh_charts()
        self.load_recent_transactions()

    def sync_filter_buttons_ui(self):
        try:
            buttons = {
                "Bugün": self.root.ids.btn_filter_today,
                "1 Hafta": self.root.ids.btn_filter_week,
                "1 Ay": self.root.ids.btn_filter_month,
                "1 Yıl": self.root.ids.btn_filter_year,
                "Hayat Boyu": self.root.ids.btn_filter_lifetime,
            }
            bg_inactive = (0.9, 0.9, 0.9, 1) if self.theme_cls.theme_style == "Light" else (0.3, 0.3, 0.3, 1)
            
            for name, btn in buttons.items():
                if name == getattr(self, "home_filter", "Bugün"):
                    btn.md_bg_color = self.theme_cls.primary_color
                    btn.text_color  = (1, 1, 1, 1)
                else:
                    btn.md_bg_color = bg_inactive
                    btn.text_color  = (0.5, 0.5, 0.5, 1)
        except Exception:
            pass

    def update_sg_period(self, segment, item):
        self.sg_period = item.text

    def refresh_dashboard_data(self, list_filter=None):
        import threading
        
        try:
            self.update_metrics_and_goals()
            self.update_change_rate_ui()
            if self.root and 'chart_master_box' in self.root.ids:
                self.root.ids.chart_master_box.refresh_dashboard(getattr(self, 'home_filter', 'Bugün'))
        except Exception as e:
            print("Error updating UI metrics:", e)

        try:
            self.refresh_insights()
        except Exception as e:
            print("Error refreshing insights:", e)
                
        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")
            
        def fetch_task():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                queries = {
                    "Günlük": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) = date('now', 'localtime') ORDER BY id DESC LIMIT 15",
                    "Bugün": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) = date('now', 'localtime') ORDER BY id DESC LIMIT 15",
                    "1 Hafta": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) >= date('now', '-7 days', 'localtime') ORDER BY id DESC LIMIT 15",
                    "Haftalık": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) >= date('now', '-7 days', 'localtime') ORDER BY id DESC LIMIT 15",
                    "1 Ay": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') ORDER BY id DESC LIMIT 15",
                    "Aylık": "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') ORDER BY id DESC LIMIT 15"
                }
                
                query = queries.get(list_filter, "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions ORDER BY id DESC LIMIT 15")
                cursor.execute(query)
                transactions_raw = cursor.fetchall()
                conn.close()
                
                processed_items = []
                for t_type, category, amount_enc, desc_enc, t_date in transactions_raw:
                    try:
                        dec_amt = float(decrypt(str(amount_enc), SECRET_KEY))
                    except:
                        dec_amt = 0.0
                        
                    try:
                        dec_desc = decrypt(str(desc_enc), SECRET_KEY) if desc_enc else ""
                    except:
                        dec_desc = ""
                        
                    processed_items.append((t_type, category, dec_amt, dec_desc, t_date))
                    
                Clock.schedule_once(lambda dt: self._render_recent_transactions(processed_items), 0)
            except Exception as e:
                print("Error fetching recent transactions:", e)
                
        threading.Thread(target=fetch_task, daemon=True).start()

    def _render_recent_transactions(self, transactions):
        try:
            recent_list = self.root.ids.recent_transactions_list
            data = []
            
            icon_mapping = {
                'su': ('water', (0.13, 0.59, 0.95, 1)),                 
                'fatura': ('receipt', (0.4, 0.4, 0.4, 1)),              
                'freelance': ('laptop-account', (0.1, 0.7, 0.7, 1)),    
                'maaş': ('bank', (0.18, 0.8, 0.25, 1)),                 
                'dijital platformlar': ('youtube-tv', (0.6, 0.2, 0.8, 1)), 
                'market': ('basket', (0.95, 0.6, 0.1, 1)),              
                'kira': ('home', (0.7, 0.3, 0.3, 1)),                   
                'ulaşım': ('bus', (0.3, 0.3, 0.3, 1)),                  
                'sağlık': ('hospital-box', (0.9, 0.1, 0.1, 1)),         
                'eğitim': ('school', (0.2, 0.4, 0.8, 1)),
                'hisse/varlık': ('chart-line', (0.08, 0.72, 0.42, 1)),
            }
            
            for t_type, category, amount, decrypted_desc, t_date in transactions:
                cat_lower = category.lower() if category else ""
                icon_data = next((v for k, v in icon_mapping.items() if k in cat_lower), None)
                
                if icon_data:
                    icon_name, icon_col = icon_data
                elif category == "Varlık Alımı":
                    icon_name, icon_col = "chart-line", (0.08, 0.72, 0.42, 1)
                elif category == "Varlık Satışı":
                    icon_name, icon_col = "cash-plus", (0.18, 0.8, 0.25, 1)
                elif t_type == "income":
                    icon_name, icon_col = "cash-plus", (0.18, 0.8, 0.25, 1)
                else:
                    icon_name, icon_col = "cart-outline", (0.9, 0.2, 0.2, 1)

                if category == "Varlık Alımı":
                    amount_text = f"[color=#0277BD]- ₺{amount:,.2f} Yatırım[/color]"
                elif category == "Varlık Satışı":
                    amount_text = f"[color=#2E7D32]+ ₺{amount:,.2f} Satış[/color]"
                elif t_type == "income":
                    amount_text = f"[color=#2E7D32]+ ₺{amount:,.2f}[/color]"
                else:
                    amount_text = f"[color=#D32F2F]- ₺{amount:,.2f}[/color]"

                data.append({
                    "text": category,
                    "secondary_text": f"{t_date[:10]} | {amount_text}",
                    "icon_source": "",
                    "icon_name": icon_name,
                    "icon_color": list(icon_col),
                })

            recent_list.data = data
        except Exception as e:
            print("Error rendering recent UI:", e)

    # -------------------------------------------------------------------------
    # Authentication & Profile
    # -------------------------------------------------------------------------
    def check_login(self):
        username = self.root.ids.username_input.text
        password = self.root.ids.password_input.text

        if username == "admin" and password == "admin_secret":
            self._handle_successful_login("admin")
        elif username == "admin" and SecurityService.verify_password(password, ADMIN_HASH):
            self._handle_successful_login("home")
        else:
            self._handle_failed_login()

    def _handle_successful_login(self, target_screen):
        self.root.ids.login_error_label.text = ""
        self.root.ids.username_input.text = ""
        self.root.ids.password_input.text = ""
        self.root.ids.screen_manager.current = target_screen

    def _handle_failed_login(self):
        self.root.ids.login_error_label.text = "Hatalı kullanıcı adı veya şifre!"
        
        pwd_container = self.root.ids.password_container
        usr_input = self.root.ids.username_input
        
        Animation.cancel_all(pwd_container)
        Animation.cancel_all(usr_input)
        
        if not hasattr(pwd_container, 'anim_original_x'):
            pwd_container.anim_original_x = pwd_container.x
        if not hasattr(usr_input, 'anim_original_x'):
            usr_input.anim_original_x = usr_input.x
            
        def _shake_anim(orig_x):
            return (
                Animation(x=orig_x + 10, duration=0.05) +
                Animation(x=orig_x - 10, duration=0.05) +
                Animation(x=orig_x + 10, duration=0.05) +
                Animation(x=orig_x - 10, duration=0.05) +
                Animation(x=orig_x, duration=0.05)
            )

        anim_pwd = _shake_anim(pwd_container.anim_original_x)
        anim_usr = _shake_anim(usr_input.anim_original_x)
        
        def clear_original_x(*args):
            if hasattr(pwd_container, 'anim_original_x'): del pwd_container.anim_original_x
            if hasattr(usr_input, 'anim_original_x'): del usr_input.anim_original_x
                
        anim_pwd.bind(on_complete=clear_original_x)
        anim_pwd.start(pwd_container)
        anim_usr.start(usr_input)

    def admin_logout(self):
        if self.root:
            self.root.ids.username_input.text = ""
            self.root.ids.password_input.text = ""
            self.root.ids.screen_manager.current = "login"

    # -------------------------------------------------------------------------
    # Categories & AI Insights
    # -------------------------------------------------------------------------
    def load_categories(self, cat_type=None):
        if cat_type:
            self.active_category_type = cat_type
            
        settings_list = self.root.ids.settings_list
        settings_list.clear_widgets()
        
        def _populate_categories(dt):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name, type, importance FROM categories WHERE type = ? ORDER BY name", (self.active_category_type,))
            categories = cursor.fetchall()
            conn.close()

            for cat_name, cat_type_val, cat_imp in categories:
                item = CategorySettingItem(cat_name=cat_name, cat_type=cat_type_val, cat_importance=cat_imp)
                settings_list.add_widget(item)
                
        Clock.schedule_once(_populate_categories, 0.1)

    def update_category_importance(self, category_name, is_active):
        new_importance = "main" if is_active else "extra"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET importance = ? WHERE name = ?", (new_importance, category_name))
        conn.commit()
        conn.close()
        self.safe_refresh_charts()

    def generate_financial_advice(self, *args):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT category, amount FROM transactions WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime')")
        expense_rows_this_month = cursor.fetchall()
        
        cat_sums, this_month_exp = {}, 0.0
        for cat, amount in expense_rows_this_month:
            try: val = float(decrypt(str(amount), SECRET_KEY))
            except: val = 0.0
            cat_sums[cat] = cat_sums.get(cat, 0.0) + val
            this_month_exp += val
            
        highest_cat_name = max(cat_sums, key=cat_sums.get) if cat_sums else "Yok"
        
        cursor.execute("SELECT amount FROM transactions WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', '-1 month', 'localtime')")
        last_month_exp = sum(float(decrypt(str(amt[0]), SECRET_KEY)) for amt in cursor.fetchall() if amt[0])
        
        cursor.execute("SELECT amount FROM transactions WHERE type='income' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime')")
        this_month_inc = sum(float(decrypt(str(amt[0]), SECRET_KEY)) for amt in cursor.fetchall() if amt[0])
        conn.close()
        
        if last_month_exp > 0:
            change_percent = ((this_month_exp - last_month_exp) / last_month_exp) * 100
            change_text = f"%{change_percent:.1f} arttı" if change_percent > 0 else f"%{abs(change_percent):.1f} azaldı"
        else:
            change_text = "karşılaştırılacak veri yok"
            
        savings_rate = ((this_month_inc - this_month_exp) / this_month_inc) * 100 if this_month_inc > 0 else 0

        advice_text = (
            f"Bu ay harcamalarınız geçen döneme kıyasla {change_text}.\n"
            f"En çok harcama yapılan alan: {highest_cat_name}.\n"
            f"Bu ayki net tasarruf oranınız: %{savings_rate:.1f}. Harika birikim dönemi!"
        )

        try:
            app = MDApp.get_running_app()
            if app and app.root and 'prediction_text' in app.root.ids:
                app.root.ids.prediction_text.text = advice_text
                app.root.ids.prediction_icon.icon = "robot-outline"
                app.root.ids.prediction_icon.text_color = (0.13, 0.59, 0.95, 1)
        except Exception:
            pass
        
        if 'advice_label' in self.root.ids:
            self.root.ids.advice_label.text = advice_text
            self.root.ids.advice_icon.icon = "robot-outline"
            self.root.ids.advice_icon.text_color = (0.13, 0.59, 0.95, 1)

    # -------------------------------------------------------------------------
    # Dialogs & Reset Functionality
    # -------------------------------------------------------------------------
    def contact_us(self):
        import webbrowser
        
        def send_email(x):
            webbrowser.open("mailto:support@finora.com")
            if hasattr(self, 'contact_dialog'):
                self.contact_dialog.dismiss()

        self.contact_dialog = MDDialog(
            title="Bize Ulaşın",
            text="Her türlü soru, öneri ve destek için bize aşağıdaki e-posta adresinden ulaşabilirsiniz:\n\n[b]support@finora.com[/b]",
            buttons=[
                MDFlatButton(text="KAPAT", on_release=lambda x: self.contact_dialog.dismiss()),
                MDRaisedButton(text="E-POSTA GÖNDER", md_bg_color=self.theme_cls.primary_color, on_release=send_email),
            ],
        )
        if hasattr(self.contact_dialog, 'ids') and 'text' in self.contact_dialog.ids:
            self.contact_dialog.ids.text.markup = True
        self.contact_dialog.open()

    def confirm_delete_all_data(self):
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height="60dp")
        self.reset_input = MDTextField(hint_text="SİL yazınız", helper_text="Onaylamak için büyük harflerle SİL yazın", helper_text_mode="persistent")
        content.add_widget(self.reset_input)

        self.reset_dialog = MDDialog(
            title="Tüm Verileri Sıfırla",
            text="Tüm işlemler, varlıklar, borçlar ve hedefler kalıcı olarak silinecektir. Emin misiniz?",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.reset_dialog.dismiss()),
                MDRaisedButton(text="SİL", md_bg_color=(1, 0.2, 0.2, 1), on_release=self.delete_all_data),
            ],
        )
        self.reset_dialog.open()

    def delete_all_data(self, *args):
        if hasattr(self, 'reset_input') and self.reset_input.text.strip() != "SİL":
            toast("Silme işlemi iptal edildi. Onay için SİL yazmalısınız.")
            return
        try:
            if hasattr(self, 'store'):
                self.store.clear()
            self.savings_goals = []
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions")
            cursor.execute("DELETE FROM active_assets")
            cursor.execute("DELETE FROM active_debts")
            cursor.execute("DELETE FROM monthly_budget_plan")
            
            cursor.execute("SELECT id, balance FROM accounts")
            previous = [(r["id"], r["balance"] or 0.0) for r in cursor.fetchall()]
            cursor.execute("UPDATE accounts SET balance = 0")
            for account_id, old_balance in previous:
                record_balance_event(cursor, ACCOUNT, account_id, -old_balance, 0.0, "delete_all_data")
                
            conn.commit()
            conn.close()
            
            self.refresh_dashboard_data()
            if 'wealth_balance' in self.root.ids:
                self.root.ids.wealth_balance.text = "₺0.00"
                self.root.ids.wealth_pnl.text = "+₺0.00 / %0.00"
            if 'budget_list' in self.root.ids:
                self.root.ids.budget_list.clear_widgets()
            
            toast("Tüm veriler başarıyla silindi!")
            if hasattr(self, 'reset_dialog'):
                self.reset_dialog.dismiss()
        except Exception as e:
            print("Factory reset failed:", e)

# =========================================================================
# 7. RUNNER ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    if _KivyWindow is None:
        print("No usable Kivy window backend detected; skipping GUI startup.")
        raise SystemExit(0)

    FinoraApp().run()
