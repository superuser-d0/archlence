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
from kivy.properties import ColorProperty, BooleanProperty, StringProperty
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
from services.category_service import CategoryService

from kivy.properties import NumericProperty

from kivy.metrics import dp

try:
    from kivy.core.window import Window as _KivyWindow
except Exception:
    _KivyWindow = None

import csv
import os

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


from ui.charts import CurvedTrendChart, HorizontalBarChart, LiquidWaveWidget, PieChart, DashboardChartManager
from ui.components import CategorySettingItem, RightButtonsContainer, BudgetListItem, LegendItem, LegendWidget
from screens.admin_screen import AdminScreen

from mixins.asset_mixin import AssetMixin
from mixins.debt_mixin import DebtMixin
from mixins.calculator_mixin import CalculatorMixin
from mixins.transaction_mixin import TransactionMixin

class FinoraApp(MDApp, AssetMixin, DebtMixin, CalculatorMixin, TransactionMixin):

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
            # print(f"[RK4] Day {int(t):>2}: Projected Wealth = {W:>14,.2f} ₺") # Kapatıldı: Kasma sorunu
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
                W0 = float(total_balance)

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
                            f"Dikkat: ODE modeli varliginizin eksiye dusecegini "
                            f"gosteriyor. Harcamalarinizi acilen gozden gecirin!"
                        )
                    elif net_change < 0:
                        pred_icon.icon  = "trending-down"
                        pred_icon.text_color = (0.95, 0.75, 0.1, 1)
                        pred_text.text = (
                            f"{ode_label}\n"
                            f"Gider ivmeniz gelirinizi asiyor; varliginiz "
                            f"{_fmt(abs(net_change))} azalabilir."
                        )
                    else:
                        pred_icon.icon  = "trending-up"
                        pred_icon.text_color = (0.18, 0.8, 0.25, 1)
                        pred_text.text = (
                            f"{ode_label}\n"
                            f"Mevcut gelir-gider dengesiyle varliginiz "
                            f"{_fmt(net_change)} artis gosterebilir."
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

            # Aylık Gelir Amacı card: display total income for the period
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

    def build(self):
        initialize_database()
        self.store = JsonStore('savings_goals.json')
        if self.store.exists('goals'):
            self.savings_goals = self.store.get('goals')['data']
        self.theme_cls.theme_style = "Light" 
        self.theme_cls.primary_palette = "Teal" 
        return Builder.load_file("ui/dashboard.kv")
        
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
        
        # 1. Main thread updates
        try:
            self.update_metrics_and_goals()
            self.update_change_rate_ui()
            if self.root and 'chart_master_box' in self.root.ids:
                self.root.ids.chart_master_box.refresh_dashboard(getattr(self, 'home_filter', 'Bugün'))
        except Exception as e:
            print("Error updating UI metrics:", e)
                
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
        from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget
        from kivy.factory import Factory
        try:
            recent_list = self.root.ids.recent_transactions_list
            recent_list.clear_widgets()
            
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

                # Just transaction date and amount - completely dropping encrypted string description
                sec_text = f"{t_date[:10]} | {amount_text}"

                item = TwoLineIconListItem(text=category, secondary_text=sec_text)
                if hasattr(item.ids, '_lbl_secondary'):
                    item.ids._lbl_secondary.markup = True
                elif hasattr(item, '_secondary_label'):
                    item._secondary_label.markup = True
                    
                icon = IconLeftWidget(icon=icon_name, theme_text_color="Custom", text_color=icon_col)
                item.add_widget(icon)
                recent_list.add_widget(item)
                recent_list.add_widget(Factory.MDSeparator())
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
        def _switch_theme(dt):
            self.theme_cls.theme_style = "Dark" if is_active else "Light"
        Clock.schedule_once(_switch_theme, 0.2)

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

    def toggle_compound_mode(self, segment, item):
        if item.text == "Gelişmiş":
            self.comp_deposit.opacity = 1
            self.comp_deposit.disabled = False
        else:
            self.comp_deposit.opacity = 0
            self.comp_deposit.disabled = True
            self.comp_deposit.text = ""

    def toggle_loan_mode(self, segment, item):
        if item.text == "Gelişmiş":
            self.loan_type.opacity = 1
            self.loan_type.disabled = False
            self.expense_header_layout.opacity = 1
            self.expense_header_layout.disabled = False
            self.expense_list_scroll.opacity = 1
            self.expense_list_scroll.disabled = False
        else:
            self.loan_type.opacity = 0
            self.loan_type.disabled = True
            self.expense_header_layout.opacity = 0
            self.expense_header_layout.disabled = True
            self.expense_list_scroll.opacity = 0
            self.expense_list_scroll.disabled = True
            
    def update_loan_type(self, segment, item):
        self.loan_type_selected = item.text
        
        # Seçime göre dinamik hint_text (İpucu) güncellemesi
        if item.text == "İhtiyaç":
            self.loan_term.hint_text = "Vade (Ay - Maks 36)"
        elif item.text == "Taşıt":
            self.loan_term.hint_text = "Vade (Ay - Maks 48)"
        elif item.text == "Konut":
            self.loan_term.hint_text = "Vade (Ay - Maks 120)"
        
    def open_expense_dialog(self, *args):
        if len(self.custom_expenses) >= 10:
            toast("Maksimum 10 masraf ekleyebilirsiniz.")
            return
            
        self.exp_dialog_layout = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="260dp")
        
        self.exp_name = MDTextField(hint_text="Masraf Adı (Örn: Ekspertiz)", max_text_length=30)
        
        self.exp_type_segment = MDSegmentedControl(size_hint_x=1)
        self.exp_type_segment.add_widget(MDSegmentedControlItem(text="Tek Seferlik"))
        self.exp_type_segment.add_widget(MDSegmentedControlItem(text="Çok Seferlik"))
        
        self.exp_amount = MDTextField(hint_text="Toplam Tutar (₺)", input_filter="float")
        
        self.exp_term = MDTextField(hint_text="Süre (Ay)", input_filter="int", opacity=0, disabled=True)
        
        def toggle_term_field(segment, item):
            if item.text == "Çok Seferlik":
                self.exp_term.opacity = 1
                self.exp_term.disabled = False
            else:
                self.exp_term.opacity = 0
                self.exp_term.disabled = True
                self.exp_term.text = ""
                
        self.exp_type_segment.bind(on_active=toggle_term_field)
        
        self.exp_dialog_layout.add_widget(self.exp_name)
        self.exp_dialog_layout.add_widget(self.exp_type_segment)
        self.exp_dialog_layout.add_widget(self.exp_amount)
        self.exp_dialog_layout.add_widget(self.exp_term)
        
        self.expense_dialog = MDDialog(
            title="Özel Masraf Ekle",
            type="custom",
            content_cls=self.exp_dialog_layout,
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.expense_dialog.dismiss()),
                MDFlatButton(text="EKLE", on_release=self.add_custom_expense)
            ]
        )
        self.expense_dialog.open()

    def add_custom_expense(self, *args):
        name = self.exp_name.text.strip()
        amount_text = self.exp_amount.text
        
        if not name or not amount_text:
            toast("Lütfen ad ve tutar girin!")
            return
            
        amount = float(amount_text)
        if amount <= 0:
            toast("Tutar 0'dan büyük olmalı!")
            return
            
        is_cok = not self.exp_term.disabled
        exp_type = "Çok Seferlik" if is_cok else "Tek Seferlik"
        
        term = 0
        if is_cok:
            if not self.exp_term.text:
                toast("Lütfen süre girin!")
                return
            term = int(self.exp_term.text)
            if term <= 0:
                toast("Süre 1 aydan büyük olmalı!")
                return
            if self.loan_term.text and term > int(self.loan_term.text):
                toast(f"Süre, kredi vadesinden büyük olamaz ({self.loan_term.text} ay)!")
                return

        exp_data = {
            "name": name,
            "type": exp_type,
            "amount": amount,
            "term": term
        }
        self.custom_expenses.append(exp_data)
        
        self.expense_dialog.dismiss()
        self.update_expense_list_ui()

    def update_expense_list_ui(self):
        self.expense_list_layout.clear_widgets()
        self.expense_header_label.text = f"Özel Masraflar ({len(self.custom_expenses)}/10)"
        
        for idx, exp in enumerate(self.custom_expenses):
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
            
            desc = f"{exp['name']} ({exp['type']}) - {exp['amount']} ₺"
            if exp["type"] == "Çok Seferlik":
                desc += f" / {exp['term']} Ay"
                
            lbl = MDLabel(text=desc, font_style="Caption")
            
            del_btn = MDIconButton(
                icon="close", 
                icon_size="16sp",
                size_hint=(None, None), 
                size=("24dp", "24dp"),
                pos_hint={"center_y": 0.5},
                on_release=lambda x, index=idx: self.remove_custom_expense(index)
            )
            row.add_widget(lbl)
            row.add_widget(del_btn)
            self.expense_list_layout.add_widget(row)

    def remove_custom_expense(self, index):
        if 0 <= index < len(self.custom_expenses):
            self.custom_expenses.pop(index)
            self.update_expense_list_ui()

    def calculate_interest(self, *args):
        try:
            p = float(self.int_principal.text)
            r = float(self.int_rate.text)
            d = int(self.int_days.text)
            
            if p <= 0 or r <= 0 or d <= 0:
                toast("Lütfen 0'dan büyük değerler girin!")
                return
                
            gross_profit = p * r * d / 36500
            net_profit = gross_profit * 0.95 # Varsayılan %5 stopaj (Vergi)
            total = p + net_profit
            
            f_profit = f"{net_profit:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            f_total = f"{total:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            
            self.int_result_label.text = f"Net Getiri: + {f_profit}\nVade Sonu: {f_total}\n(%5 Stopaj düşülmüştür)"
            self.int_result_label.theme_text_color = "Custom"
            self.int_result_label.text_color = (0.13, 0.59, 0.95, 1)
        except ValueError:
            toast("Lütfen geçerli sayılar girin!")

    def show_payment_plan_table(self, *args):
        from kivymd.uix.datatables import MDDataTable
        from kivy.metrics import dp
        from kivymd.uix.boxlayout import MDBoxLayout
        
        table_layout = MDBoxLayout(orientation="vertical")
        self.table = MDDataTable(
            use_pagination=True,
            rows_num=10,
            column_data=[
                ("Ay", dp(15)),
                ("Temel Taksit", dp(30)),
                ("Ek Masraf", dp(25)),
                ("Toplam Ödeme", dp(30)),
                ("Anapara", dp(25)),
                ("Faiz/Vergi", dp(25)),
                ("Bakiye", dp(30)),
            ],
            row_data=self.loan_table_data,
        )
        table_layout.add_widget(self.table)
        
        self.table_dialog = MDDialog(
            title="Ödeme Planı",
            type="custom",
            content_cls=table_layout,
            size_hint=(0.95, 0.95),
            buttons=[
                MDRaisedButton(text="KAPAT", on_release=lambda x: self.table_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                MDRaisedButton(text="PDF İNDİR", on_release=self.export_plan_to_pdf, md_bg_color=(0.13, 0.59, 0.95, 1))
            ]
        )
        self.table_dialog.open()

    def calculate_savings_goal(self, *args):
        try:
            target = float(self.sg_target_input.text)
            deposit = float(self.sg_deposit_input.text)
            name = self.sg_name_input.text if self.sg_name_input.text else "Hedef"
            
            if target <= 0 or deposit <= 0:
                toast("Lütfen 0'dan büyük tutarlar girin!")
                return
                
            periods = math.ceil(target / deposit)
            
            if self.sg_period == "Günlük":
                months = periods // 30
                days = periods % 30
                time_str = f"{months} Ay, {days} Gün" if months > 0 else f"{days} Gün"
                self.sg_result_label.text = f"'{name}' için gereken süre:\n{periods} Gün\n(~{time_str})"
            else:
                years = periods // 12
                months = periods % 12
                time_str = f"{years} Yıl, {months} Ay" if years > 0 else f"{months} Ay"
                self.sg_result_label.text = f"'{name}' için gereken süre:\n{periods} Ay\n(~{time_str})"
                
            self.sg_result_label.theme_text_color = "Custom"
            self.sg_result_label.text_color = (0.13, 0.59, 0.95, 1)

        except ValueError:
            toast("L\u00fctfen ge\u00e7erli say\u0131lar girin!")

    def commit_savings_goal(self, *args):
        """Append new goal to list (max 3) and refresh dashboard."""
        try:
            target = float(self.sg_target_input.text)
            name   = self.sg_name_input.text.strip() or "Birikim Hedefim"
            if target <= 0:
                toast("Hedef tutar 0'dan b\u00fcy\u00fck olmal\u0131d\u0131r!")
                return
            if len(self.savings_goals) >= 3:
                toast("\u26a0\ufe0f En fazla 3 aktif hedef ekleyebilirsin!")
                return
            goal = {
                "name":         name,
                "target":       target,
                "color":        "green",
                "current":      0.0,
                "auto_deposit": getattr(self, "sg_auto_deposit", False),
            }
            self.savings_goals.append(goal)
            self.store.put('goals', data=self.savings_goals)
            toast(f"\u2714 '{name}' hedefi eklendi!")
            self.sg_dialog.dismiss()
            # Refresh the dashboard cards
            try:
                if self.root and 'goals_container' in self.root.ids:
                    self.render_savings_goals(0)  # balance=0 placeholder; real fetch below
            except Exception:
                pass
                self.safe_refresh_charts()
        except ValueError:
            toast("L\u00fctfen ge\u00e7erli bir hedef tutar girin!")

    # ─── Color cycling ────────────────────────────────────────────────────────
    COLOR_CYCLE = ["green", "blue", "red"]
    COLOR_MAP = {
        "green": (0.1,  0.8,  0.2,  0.85),
        "blue":  (0.1,  0.5,  0.95, 0.85),
        "red":   (0.9,  0.15, 0.15, 0.85),
    }

    def cycle_goal_color(self, goal_idx, wave_widget, *args):
        """Cycle the color of a specific goal and live-update its wave widget."""
        if goal_idx >= len(self.savings_goals):
            return
        g = self.savings_goals[goal_idx]
        cur = g.get("color", "green")
        nxt = self.COLOR_CYCLE[(self.COLOR_CYCLE.index(cur) + 1) % len(self.COLOR_CYCLE)]
        g["color"] = nxt
        wave_widget.wave_color = self.COLOR_MAP[nxt]
        self.store.put('goals', data=self.savings_goals)
        color_names = {"green": "Yeşil", "blue": "Mavi", "red": "Kırmızı"}
        toast(f"Renk değiştirildi: {color_names[nxt]}")

    # ─── One-time deposit into a goal ────────────────────────────────────────
    def add_funds_to_goal(self, goal_idx, wave_widget, pct_label, *args):
        """Open a quick dialog to add a one-time amount to a specific goal."""
        if goal_idx >= len(self.savings_goals):
            return
        g = self.savings_goals[goal_idx]
        amount_field = MDTextField(hint_text="Eklenecek Tutar (\u20ba)", input_filter="float")
        inner = MDBoxLayout(orientation="vertical", size_hint_y=None, height="80dp")
        inner.add_widget(amount_field)

        def _do_add(instance):
            try:
                amount = float(amount_field.text)
                if amount <= 0:
                    toast("0'dan b\u00fcy\u00fck bir tutar girin!")
                    return
                g["current"] = g.get("current", 0.0) + amount
                self.store.put('goals', data=self.savings_goals)
                toast(f"\u20ba{amount:,.2f} eklendi!")
                fund_dlg.dismiss()
                self.render_savings_goals(0)
                self.safe_refresh_charts()
            except ValueError:
                toast("Ge\u00e7erli bir say\u0131 girin!")

        fund_dlg = MDDialog(
            title=f"{g['name']} \u2014 Miktar Ekle",
            type="custom",
            content_cls=inner,
            buttons=[
                MDRaisedButton(text="KAPAT", on_release=lambda x: fund_dlg.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                MDRaisedButton(text="EKLE",  on_release=_do_add, md_bg_color=(0.18, 0.8, 0.25, 1)),
            ]
        )
        fund_dlg.open()

    # ─── Main goal card renderer ──────────────────────────────────────────────
    def render_savings_goals(self, total_balance, *args):
        """Dynamically build one outlined MDCard per goal inside goals_container."""
        from kivymd.uix.card import MDCard as _MDCard
        if not (self.root and 'goals_container' in self.root.ids):
            return
        container = self.root.ids.goals_container
        container.clear_widgets()

        if not self.savings_goals:
            lbl = MDLabel(
                text="Birikim hedefi belirlenmedi \u2014 Ara\u00e7lar sekmesinden hedef ekleyebilirsin!",
                font_style="Caption",
                italic=True,
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(40),
                halign="center",
            )
            lbl.bind(size=lbl.setter('text_size'))
            container.add_widget(lbl)
            return

        for idx, goal in enumerate(self.savings_goals):
            target    = float(goal.get("target", 1))
            current   = float(goal.get("current", 0.0))
            pct       = max(0.0, min(100.0, (current / target) * 100))
            color_key = goal.get("color", "green")
            wave_clr  = self.COLOR_MAP.get(color_key, self.COLOR_MAP["green"])

            if pct >= 100:
                quote = "Tebrikler! B\u00fct\u00e7e tamamland\u0131, hedeflenen donan\u0131mlar\u0131 almaya haz\u0131rs\u0131n!"
            elif current < 0:
                quote = "B\u00fct\u00e7en alarm veriyor \u2014 harcamalar\u0131n\u0131 optimize et!"
            elif pct < 25:
                quote = "Her b\u00fcy\u00fck ba\u015far\u0131 k\u00fc\u00e7\u00fck bir ad\u0131mla ba\u015flar. Devam!"
            elif pct < 75:
                quote = "Harika! Yar\u0131 yola geldin. Sab\u0131r en b\u00fcy\u00fck sermaye!"
            else:
                quote = "Hedefe ramak kald\u0131! Son hamleyi yap!"

            formatted_target  = f"\u20ba{target:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            formatted_current = f"\u20ba{current:,.2f}".replace(",","X").replace(".",",").replace("X",".")

            card = _MDCard(
                orientation="vertical",
                size_hint_y=None,
                height=dp(180),
                padding=dp(16),
                spacing=dp(12),
                style="outlined",
                md_bg_color=getattr(self.theme_cls, 'bg_darkest', getattr(self.theme_cls, 'bg_normal', (1, 1, 1, 1))),
                line_color=(0.5, 0.5, 0.5, 0.35),
                radius=[dp(14), dp(14), dp(14), dp(14)],
            )

            # Header row: trophy icon + goal name
            hdr = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
            ico = MDIconButton(
                icon="trophy",
                theme_text_color="Custom",
                icon_color=(0.95, 0.75, 0.1, 1),
                size_hint_x=None,
                width=dp(36),
                pos_hint={"center_y": .5}
            )
            name_lbl = MDLabel(
                text=f"{goal['name']}  \u2014  Hedef: {formatted_target}  |  Biriken: {formatted_current}",
                bold=True,
                theme_text_color="Primary",
                font_style="Subtitle2",
                pos_hint={"center_y": .5}
            )
            hdr.add_widget(ico)
            hdr.add_widget(name_lbl)
            card.add_widget(hdr)

            # Daha kibar ve ince dalga barı (Height dp(20))
            wave = LiquidWaveWidget(
                size_hint_x=1,
                size_hint_y=None,
                height=dp(20),
                progress=pct,
                wave_color=wave_clr,
            )
            card.add_widget(wave)

            # Motivation Label: theme_text_color="Secondary", italicized.
            pct_lbl = MDLabel(
                text=f"%{pct:.1f} Tamamland\u0131 \u2014 {quote}".replace(".", ","),
                bold=False,
                font_size=dp(13),
                italic=True,
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(20),
            )
            pct_lbl.bind(size=pct_lbl.setter('text_size'))
            card.add_widget(pct_lbl)

            # Footer: MDBoxLayout with icon_size="28sp" buttons (Palette, Plus).
            act_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(40),
                spacing=dp(16),
            )
            btn_color = MDIconButton(
                icon="palette",
                theme_text_color="Custom",
                icon_color=wave_clr[:3] + (1,),
                icon_size="28sp",
                pos_hint={"center_y": .5}
            )
            btn_color.bind(on_release=lambda inst, i=idx, w=wave: self.cycle_goal_color(i, w))

            btn_funds = MDIconButton(
                icon="cash-plus",
                theme_text_color="Custom",
                icon_color=(0.1, 0.8, 0.2, 1),
                icon_size="28sp",
                pos_hint={"center_y": .5}
            )
            btn_funds.bind(on_release=lambda inst, i=idx, w=wave, p=pct_lbl: self.add_funds_to_goal(i, w, p))

            act_row.add_widget(btn_color)
            act_row.add_widget(btn_funds)
            card.add_widget(act_row)

            container.add_widget(card)

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
        
        cat_sums = {}
        this_month_exp = 0.0
        for cat, amount in expense_rows_this_month:
            try:
                val = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                val = 0.0
            cat_sums[cat] = cat_sums.get(cat, 0.0) + val
            this_month_exp += val
            
        highest_cat_name = max(cat_sums, key=cat_sums.get) if cat_sums else "Yok"
        
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

    def setup_dynamic_months(self):
        import datetime
        MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        
        current_month_index = datetime.datetime.now().month  
        self.active_budget_month = current_month_index
        
        container = getattr(self.root.ids, 'month_selector_container', None)
        if container:
            container.clear_widgets()
            
            from kivymd.uix.button import MDRoundFlatButton
            for i in range(current_month_index, 13):
                month_name = MONTHS[i - 1]
                btn = MDRoundFlatButton(text=month_name)
                btn.bind(on_release=lambda instance, m_idx=i: self.change_budget_month(m_idx))
                container.add_widget(btn)

    def change_budget_month(self, month_index):
        self.active_budget_month = month_index
        self.load_budget_list()
        self.generate_next_month_projection()

    def generate_next_month_projection(self):
        import datetime
        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)
        
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. SADECE Bütçe Planlayıcı tablosundan (monthly_budget_plan) ve SEÇİLİ AY'a ait verileri çek
        try:
            cursor.execute("SELECT type, amount FROM monthly_budget_plan WHERE target_month = ?", (target_month,))
        except Exception:
            cursor.execute("SELECT type, amount FROM monthly_budget_plan")
            
        rows = cursor.fetchall()
        planlanan_gelir = 0.0
        planlanan_gider = 0.0
        for t_type, amount in rows:
            try:
                val = float(decrypt(str(amount), SECRET_KEY))
            except Exception:
                val = 0.0
            if t_type == "Gelir" or t_type == "income": planlanan_gelir += val
            elif t_type == "Gider" or t_type == "expense": planlanan_gider += val
        conn.close()
        
        # 2. İZOLE HESAPLAMA (Geçmiş varlıklar veya ekstra harcamalar dahil edilmez)
        harcanabilir_limit = planlanan_gelir - planlanan_gider
        
        # 3. SIFIRIN ALTI KONTROLÜ VE TAVSİYE MANTIĞI
        advice_text = "Bütçeniz dengede."
        icon = "check-circle"
        color = (0.18, 0.8, 0.25, 1) # Yeşil
        
        if harcanabilir_limit < 0:
            advice_text = "Dikkat: Planlanan giderler, gelirlerinizi aşıyor. Bütçeniz eksiye düşecek!"
            icon = "close-circle"
            color = (0.9, 0.2, 0.2, 1) # Kırmızı
            
        elif harcanabilir_limit == 0:
            advice_text = "Dikkat: Gelir ve gideriniz başa baş. Bütçenizde hiç esneme payı yok."
            icon = "alert"
            color = (0.95, 0.6, 0.1, 1) # Turuncu
            
        # Arayüz (UI) Güncellemesi
        if hasattr(self.root.ids, 'projection_label'):
            formatted_limit = f"{harcanabilir_limit:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                      "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            try:
                ay_ismi = MONTHS[target_month - 1]
            except:
                ay_ismi = "Ocak"
            self.root.ids.projection_label.text = f"{ay_ismi} Ayı Harcama Limitiniz: {formatted_limit}\n\n{advice_text}"
            self.root.ids.projection_icon.icon = icon
            self.root.ids.projection_icon.text_color = color
            
        return {
            "harcanabilir_limit": harcanabilir_limit,
            "tavsiye": advice_text,
            "tavsiye_ikonu": icon
        }

    def show_budget_planner(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivymd.uix.selectioncontrol import MDSwitch
        from kivymd.uix.label import MDLabel
        from kivy.core.window import Window
        import datetime

        # ── Outer container: a ScrollView so nothing ever squishes ──────────
        outer_scroll = ScrollView(
            size_hint_y=None,
            height=Window.height * 0.65,
            do_scroll_x=False,
            do_scroll_y=True,
        )

        form_layout = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(25),
            padding=[dp(15), dp(30), dp(15), dp(15)],
        )

        # ── Inputs ───────────────────────────────────────────────────────────
        self.bp_name_input = MDTextField(
            hint_text="Kalem Adı (Örn: Maaş, Kira)",
            size_hint_y=None,
            height=dp(68),
        )
        self.bp_amount_input = MDTextField(
            hint_text="Tutar (₺)",
            input_filter="float",
            size_hint_y=None,
            height=dp(68),
        )

        # ── Gelir / Gider segmented control ─────────────────────────────────
        self.bp_type_segment = MDSegmentedControl(size_hint_x=1)
        self.bp_type_segment.add_widget(MDSegmentedControlItem(text="Gelir"))
        self.bp_type_segment.add_widget(MDSegmentedControlItem(text="Gider"))
        self.bp_selected_type = "income"

        def on_seg_active(seg, item):
            self.bp_selected_type = "expense" if item.text == "Gider" else "income"

        self.bp_type_segment.bind(on_active=on_seg_active)

        # ── Switch row ───────────────────────────────────────────────────────
        switch_layout = MDBoxLayout(
    orientation="horizontal", 
    size_hint_y=None, 
    height=dp(48), 
    spacing=dp(10),
    padding=[dp(5), 0, dp(45), 0] # Shifted left by reducing left padding and increasing right padding
)
        switch_label = MDLabel(
            text="Mevcut kalemi diğer aylara da uygula",
            theme_text_color="Primary",
            valign="center",
            halign="left",
            size_hint_x=1,
        )
        self.bp_repeat_switch = MDSwitch(
            pos_hint={"center_y": 0.5},
            active=False,
            size_hint_x=None,
            width=dp(48),
        )
        switch_layout.add_widget(switch_label)
        switch_layout.add_widget(self.bp_repeat_switch)

        # ── Month grid (3 columns → wraps cleanly, never overflows) ─────────
        self.months_grid = GridLayout(
            cols=3,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(0),
            opacity=0,
        )
        upcoming_months = ["Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        for month_name in upcoming_months:
            btn = MDRaisedButton(
                text=month_name,
                size_hint=(1, None),
                height=dp(36),
                md_bg_color=(0.12, 0.53, 0.53, 1),
                text_color=(1, 1, 1, 1),
                elevation=0,
            )
            btn.is_selected = False
            btn.bind(on_release=self.toggle_custom_month_button)
            self.months_grid.add_widget(btn)

        def on_switch_active(instance, value):
            if value:
                # 2 rows of 36dp buttons + 8dp spacing + 8dp padding
                self.months_grid.height = dp(80)
                self.months_grid.opacity = 1
            else:
                self.months_grid.height = dp(0)
                self.months_grid.opacity = 0

        self.bp_repeat_switch.bind(active=on_switch_active)

        # ── List area (items populated by load_budget_list) ──────────────────
        self.bp_list_container = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(4),
        )

        # ── Assemble form ────────────────────────────────────────────────────
        form_layout.add_widget(self.bp_name_input)
        form_layout.add_widget(self.bp_amount_input)
        form_layout.add_widget(self.bp_type_segment)
        form_layout.add_widget(switch_layout)
        form_layout.add_widget(self.months_grid)
        form_layout.add_widget(self.bp_list_container)

        outer_scroll.add_widget(form_layout)

        self.bp_dialog = MDDialog(
            title="Bütçe Planlayıcı",
            type="custom",
            content_cls=outer_scroll,
            buttons=[
                MDFlatButton(text="KAPAT", on_release=lambda x: self.bp_dialog.dismiss()),
                MDRaisedButton(text="EKLE", on_release=self.save_budget_item),
            ],
        )
        self.bp_dialog.open()
        self.load_budget_list()

    def load_budget_list(self):
        # Works with both the new bp_list_container and the old bp_list (MDList)
        container = getattr(self, "bp_list_container", getattr(self, "bp_list", None))
        if container is None:
            return

        container.clear_widgets()

        from database.db import get_connection
        from kivymd.uix.button import MDIconButton
        from kivymd.uix.label import MDLabel
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.uix.widget import Widget
        import datetime

        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, type, name, amount FROM monthly_budget_plan WHERE target_month = ?",
                (target_month,),
            )
        except Exception:
            cursor.execute("SELECT id, type, name, amount FROM monthly_budget_plan")

        rows = cursor.fetchall()
        conn.close()

        for item_id, item_type, name, amount in rows:
            type_tr = "Gelir" if item_type == "income" else "Gider"
            amount_str = f"{amount:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

            # ── Row: [icon | text column | spacer | edit btn | delete btn] ──
            row = MDBoxLayout(
                orientation="horizontal",
                adaptive_height=True,
                spacing=dp(8),
                padding=[dp(12), dp(8), dp(8), dp(8)],
                size_hint_y=None,
                height=dp(56),
            )

            # Left icon
            left_icon = MDIconButton(
                icon="cash" if item_type == "income" else "cart",
                theme_text_color="Custom",
                text_color=(0.12, 0.53, 0.53, 1),
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(40), dp(40)),
            )

            # Text column
            text_col = MDBoxLayout(
                orientation="vertical",
                adaptive_height=True,
                size_hint_x=1,
                pos_hint={"center_y": 0.5},
            )
            name_lbl = MDLabel(
                text=name,
                adaptive_height=True,
                font_style="Body1",
            )
            sub_lbl = MDLabel(
                text=f"{type_tr} | {amount_str}",
                adaptive_height=True,
                font_style="Caption",
                theme_text_color="Secondary",
            )
            text_col.add_widget(name_lbl)
            text_col.add_widget(sub_lbl)

            # Edit button
            edit_btn = MDIconButton(
                icon="pencil",
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                on_release=lambda x, iid=item_id: self.edit_budget_item(iid),
            )

            # Delete button
            delete_btn = MDIconButton(
                icon="trash-can",
                theme_text_color="Custom",
                text_color=(0.9, 0.2, 0.2, 1),
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                on_release=lambda x, iid=item_id: self.delete_budget_item(iid),
            )

            row.add_widget(left_icon)
            row.add_widget(text_col)
            row.add_widget(edit_btn)
            row.add_widget(delete_btn)

            container.add_widget(row)
            # Simple separator line compatible with KivyMD 1.2.0
            sep = Widget(size_hint_y=None, height=dp(1))
            container.add_widget(sep)

    def save_budget_item(self, *args):
        # Strip ALL invisible characters — prevents the Admin[] artifact
        name = self.bp_name_input.text.strip().replace('\n', '').replace('\r', '')
        if not name:
            toast("Kalem adı boş olamaz!")
            return
        try:
            amount = float(self.bp_amount_input.text)
        except ValueError:
            toast("Geçerli bir tutar girin!")
            return

        is_propagate_active = self.bp_repeat_switch.active
        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)

        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("ALTER TABLE monthly_budget_plan ADD COLUMN target_month INTEGER DEFAULT 1")
        except Exception:
            pass

        if getattr(self, "editing_item_id", None):
            cursor.execute(
                """UPDATE monthly_budget_plan
                   SET type = ?, name = ?, amount = ?, target_month = ?
                   WHERE id = ?""",
                (self.bp_selected_type, name, amount, target_month, self.editing_item_id),
            )
            self.editing_item_id = None
        else:
            cursor.execute(
                """INSERT INTO monthly_budget_plan (type, name, amount, target_month)
                   VALUES (?, ?, ?, ?)""",
                (self.bp_selected_type, name, amount, target_month),
            )

        # Propagate to selected months
        if is_propagate_active:
            MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                      "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            for child in self.months_grid.children:
                if isinstance(child, MDRaisedButton) and getattr(child, "is_selected", False):
                    try:
                        m_int = MONTHS.index(child.text) + 1
                    except ValueError:
                        continue
                    cursor.execute(
                        """INSERT INTO monthly_budget_plan (type, name, amount, target_month)
                           VALUES (?, ?, ?, ?)""",
                        (self.bp_selected_type, name, amount, m_int),
                    )

        conn.commit()
        conn.close()

        self.bp_name_input.text = ""
        self.bp_amount_input.text = ""
        self.load_budget_list()
        self.generate_next_month_projection()
        
    def toggle_custom_month_button(self, btn):
        if not getattr(btn, 'is_selected', False):
            btn.is_selected = True
            btn.md_bg_color = (0.07, 0.38, 0.38, 1)  # Darker teal when selected
        else:
            btn.is_selected = False
            btn.md_bg_color = (0.12, 0.53, 0.53, 1)  # Original teal when unselected

    def delete_budget_item(self, item_id):
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monthly_budget_plan WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        self.load_budget_list()
        self.generate_next_month_projection()
        toast("Kalem silindi.")

    def edit_budget_item(self, item_id):
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT type, name, amount FROM monthly_budget_plan WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.editing_item_id = item_id
            self.bp_selected_type = row[0]
            self.bp_name_input.text = row[1]
            self.bp_amount_input.text = str(row[2])

if __name__ == "__main__":
    if _KivyWindow is None:
        print("No usable Kivy window backend detected; skipping GUI startup.")
        raise SystemExit(0)

    FinoraApp().run()