import os
import sys
import faulthandler
import traceback as _traceback
from datetime import datetime as _crash_datetime

# Crash reporting: log_level=error aşağıda Kivy'nin stderr yakalamasını
# susturduğu için, çökmeler crash.log'a buradan yazılmazsa hiçbir iz bırakmaz.
_CRASH_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")

# Native çökmelerde (SIGSEGV/SIGABRT vb.) Python stack trace'ini crash.log'a döker.
# Dosya tanıtıcısı süreç boyunca açık kalmalı; faulthandler fd'ye doğrudan yazar.
_crash_log_file = open(_CRASH_LOG_PATH, "a", encoding="utf-8")
faulthandler.enable(file=_crash_log_file)


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    """Yakalanmamış Python istisnalarını crash.log'a zaman damgasıyla yazar."""
    try:
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n===== Unhandled exception at {_crash_datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            _traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _log_unhandled_exception

# Configure Kivy before importing the UI stack so it can run in headless
# environments (for tests and servers) without aborting on missing window
# providers such as SDL2 image libraries.
if not os.environ.get("KIVY_NO_ARGS"):
    os.environ["KIVY_NO_ARGS"] = "1"
if not os.environ.get("KIVY_WINDOW"):
    os.environ["KIVY_WINDOW"] = "mock" if not os.environ.get("DISPLAY") else "sdl2"

# Penceresiz (headless) çalışmada Kivy'nin piksel yoğunluğu None kalır ve
# KivyMD import sırasında dp() çağrıları TypeError ile çöker; sabit değer ver.
if os.environ.get("KIVY_WINDOW") == "mock":
    os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
    os.environ.setdefault("KIVY_DPI", "96")

from kivy.config import Config
Config.set('kivy', 'log_level', 'error') # Only log errors
Config.set('kivy', 'log_maxfiles', 2)    # Keep only 2 log files

from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.uix.scrollview import ScrollView
from kivy.factory import Factory
from kivy.properties import StringProperty
from math import sin, cos, radians
from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivy.clock import Clock
import math
import datetime
from kivy.properties import ColorProperty, BooleanProperty
from kivy.storage.jsonstore import JsonStore

try:
    from kivy.core.window import Window
except BaseException as exc:
    class Window(object):
        size = (800, 600)

        @staticmethod
        def bind(*args, **kwargs):
            return None

        @staticmethod
        def unbind(*args, **kwargs):
            return None

try:
    from kivymd.app import MDApp
    from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
    from kivymd.uix.dialog import MDDialog
    from kivymd.uix.menu import MDDropdownMenu
    from kivymd.uix.textfield import MDTextField
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.gridlayout import MDGridLayout
    from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
    from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget
    from kivymd.toast import toast
    from kivymd.uix.label import MDLabel, MDIcon
    from kivymd.uix.list import TwoLineAvatarIconListItem, IRightBodyTouch
    from kivymd.uix.screen import MDScreen
except BaseException as exc:
    from kivy.app import App
    import warnings
    warnings.warn(f"KivyMD import failed; using fallback UI classes: {exc}")

    class MDApp(App):
        def run(self):
            print("KivyMD is unavailable in this environment; skipping GUI startup.")
            return None

    class MDRaisedButton(Widget):
        pass

    class MDFlatButton(Widget):
        pass

    class MDIconButton(Widget):
        pass

    class MDDialog(object):
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def open(self, *args, **kwargs):
            return None

        def dismiss(self, *args, **kwargs):
            return None

    class MDDropdownMenu(object):
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def open(self, *args, **kwargs):
            return None

        def dismiss(self, *args, **kwargs):
            return None

    class MDTextField(Widget):
        pass

    class MDBoxLayout(BoxLayout):
        pass

    class MDGridLayout(GridLayout):
        pass

    class MDSegmentedControl(Widget):
        pass

    class MDSegmentedControlItem(Widget):
        pass

    class TwoLineIconListItem(Widget):
        pass

    class IconLeftWidget(Widget):
        pass

    class MDLabel(Widget):
        pass

    class MDIcon(Widget):
        pass

    class TwoLineAvatarIconListItem(Widget):
        pass

    class IRightBodyTouch(object):
        pass

    class MDScreen(Widget):
        pass

    def toast(*args, **kwargs):
        return None

from utils.crypto import encrypt, decrypt
SECRET_KEY = 'finora_secure_2026'

from database.init_db import initialize_database
from database.db import get_connection
from services.transaction_service import TransactionService
from services.queries import CategoryService



from kivy.metrics import dp

try:
    from kivy.core.window import Window as _KivyWindow
except Exception:
    _KivyWindow = None

import csv

try:
    from kivymd.uix.screen import MDScreen
except BaseException:
    pass

try:
    from kivymd.uix.dialog import MDDialog
except BaseException:
    pass

try:
    from kivymd.uix.button import MDFlatButton, MDRaisedButton
except BaseException:
    pass


from ui.charts import CurvedTrendChart, HorizontalBarChart, LiquidWaveWidget, PieChart, DashboardChartManager, ConfettiWidget
from ui.components import CategorySettingItem, RightButtonsContainer, BudgetListItem, LegendItem, LegendWidget
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

class FinoraApp(MDApp, AssetMixin, DebtMixin, CalculatorMixin, # type: ignore
                TransactionMixin, BudgetMixin, SavingsMixin, RecurringMixin,
                MigrationMixin, AccountMixin, InsightsMixin):

    # ──────────────────────────────────────────────────────────────────────────
    # ODE / RK4 Financial Projection Engine
    # Model: dW/dt = r*W(t) + I - E
    #   W : wealth at time t (days)
    #   r : daily growth rate  (default 0.0001 ≈ 3.65% annual)
    #   I : average daily income  (last 30 days)
    #   E : average daily expense (last 30 days)
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _rk4_wealth_projection(W0, daily_income, daily_expense, days=30, r=0.0001):
        """Pure-Python 4th-Order Runge-Kutta solver.

        Parameters
        ----------
        W0            : float  – current total wealth (initial condition)
        daily_income  : float  – average daily income (I)
        daily_expense : float  – average daily expense (E)
        days          : int    – number of days to simulate (default 30)
        r             : float  – daily growth rate (default 0.0001 ≈ 3.65%/yr)

        Returns
        -------
        float – projected wealth at t = days
        """
        I = daily_income
        E = daily_expense
        dt = 1.0  # step size: 1 day

        def f(t, W):
            """RHS of the ODE: dW/dt = r*W + I - E"""
            return r * W + I - E

        W = W0
        t = 0.0
        for _ in range(days):
            k1 = f(t,        W)
            k2 = f(t + dt/2, W + dt/2 * k1)
            k3 = f(t + dt/2, W + dt/2 * k2)
            k4 = f(t + dt,   W + dt   * k3)
            W  = W + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
            t += dt
        return W

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

        ana_gelir, ek_gelir, temel_gider, ekstra_gider = 0.0, 0.0, 0.0, 0.0
        for amount, t_type, importance in rows:
            try:
                decrypted_amount = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                decrypted_amount = 0.0
                
            if t_type == "income" or t_type == "Gelir":
                if importance == "main": ana_gelir += decrypted_amount
                else: ek_gelir += decrypted_amount
            elif t_type == "expense" or t_type == "Gider":
                if importance == "main": temel_gider += decrypted_amount
                else: ekstra_gider += decrypted_amount

        total_income = ana_gelir + ek_gelir
        total_expense = temel_gider + ekstra_gider
        # Cüzdan = saf likit nakit (gelir - gider). Varlık değeri buraya eklenmez.
        total_balance = total_income - total_expense

        filter_text = getattr(self, "home_filter", "Bugün")

        # ── Periyoda Göre Gelir/Gider Özeti ───────────────────────────────────
        period_income  = 0.0
        period_expense = 0.0
        period_net     = 0.0
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
                date_cond = "> '2000-01-01'"  # Tüm zamanlar
            else:
                date_cond = "= date('now', 'localtime')"  # Bugün

            cursor2.execute(
                f"SELECT amount, type FROM transactions WHERE date(transaction_date) {date_cond}"
            )
            for t_amt, t_typ in cursor2.fetchall():
                try:
                    val = float(decrypt(str(t_amt), SECRET_KEY))
                except Exception:
                    val = 0.0
                if t_typ in ("income", "Gelir"):
                    period_income  += val
                    period_net     += val
                elif t_typ in ("expense", "Gider"):
                    period_expense += val
                    period_net     -= val
            conn2.close()
        except Exception:
            pass
        # ──────────────────────────────────────────────────────────────────────

        if self.root:
            try:
                # ── Dönem Metrik Kartları (Gelir / Gider / Net) ─────────────────────
                def _fmt(v): return f"₺{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                self.root.ids.period_income_label.text  = _fmt(period_income)
                self.root.ids.period_expense_label.text = _fmt(period_expense)
                net_lbl = self.root.ids.period_net_label
                net_lbl.text = ("+ " if period_net >= 0 else "- ") + _fmt(abs(period_net))
                if period_net > 0:
                    net_lbl.text_color = (0.06, 0.55, 0.18, 1)
                elif period_net < 0:
                    net_lbl.text_color = (0.78, 0.1, 0.1, 1)
                else:
                    net_lbl.text_color = (0.5, 0.5, 0.5, 1)

                # ── Home Screen Balance ──────────────────────────────────────────
                formatted_balance = (
                    f"{total_balance:,.2f} ₺"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
                self.root.ids.home_total_balance.text = formatted_balance
                self.root.ids.total_card_amount.text  = formatted_balance

                # Gizli eksi bakiye uyarısı: toplam nakit bakiye eksiye düştüğünde
                # KivyMD "Error" temalı kırmızı uyarı satırını göster, artıdaysa gizle.
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
                formatted_period = (
                    f"{period_net:,.2f} ₺"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
                self.root.ids.today_card_amount.text = f"{prefix}{formatted_period}"

                if total_balance > 0:   self.home_circle_color = (0.18, 0.8, 0.25, 1)
                elif total_balance < 0: self.home_circle_color = (0.9,  0.2,  0.2,  1)
                else:                   self.home_circle_color = (0.5,  0.5,  0.5,  0.2)

                if hasattr(self.root.ids, 'balance_circle'):
                    self.root.ids.balance_circle.canvas.ask_update()

                # ── Toplam Varlık Kartı: yalnızca cash tarafını güncelle ───────────
                # (varlık tarafı, render_active_assets tamamlanınca güncellenir)
                try:
                    # Sadece mevcut cash bakiyesini koy; varlık gelince ezilecek
                    self._liquid_balance_cache = total_balance
                    if not hasattr(self, '_assets_cache') or not self._assets_cache:
                        # varlık veri yoksa sadece cash’i göster
                        self._update_wealth_label(total_balance, None)
                except Exception:
                    pass

                self.render_savings_goals(total_balance)

            except Exception as e:
                pass
                
            try:
                import datetime

                # ── RK4 ODE Projeksiyonu ─────────────────────────────────────
                # Son 30 günün gelir ve giderlerini çek (I ve E parametreleri)
                conn_pred = get_connection()
                cursor_pred = conn_pred.cursor()
                cursor_pred.execute("""
                    SELECT type, amount 
                    FROM transactions
                    WHERE date(transaction_date) >= date('now', '-30 days', 'localtime')
                """)
                rows = cursor_pred.fetchall()
                conn_pred.close()

                inc_30 = 0.0
                exp_30 = 0.0
                for t_type, amount in rows:
                    try:
                        val = float(decrypt(str(amount), SECRET_KEY))
                    except Exception:
                        val = 0.0
                    if t_type == 'income' or t_type == 'Gelir': inc_30 += val
                    elif t_type == 'expense' or t_type == 'Gider': exp_30 += val

                # Günlük ortalama gelir (I) ve gider (E)
                daily_income  = inc_30 / 30.0
                daily_expense = exp_30 / 30.0

                # Başlangıç varlığı W(0) = mevcut net bakiye
                W0 = total_balance

                # RK4 ile 30 günlük projeksiyon (r = 0.0001 ≈ %3,65 yıllık)
                DAILY_RATE = 0.0001
                projected_wealth = self._rk4_wealth_projection(
                    W0=W0,
                    daily_income=daily_income,
                    daily_expense=daily_expense,
                    days=30,
                    r=DAILY_RATE,
                )

                # Türkçe para formatı: 1.234.567,89 ₺
                def _fmt(val):
                    return f"{val:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

                net_change = projected_wealth - W0

                # Simülasyon etiketi
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
                        pred_text.text = (
                            f"{ode_label}\n"
                            f"Dikkat: ODE modeli varlığınızın eksiye düşeceğini "
                            f"gösteriyor. Harcamalarınızı acilen gözden geçirin!"
                        )
                    elif net_change < 0:
                        pred_icon.icon  = "trending-down"
                        pred_icon.text_color = (0.95, 0.75, 0.1, 1)
                        pred_text.text = (
                            f"{ode_label}\n"
                            f"Gider ivmeniz gelirinizi aşıyor; varlığınız "
                            f"{_fmt(abs(net_change))} azalabilir."
                        )
                    else:
                        pred_icon.icon  = "trending-up"
                        pred_icon.text_color = (0.18, 0.8, 0.25, 1)
                        pred_text.text = (
                            f"{ode_label}\n"
                            f"Mevcut gelir-gider dengesiyle varlığınız "
                            f"{_fmt(net_change)} artış gösterebilir."
                        )

            except Exception:
                pass

        if self.root and 'metric_val_income' in self.root.ids:
            from kivy.clock import Clock
            from kivy.metrics import dp
            from kivy.animation import Animation

            self.root.ids.metric_val_income.text = f"{total_income:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            self.root.ids.metric_val_expense.text = f"{total_expense:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

            if total_income > 0:
                savings_rate = ((total_income - total_expense) / total_income) * 100
                self.root.ids.metric_val_savings.text = f"%{savings_rate:.1f}".replace(".", ",")
            else:
                self.root.ids.metric_val_savings.text = "%0,0"

            # Aylık Gelir Amacı kartı: seçili döneme ait toplam geliri gösterir
            if 'metric_val_trend' in self.root.ids:
                aim_text = (f"{total_income:,.0f} ₺".replace(",", ".")
                            if total_income > 0 else "Veri Yok")
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

    dialog = None
    selected_type = "income"
    active_category_type = StringProperty("income")
    selected_category = "Kategori Se\u00e7" 
    home_filter = "Bug\u00fcn"  # Ba\u015flang\u0131\u00e7 Zaman Filtresi
    home_circle_color = ColorProperty((0.5, 0.5, 0.5, 0.2))
    savings_goals = []   # list of goal dicts, max 3
    # Aktif görünüm teması: 'standard' (KivyMD varsayılanı) | 'premium' (Indigo).
    # Ayarlar'daki anahtar buna bağlı olduğu için Property olmalı.
    theme_name = StringProperty("standard")

    def build(self):
        initialize_database()
        self.store = JsonStore('savings_goals.json')
        if self.store.exists('goals'):
            self.savings_goals = self.store.get('goals')['data']
        self.theme_cls.theme_style = "Light"
        # Tema tercihi kalıcı: kayıt yoksa standart (stabil KivyMD) ile açılır.
        self.config_store = JsonStore('finora_config.json')
        pref = "standard"
        if self.config_store.exists('theme'):
            pref = self.config_store.get('theme').get('name', 'standard')
        # persist=False: açılışta okuduğumuzu geri yazmanın anlamı yok.
        self.apply_theme(pref, persist=False)
        return Builder.load_file("ui/dashboard.kv")

    # ─── Görünüm Teması ───────────────────────────────────────────────────────
    def apply_theme(self, theme_name, persist=True):
        """Standart (KivyMD Teal) ya da Premium (Indigo) temayı dinamik uygular.

        Palet değişimi ui/theme.py'de; burada ek olarak kart gölgeleri
        normalize edilir (bkz. _normalize_card_shadows) ve tercih diske yazılır.
        """
        from ui.theme import apply_premium_theme, apply_standard_theme

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

    def _normalize_card_shadows(self, *args):
        """Tüm MDCard'ların elevation/gölge değerlerini sıfırlar.

        KivyMD 1.2'de elevation + shadow_softness kombinasyonu, özellikle
        premium temanın açık zemininde, kartın arkasında yumuşak gölge yerine
        sert gri bir blok olarak render ediliyordu. Düz (flat) kart + yuvarlak
        köşe her iki temada da stabil; bu yüzden gölge kv'den değil buradan,
        tema uygulanırken merkezî olarak kapatılır.

        Ayrıca `ui.theme.apply_card_theme` ile işaretlenmiş (Python'da imperatif
        kurulmuş) kartların dolgu ve kenarlık renkleri burada tazelenir: KV'deki
        kartlar bağlamalarla kendiliğinden güncellenir, Python'dakiler rengi bir
        kez hesapladığı için tema değişimini kaçırırdı.
        """
        if not self.root:
            return
        from kivymd.uix.card import MDCard
        from ui.theme import refresh_card_theme
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

    def _all_widgets(self):
        """root + tüm ScreenManager ekranları + açık diyaloglar üzerinde gezer.

        `Widget.walk()` tek başına yetmiyor: ScreenManager yalnızca GÖRÜNEN
        ekranı children'ında tutar (diğerleri `.screens` içinde), diyaloglar ise
        root'a değil Window'a bağlanır. Tema tazeleme her ikisini de görmek
        zorunda.
        """
        from kivy.uix.screenmanager import ScreenManager
        from kivy.core.window import Window

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

    def contact_us(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
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
                MDRaisedButton(
                    text="E-POSTA GÖNDER",
                    md_bg_color=self.theme_cls.primary_color,
                    on_release=send_email
                ),
            ],
        )
        # Enable markup so [b] works
        if hasattr(self.contact_dialog, 'ids') and 'text' in self.contact_dialog.ids:
            self.contact_dialog.ids.text.markup = True
        self.contact_dialog.open()

    def confirm_delete_all_data(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height="60dp")
        self.reset_input = MDTextField(
            hint_text="SİL yazınız",
            helper_text="Onaylamak için büyük harflerle SİL yazın",
            helper_text_mode="persistent"
        )
        content.add_widget(self.reset_input)

        self.reset_dialog = MDDialog(
            title="Tüm Verileri Sıfırla",
            text="Tüm işlemler, varlıklar, borçlar ve hedefler kalıcı olarak silinecektir. Emin misiniz?",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.reset_dialog.dismiss()),
                MDRaisedButton(
                    text="SİL",
                    md_bg_color=(1, 0.2, 0.2, 1),
                    on_release=self.delete_all_data
                ),
            ],
        )
        self.reset_dialog.open()

    def delete_all_data(self, *args):
        from kivymd.toast import toast
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
            # Hesaplar Kopuk düzeltmesi: tüm işlemler silindiğinde accounts.balance
            # de sıfırlanır, yoksa tablo eski (artık karşılığı olmayan) bir bakiyede kalır.
            cursor.execute("UPDATE accounts SET balance = 0")
            conn.commit()
            conn.close()
            
            self.refresh_dashboard_data()
            if 'wealth_balance' in self.root.ids:
                self.root.ids.wealth_balance.text = "₺0.00"
                self.root.ids.wealth_pnl.text = "+₺0.00 / %0.00"
            if 'budget_list' in self.root.ids:
                self.root.ids.budget_list.clear_widgets()
            
            from kivymd.toast import toast
            toast("Tüm veriler başarıyla silindi!")
            if hasattr(self, 'reset_dialog'):
                self.reset_dialog.dismiss()
        except Exception as e:
            print("Factory reset failed:", e)

    def on_start(self):
        import logging
        # Kart gölgeleri build() sırasında root henüz yokken normalize edilemiyor;
        # ilk kare çizilmeden önce burada kapatılır (gri blok hatası).
        self._normalize_card_shadows()
        # yfinance / requests_cache DEBUG loglarını uygulama başlangıcında sustur
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("peewee").setLevel(logging.CRITICAL)
        self.purge_logs()
        self.vacuum_database()
        self.setup_dynamic_months()
        self.safe_refresh_charts()
        self.load_recent_transactions("Günlük")
        self.generate_financial_advice()
        self.load_active_debts()
        self.load_active_assets()
        self.load_asset_history()
        self.process_due_auto_deductions()

    def purge_logs(self):
        import os, glob
        from kivy.utils import platform
        log_dir = os.path.expanduser('~/.kivy/logs')
        if not os.path.exists(log_dir):
            return
        
        total_size = sum(os.path.getsize(os.path.join(log_dir, f)) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f)))
        if total_size > 5 * 1024 * 1024:
            for f in glob.glob(os.path.join(log_dir, "*.txt")):
                try:
                    os.remove(f)
                except Exception:
                    pass
            print("Purged Kivy logs due to size > 5MB")

    def vacuum_database(self):
        """VACUUM the SQLite database to free up unused space."""
        try:
            conn = get_connection()
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            print("Database VACUUM completed.")
        except Exception as e:
            print(f"VACUUM failed: {e}")

    def change_home_filter(self, text):
        self.home_filter = text
        self.sync_filter_buttons_ui()
        self.safe_refresh_charts()
        self.load_recent_transactions()

    def calculate_monthly_change_rate(self):
        import datetime
        from database.db import get_connection
        from utils.crypto import decrypt
        
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
        else: # Bugün
            current_start = now
            prev_start = now - datetime.timedelta(days=1)
            prev_end = now

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type, transaction_date FROM transactions")
        rows = cursor.fetchall()
        conn.close()
        
        current_net = 0.0
        prev_net = 0.0
        
        for r in rows:
            amount_enc, t_type, t_date = r
            if not t_date: continue
            
            try:
                t_dt = datetime.datetime.strptime(t_date[:10], "%Y-%m-%d").date()
            except:
                continue
                
            try:
                amount = float(decrypt(amount_enc, SECRET_KEY))
            except:
                amount = 0.0
                
            if t_type == 'income' or t_type == 'Gelir':
                val = amount
            elif t_type == 'expense' or t_type == 'Gider':
                val = -amount
            else:
                val = 0.0

            if current_start <= t_dt <= now:
                current_net += val
            elif prev_start <= t_dt < prev_end:
                prev_net += val
                
        if prev_net == 0:
            if current_net > 0:
                change_rate = 100.0
            elif current_net < 0:
                change_rate = -100.0
            else:
                change_rate = 0.0
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
                    label.text_color = (0.18, 0.8, 0.25, 1) # İyi (Yeşil - Net Bakiye Artışı)
                elif rate < 0:
                    label.text = f"-%{abs(rate):.1f}"
                    label.text_color = (0.9, 0.2, 0.2, 1) # Kötü (Kırmızı - Net Bakiye Azalışı)
                else:
                    label.text = "%0.0"
                    label.text_color = (0.5, 0.5, 0.5, 1) # Sabit (Gri)
        except Exception as e:
            print("Error updating change rate UI:", e)

    def refresh_dashboard_data(self, list_filter=None):
        import threading
        from kivy.clock import Clock
        
        # 1. Ana iş parçacığı (main thread) UI güncellemeleri
        try:
            self.update_metrics_and_goals()
            self.update_change_rate_ui()
            if self.root and 'chart_master_box' in self.root.ids:
                self.root.ids.chart_master_box.refresh_dashboard(getattr(self, 'home_filter', 'Bugün'))
        except Exception as e:
            print("Error updating UI metrics:", e)

        # Faz 1 içgörüleri (sağlık skoru / abonelik radarı / anomaliler).
        # Kendi thread'ini açar; buradaki senkron blok uzamasın diye ayrı durur.
        try:
            self.refresh_insights()
        except Exception as e:
            print("Error refreshing insights:", e)
                
        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")
            
        def fetch_task():
            from database.db import get_connection
            from utils.crypto import decrypt
            SECRET_KEY = 'finora_secure_2026'
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                if list_filter == "Günlük" or list_filter == "Bugün":
                    query = "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) = date('now', 'localtime') ORDER BY id DESC LIMIT 15"
                elif list_filter == "1 Hafta" or list_filter == "Haftalık":
                    query = "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE date(transaction_date) >= date('now', '-7 days', 'localtime') ORDER BY id DESC LIMIT 15"
                elif list_filter == "1 Ay" or list_filter == "Aylık":
                    query = "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions WHERE strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') ORDER BY id DESC LIMIT 15"
                else:
                    query = "SELECT type, category, amount, description, strftime('%d/%m %H:%M', transaction_date) FROM transactions ORDER BY id DESC LIMIT 15"
                    
                cursor.execute(query)
                transactions_raw = cursor.fetchall()
                conn.close()
                
                processed_items = []
                for t_type, category, amount_enc, desc_enc, t_date in transactions_raw:
                    try:
                        dec_amt = float(decrypt(str(amount_enc), SECRET_KEY))
                    except Exception:
                        dec_amt = 0.0
                    # Açıklamalar da tutarlar gibi utils.crypto (AES-CBC) ile
                    # yazılıyor; eskiden burada yanlışlıkla Fernet tabanlı
                    # SecurityService kullanılıyordu ve açıklamalar ekranda
                    # çözülmemiş base64 olarak görünüyordu.
                    try:
                        dec_desc = decrypt(str(desc_enc), SECRET_KEY) if desc_enc else ""
                    except Exception:
                        dec_desc = ""
                        
                    processed_items.append((t_type, category, dec_amt, dec_desc, t_date))
                    
                Clock.schedule_once(lambda dt: self._render_recent_transactions(processed_items), 0)
            except Exception as e:
                print("Error fetching recent transactions:", e)
                
        threading.Thread(target=fetch_task, daemon=True).start()

    def _render_recent_transactions(self, transactions):
        """Son işlemler listesini RecycleView'ın data listesine tek seferde atar
        (bkz. mixins/asset_mixin.py::render_asset_history — aynı RecycleView
        deseni, ui/components.py::RecycleListRow)."""
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
                'hisse/varlık': ('chart-line', (0.08, 0.72, 0.42, 1)),  # Hisse/Varlık alımı
            }
            
            for t_type, category, amount, decrypted_desc, t_date in transactions:
                cat_lower = category.lower() if category else ""
                icon_data = next((v for k, v in icon_mapping.items() if k in cat_lower), None)
                if icon_data:
                    icon_name, icon_col = icon_data
                elif category == "Varlık Alımı":
                    icon_name = "chart-line"
                    icon_col  = (0.08, 0.72, 0.42, 1)
                elif category == "Varlık Satışı":
                    icon_name = "cash-plus"
                    icon_col  = (0.18, 0.8, 0.25, 1)
                elif t_type == "income":
                    icon_name = "cash-plus"
                    icon_col  = (0.18, 0.8, 0.25, 1)
                else:
                    icon_name = "cart-outline"
                    icon_col  = (0.9, 0.2, 0.2, 1)

                if category == "Varlık Alımı":
                    amount_text = f"[color=#0277BD]- ₺{amount:,.2f} Yatırım[/color]"
                elif category == "Varlık Satışı":
                    amount_text = f"[color=#2E7D32]+ ₺{amount:,.2f} Satış[/color]"
                elif t_type == "income":
                    amount_text = f"[color=#2E7D32]+ ₺{amount:,.2f}[/color]"
                else:
                    amount_text = f"[color=#D32F2F]- ₺{amount:,.2f}[/color]"

                # Şifrelenmiş açıklamayı atlayıp, sadece işlem tarihi ve tutarı gösterilir
                sec_text = f"{t_date[:10]} | {amount_text}"

                data.append({
                    "text": category,
                    "secondary_text": sec_text,
                    "icon_source": "",
                    "icon_name": icon_name,
                    "icon_color": list(icon_col),
                })

            recent_list.data = data
        except Exception as e:
            print("Error rendering recent UI:", e)


    # ─── Toplam Varlık Kartı Yardımcıları ─────────────────────────────────────────
    _wealth_visible = True       # Başlangıçta görünür
    _liquid_balance_cache = 0.0  # update_metrics_and_goals tarafından yazılır
    _assets_cache = []           # render_active_assets tarafından yazılır

    def _fmt_tr(self, value: float) -> str:
        """Parasal değeri Türk formatına dönüştürür: ₺454.223,91"""
        return (
            f"₺{abs(value):,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )

    def _update_wealth_label(self, total_wealth: float, today_pnl):
        """
        Wealth kartını günceller.
        total_wealth : Liquid Cash + Tüm Varlık Değeri
        today_pnl    : Bugünün net değişimı (float) veya None
        """
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
                # Günlük bakiye değişim oranı
                pct = (today_pnl / (total_wealth - today_pnl) * 100) if (total_wealth - today_pnl) != 0 else 0.0
                sign = "+" if today_pnl >= 0 else "-"
                c_sign = "+" if pct >= 0 else "-"
                pnl.text = (
                    f"{sign}{self._fmt_tr(abs(today_pnl))} "
                    f"({c_sign}{abs(pct):.2f}%) Bugün"
                )
                if today_pnl > 0:
                    pnl.text_color = (0.06, 0.86, 0.29, 1)  # yeşil
                elif today_pnl < 0:
                    pnl.text_color = (0.95, 0.22, 0.22, 1)  # kırmızı
                else:
                    pnl.text_color = (0.5, 0.5, 0.5, 1)    # gri
        except Exception as _e:
            pass  # Kart henüz oluşmadı

    def toggle_wealth_visibility(self):
        """Göz ikonuna basılınca toplam varlığı gizle / göster."""
        self._wealth_visible = not self._wealth_visible
        # Şu anki cache verisiyle yeniden render et
        self.update_wealth_card(self._assets_cache)

    def update_wealth_card(self, enriched_assets):
        """
        Zenginleştirilmiş varlık listesinden toplam varlığı
        ve bugünkü PnL'yi hesaplayıp karta yazar.
        Hem render_active_assets hem de toggle_wealth_visibility tarafından çağrılır.
        """
        liquid_cash = getattr(self, '_liquid_balance_cache', 0.0)

        # Toplam canlı portföy değeri
        portfolio_live = sum(
            a['total_value']
            for a in enriched_assets
            if a.get('total_value') is not None
        )
        total_wealth = liquid_cash + portfolio_live

        # Bugünün varlık PnL: (canlı değer - maliyet) - önceki gün maliyeti yaklaşımı
        # Basit yaklaşım: Şu anki K/Z toplamı + bugünkü likit akış
        asset_pnl = sum(
            a['pnl_amount']
            for a in enriched_assets
            if a.get('pnl_amount') is not None
        )

        # Bugünkü likit değişim (sadece bugüne ait gelir-gider farkı)
        today_liquid_delta = 0.0
        try:
            from database.db import get_connection
            from utils.crypto import decrypt
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
                if t_typ in ("income", "Gelir"):
                    today_liquid_delta += val
                elif t_typ in ("expense", "Gider"):
                    today_liquid_delta -= val
            conn_t.close()
        except Exception:
            pass

        today_pnl = asset_pnl + today_liquid_delta
        self._update_wealth_label(total_wealth, today_pnl if enriched_assets else None)

    def safe_refresh_charts(self):
        self.refresh_dashboard_data()

    def sync_filter_buttons_ui(self):
        try:
            buttons = {
                "Bugün":      self.root.ids.btn_filter_today,
                "1 Hafta":   self.root.ids.btn_filter_week,
                "1 Ay":      self.root.ids.btn_filter_month,
                "1 Yıl":     self.root.ids.btn_filter_year,
                "Hayat Boyu": self.root.ids.btn_filter_lifetime,
            }
            bg_inactive = (
                (0.9, 0.9, 0.9, 1)
                if self.theme_cls.theme_style == "Light"
                else (0.3, 0.3, 0.3, 1)
            )
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

    def toggle_theme(self, is_active):
        """Açık/karanlık mod geçişi.

        Renk token'ları KV bağlamalarıyla kendiliğinden güncellenir; burada
        yalnızca bağlamayla ulaşılamayan iki şey toparlanır: MDCard gölgeleri ve
        AÇIK DİYALOGLARDAKİ giriş alanları (diyaloglar Window'a bağlanır,
        app.root ağacında olmadıkları için normalize taraması onları görmez).
        """
        def _switch_theme(dt):
            from ui.theme import apply_dark_surface_tokens
            apply_dark_surface_tokens()
            self.theme_cls.theme_style = "Dark" if is_active else "Light"
            Clock.schedule_once(self._after_theme_switch, 0)
        Clock.schedule_once(_switch_theme, 0.2)

    def _after_theme_switch(self, *args):
        self._normalize_card_shadows()
        self._resync_text_fields()

    def _resync_text_fields(self):
        """Giriş alanlarının iç (_hint_text_color vb.) renklerini tazeler.

        MDTextField, çizimde kullandığı özel `_` alanlarını public renklerden
        yalnızca belirli anlarda kopyalar; KV kuralı public değerleri
        güncelledikten sonra bu kopyalamayı açıkça tetiklemezsek açık kalan bir
        diyalogda hint metni eski temanın renginde kalır.
        """
        from kivymd.uix.textfield import MDTextField

        if not self.root:
            return
        for widget in self._all_widgets():
            if isinstance(widget, MDTextField):
                try:
                    widget.set_default_colors(0)
                except Exception:
                    pass

    def check_login(self):
        from security.security_service import SecurityService
        
        username = self.root.ids.username_input.text
        password = self.root.ids.password_input.text

        ADMIN_HASH = "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"

        if username == "admin" and password == "admin_secret":
            self.root.ids.login_error_label.text = ""
            self.root.ids.username_input.text = ""
            self.root.ids.password_input.text = ""
            self.root.ids.screen_manager.current = "admin"
        elif username == "admin" and SecurityService.verify_password(password, ADMIN_HASH):
            self.root.ids.login_error_label.text = ""
            self.root.ids.username_input.text = ""
            self.root.ids.password_input.text = ""
            self.root.ids.screen_manager.current = "home"
        else:
            self.root.ids.login_error_label.text = "Hatalı kullanıcı adı veya şifre!"
            
            pwd_container = self.root.ids.password_container
            usr_input = self.root.ids.username_input
            
            Animation.cancel_all(pwd_container)
            Animation.cancel_all(usr_input)
            
            if not hasattr(pwd_container, 'anim_original_x'):
                pwd_container.anim_original_x = pwd_container.x
            if not hasattr(usr_input, 'anim_original_x'):
                usr_input.anim_original_x = usr_input.x
                
            ox_pwd = pwd_container.anim_original_x
            ox_usr = usr_input.anim_original_x
            
            anim_pwd = (
                Animation(x=ox_pwd + 10, duration=0.05) +
                Animation(x=ox_pwd - 10, duration=0.05) +
                Animation(x=ox_pwd + 10, duration=0.05) +
                Animation(x=ox_pwd - 10, duration=0.05) +
                Animation(x=ox_pwd, duration=0.05)
            )
            
            anim_usr = (
                Animation(x=ox_usr + 10, duration=0.05) +
                Animation(x=ox_usr - 10, duration=0.05) +
                Animation(x=ox_usr + 10, duration=0.05) +
                Animation(x=ox_usr - 10, duration=0.05) +
                Animation(x=ox_usr, duration=0.05)
            )
            
            def clear_original_x(*args):
                if hasattr(pwd_container, 'anim_original_x'):
                    del pwd_container.anim_original_x
                if hasattr(usr_input, 'anim_original_x'):
                    del usr_input.anim_original_x
                    
            anim_pwd.bind(on_complete=clear_original_x)
            
            anim_pwd.start(pwd_container)
            anim_usr.start(usr_input)

    def admin_logout(self):
        if self.root:
            self.root.ids.username_input.text = ""
            self.root.ids.password_input.text = ""
            self.root.ids.screen_manager.current = "login"

    def load_categories(self, cat_type=None):
        if cat_type:
            self.active_category_type = cat_type
            
        settings_list = self.root.ids.settings_list
        settings_list.clear_widgets()
        from kivy.clock import Clock
        
        def _populate_categories(dt):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name, type, importance FROM categories WHERE type = ? ORDER BY name", (self.active_category_type,))
            categories = cursor.fetchall()
            conn.close()

            for cat_name, cat_type_val, cat_imp in categories:
                item = CategorySettingItem(
                    cat_name=cat_name,
                    cat_type=cat_type_val,
                    cat_importance=cat_imp
                )
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
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. En çok harcama yapılan alan (Bu ay)
        # 1. En çok harcama yapılan alan (Bu ay)
        cursor.execute("""
            SELECT category, amount 
            FROM transactions 
            WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') 
        """)
        expense_rows_this_month = cursor.fetchall()
        
        cat_sums: dict[str, float] = {}
        this_month_exp = 0.0
        for cat, amount in expense_rows_this_month:
            try:
                val = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                val = 0.0
            cat_sums[cat] = cat_sums.get(cat, 0.0) + val
            this_month_exp += val
            
        highest_cat_name = max(cat_sums, key=lambda k: cat_sums[k]) if cat_sums else "Yok"
        
        # 2. Geçen döneme kıyasla harcama değişimi
        cursor.execute("""
            SELECT amount 
            FROM transactions 
            WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', '-1 month', 'localtime')
        """)
        last_month_exp = 0.0
        for (amount,) in cursor.fetchall():
            try:
                last_month_exp += float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                pass
        
        # 3. Tasarruf Oranı (Bu ay)
        cursor.execute("""
            SELECT amount 
            FROM transactions 
            WHERE type='income' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime')
        """)
        this_month_inc = 0.0
        for (amount,) in cursor.fetchall():
            try:
                this_month_inc += float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                pass
        conn.close()
        
        if last_month_exp > 0:
            change_percent = ((this_month_exp - last_month_exp) / last_month_exp) * 100
            if change_percent > 0:
                change_text = f"%{change_percent:.1f} arttı"
            else:
                change_text = f"%{abs(change_percent):.1f} azaldı"
        else:
            change_text = "karşılaştırılacak veri yok"
            
        savings_rate = 0
        if this_month_inc > 0:
            savings_rate = ((this_month_inc - this_month_exp) / this_month_inc) * 100

        advice_text = (
            f"Bu ay harcamalarınız geçen döneme kıyasla {change_text}.\n"
            f"En çok harcama yapılan alan: {highest_cat_name}.\n"
            f"Bu ayki net tasarruf oranınız: %{savings_rate:.1f}. Harika birikim dönemi!"
        )
        
        icon = "robot-outline"
        color = (0.13, 0.59, 0.95, 1)

        # UI Güncellemesi
        try:
            app = MDApp.get_running_app()
            if app and app.root and 'prediction_text' in app.root.ids:
                app.root.ids.prediction_text.text = advice_text
                app.root.ids.prediction_icon.icon = icon
                app.root.ids.prediction_icon.text_color = color
        except Exception:
            pass
        
        # Fallback for old advice_label if it exists
        if 'advice_label' in self.root.ids:
            self.root.ids.advice_label.text = advice_text
            self.root.ids.advice_icon.icon = icon
            self.root.ids.advice_icon.text_color = color

if __name__ == "__main__":
    if _KivyWindow is None:
        print("No usable Kivy window backend detected; skipping GUI startup.")
        raise SystemExit(0)

    FinoraApp().run()