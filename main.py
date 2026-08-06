"""
Archlence KivyMD Application - Main Entry Point
"""

# =========================================================================
# 1. STANDARD LIBRARY IMPORTS
# =========================================================================
import os
import sys
import logging
import datetime
import faulthandler
import traceback as _traceback
import stat
import shutil
from pathlib import Path

# ── Konsol kodlaması: Türkçe metin Windows'ta süreci ÖLDÜRMESİN ─────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

from utils.app_paths import data_dir, log_dir, migrate_legacy_path, resource_dir

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(resource_dir())

# =========================================================================
# 2. CRASH REPORTING & EARLY CONFIGURATION
# =========================================================================
_CRASH_LOG_DIR = log_dir()
os.makedirs(_CRASH_LOG_DIR, exist_ok=True)
_CRASH_LOG_PATH = os.path.join(_CRASH_LOG_DIR, "crash.log")
_crash_log_file = open(_CRASH_LOG_PATH, "a", encoding="utf-8")
faulthandler.enable(file=_crash_log_file)


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    """Yakalanmamış Python istisnalarını crash.log'a zaman damgasıyla yazar."""
    try:
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(
                f"\n===== Unhandled exception at {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n"
            )
            _traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        # EXCEPTION-AUDIT: bilinçli geniş — crash günlüğünü YAZAN yol.
        # BİLEREK sessiz: burası crash günlüğünü YAZAN yol. `get_logger()`
        # çağırmak, log altyapısının kendisi bozuksa (disk dolu, izin hatası)
        # aynı hatayı yeniden tetikleyip özyinelemeye ya da ikinci bir
        # istisnaya yol açar. Aşağıdaki `sys.__excepthook__` zaten asıl
        # istisnayı stderr'e basar — tek iz kaybı olmaz.
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _log_unhandled_exception

if not os.environ.get("KIVY_NO_ARGS"):
    os.environ["KIVY_NO_ARGS"] = "1"

ARCHLENCE_HEADLESS = os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in (
    "1", "true", "yes",
)

if ARCHLENCE_HEADLESS:
    os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
    os.environ.setdefault("KIVY_DPI", "96")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("KIVY_WINDOW", "sdl2")

# =========================================================================
# 3. KIVY / KIVYMD IMPORTS
# =========================================================================
from kivy.config import Config

Config.set("kivy", "log_level", "error")
Config.set("kivy", "log_maxfiles", 2)
Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.metrics import dp
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.storage.jsonstore import JsonStore
from kivy.properties import (
    StringProperty,
    ColorProperty,
)

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout

# Graceful Window Mocking
try:
    from kivy.core.window import Window as _KivyWindow
    from kivy.core.window import Window
    if Window is None:
        raise RuntimeError(
            "Kivy herhangi bir pencere sağlayıcısı bulamadı "
            "(egl_rpi/sdl2/x11 hiçbiri kullanılamadı)."
        )
except (ImportError, RuntimeError):
    if not ARCHLENCE_HEADLESS:
        raise
    _KivyWindow = None

    class Window(object):
        size = (800, 600)

        @staticmethod
        def bind(*args, **kwargs):
            return None

        @staticmethod
        def unbind(*args, **kwargs):
            return None


# Graceful KivyMD Mocking
try:
    from kivymd.app import MDApp
    from utils.toast import toast
    from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
    from kivymd.uix.dialog import MDDialog
    from kivymd.uix.menu import MDDropdownMenu
    from kivymd.uix.textfield import MDTextField
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.gridlayout import MDGridLayout
    from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
    from kivymd.uix.list import (
        TwoLineIconListItem,
        IconLeftWidget,
        TwoLineAvatarIconListItem,
        IRightBodyTouch,
    )
    from kivymd.uix.label import MDLabel, MDIcon
    from kivymd.uix.screen import MDScreen
except (ImportError, AttributeError) as exc:
    if not ARCHLENCE_HEADLESS:
        raise
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

    def toast(*args, **kwargs):
        return None


# =========================================================================
# 4. LOCAL MODULE IMPORTS
# =========================================================================
from utils.crypto import decrypt, key_protection_status
from database.init_db import initialize_database
from database.db import (
    managed_connection,
    COMPLETED_TX,
    COMPLETED_TX_T,
    migrate_legacy_database_location,
)

from ui.charts import (
    HorizontalBarChart,
    ScenarioComparisonChart,
)
from ui.components import (
    CategorySettingItem,
)
from ui.theme import (
    apply_premium_theme,
    apply_standard_theme,
    refresh_card_theme,
    apply_dark_surface_tokens,
    restyle_text_fields,
    _refresh,
)
import ui.theme as ftheme
from ui.i18n import tr as translate, set_language as set_active_language
from utils.currency import format_try
from utils.errors import FinancialDataIntegrityError
from utils.version import APP_VERSION

# Destek/geri bildirim kanalı. README, PKGBUILD ve release notlarındaki
# adresle aynı; tek yerde durur ki depo taşınırsa burada da güncellensin.
ARCHLENCE_GITHUB_URL = "https://github.com/superuser-d0/archlence"

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
from mixins.scenario_mixin import ScenarioMixin
from mixins.subscription_mixin import SubscriptionMixin
from mixins.pending_mixin import PendingMixin
from mixins.calendar_mixin import CalendarMixin
from security.security_service import LoginThrottle, PasswordPolicy, SecurityService
from services.backup_service import decrypt_recovery_material
from services.history_service import write_daily_snapshot

# =========================================================================
# 5. CONSTANTS & SYSTEM PREP
# =========================================================================
SECRET_KEY = "fi" + "nora_secure_2026"

def _resolve_config_path():
    override = os.environ.get("ARCHLENCE_CONFIG_PATH")
    if override:
        return override

    target_path = os.path.join(data_dir(), "archlence_config.json")
    legacy_path = os.path.join(_APP_DIR, "archlence_config.json")
    legacy_finora_path = os.path.join(_APP_DIR, "fi" + "nora_config.json")

    if not migrate_legacy_path(legacy_path, target_path):
        migrate_legacy_path(legacy_finora_path, target_path)
    return target_path

def _resolve_savings_store_path():
    legacy_path = os.path.join(_APP_DIR, "savings_goals.json")
    target_path = os.path.join(data_dir(), "savings_goals.json")
    migrate_legacy_path(legacy_path, target_path)
    return target_path


def setup_appimage_desktop_integration():
    """
    AppImage olarak çalıştırıldığında kendini Linux başlat menüsüne (.local/share/applications),
    masaüstüne ve ikon kütüphanesine otomatik olarak entegre eder.
    """
    appimage_path = os.environ.get("APPIMAGE")

    if not appimage_path:
        return

    applications_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir = Path.home() / "Desktop"
    icons_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"

    if not desktop_dir.exists():
        desktop_dir = Path.home() / "Masaüstü"
        if not desktop_dir.exists():
            desktop_dir = None

    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    # İkon Kopyalama Adımı (shutil entegre edildi)
    source_icon = Path(resource_dir()) / "assets" / "icon.png"
    target_icon = icons_dir / "archlence.png"

    if source_icon.exists() and not target_icon.exists():
        try:
            shutil.copy2(source_icon, target_icon)
        except OSError as e:
            from utils.logging_config import get_logger
            get_logger().exception("İkon sisteme kopyalanamadı")

    desktop_file_name = "archlence.desktop"
    app_menu_path = applications_dir / desktop_file_name

    desktop_content = f"""[Desktop Entry]
Name=Archlence
Comment=Local-First Personal Finance Manager
Exec="{appimage_path}"
Icon=archlence
Terminal=false
Type=Application
Categories=Office;Finance;
StartupNotify=true
"""

    try:
        with open(app_menu_path, "w", encoding="utf-8") as f:
            f.write(desktop_content)
        app_menu_path.chmod(app_menu_path.stat().st_mode | stat.S_IEXEC)
    except OSError as e:
        from utils.logging_config import get_logger
        get_logger().exception("Başlat menüsü kısayolu oluşturulamadı")

    if desktop_dir:
        desktop_shortcut_path = desktop_dir / desktop_file_name
        if not desktop_shortcut_path.exists():
            try:
                with open(desktop_shortcut_path, "w", encoding="utf-8") as f:
                    f.write(desktop_content)
                desktop_shortcut_path.chmod(desktop_shortcut_path.stat().st_mode | stat.S_IEXEC)
            except OSError as e:
                from utils.logging_config import get_logger
                get_logger().exception("Masaüstü simgesi oluşturulamadı")


# =========================================================================
# 6. MAIN APPLICATION CLASS
# =========================================================================
class ArchlenceApp(
    MDApp,  # type: ignore
    AssetMixin,
    DebtMixin,
    CalculatorMixin,
    TransactionMixin,  # type: ignore
    BudgetMixin,
    SavingsMixin,
    RecurringMixin,
    MigrationMixin,
    AccountMixin,
    InsightsMixin,
    HistoryMixin,
    ScenarioMixin,
    SubscriptionMixin,
    PendingMixin,
    CalendarMixin,
):
    title = "Archlence"
    icon = "assets/icon.png"

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
    language = StringProperty("tr")
    key_protection_text = StringProperty("Anahtar koruması denetleniyor…")
    version = StringProperty(APP_VERSION)

    _wealth_visible = True
    _liquid_balance_cache = 0.0
    _assets_cache = []

    # -------------------------------------------------------------------------
    # Lifecycle & Initialization
    # -------------------------------------------------------------------------
    @staticmethod
    def _warm_crypto_key_in_background():
        import threading
        from utils.crypto import DEFAULT_PASSWORD, _get_aead_key, _get_key

        def _warm():
            try:
                _get_key(DEFAULT_PASSWORD)
                _get_aead_key()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Şifreleme anahtarı arka planda ısıtılamadı")

        thread = threading.Thread(target=_warm, daemon=True)
        thread.start()
        return thread

    def build(self):
        try:
            setup_appimage_desktop_integration()
        except (OSError, RuntimeError) as e:
            from utils.logging_config import get_logger
            get_logger().exception("Appimage entegrasyonu hatası")

        Clock.max_iteration = 50
        from services.background_task_manager import BackgroundTaskManager

        self.background_tasks = BackgroundTaskManager(
            schedule=lambda callback: Clock.schedule_once(
                lambda _dt: callback(), 0
            )
        )
        self._warm_crypto_key_in_background()
        migrate_legacy_database_location()
        initialize_database()
        self.store = JsonStore(_resolve_savings_store_path())
        if self.store.exists("goals"):
            self.savings_goals = self.store.get("goals")["data"]

        self.theme_cls.theme_style_switch_animation = False
        self.config_store = JsonStore(_resolve_config_path())
        saved_style = "Light"
        if self.config_store.exists("display"):
            saved_style = self.config_store.get("display").get("style", "Light")
        self.theme_cls.theme_style = (
            saved_style if saved_style in ("Light", "Dark") else "Light"
        )

        language = "tr"
        if self.config_store.exists("language"):
            language = self.config_store.get("language").get("code", "tr")
        self.language = set_active_language(language)
        protection = key_protection_status()
        self.key_protection_text = (
            protection.method
            if protection.secure_store
            else f"{protection.method} — {protection.warning}"
        )

        pref = "standard"
        if self.config_store.exists("theme"):
            pref = self.config_store.get("theme").get("name", "standard")

        self.apply_theme(pref, persist=False)
        Builder.load_file("ui/tools.kv")
        root = Builder.load_file("ui/dashboard.kv")
        root.ids.screen_manager.current = self.authentication_screen()
        return root

    def tr(self, text, language=None):
        return translate(text, language or self.language)

    def set_language(self, code, persist=True):
        self.language = set_active_language(code)
        if persist:
            try:
                self.config_store.put("language", code=self.language)
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Dil tercihi kaydedilemedi")

        if self.root:
            chart_box = self.root.ids.get("chart_master_box")
            if chart_box is not None:
                pie_empty = getattr(chart_box, "_pie_empty_label", None)
                trend_empty = getattr(chart_box, "_trend_empty_label", None)
                if pie_empty is not None:
                    pie_empty.text = self.tr("₺0\nVeri Yok")
                if trend_empty is not None:
                    trend_empty.text = self.tr("Veri Yok")
            Clock.schedule_once(lambda dt: self.refresh_dashboard_data(), 0)
            Clock.schedule_once(lambda dt: self.load_active_debts(), 0.05)
            Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0.1)
            Clock.schedule_once(self._refresh_language_widgets, 0)

    def _refresh_language_widgets(self, *args):
        if not self.root:
            return
        nav = self.root.ids.get("bottom_nav")
        if nav is not None:
            try:
                tabs = nav.ids.tab_manager.screens
            except (AttributeError, KeyError):
                tabs = []
            for tab in tabs:
                header = getattr(tab, "header", None)
                try:
                    header.ids._label.text = tab.text
                    header.ids._label.texture_update()
                    header.canvas.ask_update()
                except (AttributeError, KeyError):
                    pass
        self._refresh_text_textures()

    def open_language_dialog(self):
        dialog = MDDialog(
            title=self.tr("Uygulama Dili"),
            buttons=[
                MDFlatButton(
                    text=translate("TÜRKÇE"),
                    on_release=lambda _btn: (self.set_language("tr"), dialog.dismiss()),
                ),
                MDRaisedButton(
                    text=translate("ENGLISH"),
                    on_release=lambda _btn: (self.set_language("en"), dialog.dismiss()),
                ),
            ],
        )
        dialog.open()

    def on_start(self):
        self._normalize_card_shadows()

        tool_card_bindings = (
            ("budget_tool_card", self.show_budget_planner),
            ("calendar_tool_card", self.open_calendar_view),
            ("calc_basic_tool_card", lambda: self.open_calculator("basic")),
            ("calc_interest_tool_card", lambda: self.open_calculator("interest")),
            ("calc_compound_tool_card", lambda: self.open_calculator("compound")),
            ("calc_loan_tool_card", lambda: self.open_calculator("loan")),
            ("calc_savings_goal_tool_card",
                lambda: self.open_calculator("savings_goal")),
            ("scenario_tool_card", self.open_scenario_sandbox),
            ("reset_data_tool_card", self.confirm_delete_all_data),
        )
        for card_id, callback in tool_card_bindings:
            try:
                ftheme.bind_card_tap(self.root.ids[card_id], callback)
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception(f"'{card_id}' karesi tıklanabilir yapılamadı")

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("peewee").setLevel(logging.CRITICAL)

        self.purge_logs()
        self.vacuum_database()

        from services.asset_service import start_data_warmup

        start_data_warmup()

        self.write_daily_balance_snapshot()
        self.setup_dynamic_months()
        self.safe_refresh_charts()
        self.load_recent_transactions("Günlük")
        self.generate_financial_advice()
        self.load_active_debts()
        self.load_active_assets()
        self.load_asset_history()
        self.process_due_auto_deductions()

    def on_stop(self):
        try:
            self.stop_active_assets_refresh()
        except Exception as exc:
            from utils.logging_config import get_logger
            get_logger().exception("Arka plan tazeleme durdurulamadı")
        if hasattr(self, "background_tasks"):
            self.background_tasks.shutdown(wait=False)

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
                if not hasattr(self, "config_store"):
                    self.config_store = JsonStore(_resolve_config_path())
                self.config_store.put("theme", name=theme_name)
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Tema tercihi kaydedilemedi")

    def toggle_theme(self, is_active):
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
                try:
                    self.config_store.put("display", style=desired_style)
                except Exception as e:
                    from utils.logging_config import get_logger
                    get_logger().exception("Görünüm tercihi kaydedilemedi")
                Clock.schedule_once(self._after_theme_switch, 0)
            finally:
                self._applying_theme_style = False

        self._pending_theme_switch = Clock.schedule_once(_switch_theme, 0.12)

    def _after_theme_switch(self, *args):
        try:
            _refresh(self.theme_cls)
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Tema sonrası yüzey renkleri tazelenemedi")
        self._normalize_card_shadows()
        self._resync_text_fields()
        # EXCEPTION-AUDIT: bilinçli geniş — canlı widget ağacı, açık
        # gözlemci yüzeyi; kozmetik kazanç, çökme riski.
        # BİLEREK geniş: bu döngü CANLI widget ağacının tamamını gezer; içinde
        # KV'de tanımlı ve üçüncü parti widget'lar da var. Kivy'de özellik
        # ataması gözlemcileri EŞZAMANLI çalıştırdığı için tip kümesi kapalı
        # değil. Buradan kaçan bir istisna tema geçişini komple çökertir,
        # kazancı ise yalnızca kozmetik. Sessiz `pass` yerine sayaçla
        # loglanıyor: etiket başına spam üretmeden görünür oluyor.
        failures = []
        for widget in self._all_widgets():
            if isinstance(widget, MDLabel):
                try:
                    widget.on_theme_text_color(widget, widget.theme_text_color)
                # EXCEPTION-AUDIT: bilinçli geniş — yukarıdaki gerekçe.
                except Exception as exc:
                    failures.append(exc)
        if failures:
            from utils.logging_config import get_logger
            get_logger().warning(
                "Tema sonrası %d etiketin metin rengi tazelenemedi; ilki: %r",
                len(failures), failures[0])
        Clock.schedule_once(self._rebuild_after_theme_layout, 0.2)

    def _rebuild_after_theme_layout(self, *args):
        if self.root:
            chart_box = self.root.ids.get("chart_master_box")
            if chart_box is not None and hasattr(chart_box, "refresh_theme"):
                try:
                    chart_box.refresh_theme()
                except Exception as exc:
                    from utils.logging_config import get_logger
                    get_logger().exception("Tema sonrası grafikler yenilenemedi")
            for widget in self.root.walk():
                if isinstance(widget, HorizontalBarChart):
                    try:
                        widget.update_chart()
                    except Exception as exc:
                        from utils.logging_config import get_logger
                        get_logger().exception("Tema sonrası çubuk grafik yenilenemedi")
                elif isinstance(widget, ScenarioComparisonChart):
                    try:
                        widget.draw_immediate()
                    except Exception as exc:
                        from utils.logging_config import get_logger
                        get_logger().exception("Tema sonrası senaryo grafiği yenilenemedi")
        if hasattr(self, "render_accounts"):
            try:
                self.render_accounts()
            except Exception as exc:
                from utils.logging_config import get_logger
                get_logger().exception("Tema sonrası kartlar yenilenemedi")
        self._normalize_card_shadows()
        Clock.schedule_once(self._refresh_text_textures, 0.05)

    def _refresh_text_textures(self, *args):
        # EXCEPTION-AUDIT: bilinçli geniş — gerekçe
        # `_after_theme_switch`'teki döngüyle aynı.
        # Ölçülen gerçek hata: `font_name` diskte yoksa `texture_update()`
        # OSError veriyor ("Label: File '...' not found"). Eskiden bu tamamen
        # sessizdi; paketlenmiş derlemede eksik bir font, hiçbir iz bırakmadan
        # tüm metinlerin yeniden çizilmemesine yol açardı.
        failures = []
        for widget in self._all_widgets():
            if isinstance(widget, MDLabel):
                try:
                    widget.texture_update()
                    widget.canvas.ask_update()
                # EXCEPTION-AUDIT: bilinçli geniş — yukarıdaki gerekçe.
                except Exception as exc:
                    failures.append(exc)
        if failures:
            from utils.logging_config import get_logger
            get_logger().warning(
                "Tema sonrası %d etiketin dokusu yenilenemedi; ilki: %r",
                len(failures), failures[0])

    def _normalize_card_shadows(self, *args):
        if not self.root:
            return

        from kivymd.uix.card import MDCard

        # EXCEPTION-AUDIT: bilinçli geniş — gerekçe
        # `_after_theme_switch`'teki döngüyle aynı.
        failures = []
        for widget in self._all_widgets():
            if isinstance(widget, MDCard):
                try:
                    if hasattr(widget, "_archlence_tint"):
                        refresh_card_theme(widget, self.theme_cls)
                    widget.elevation = 0
                    if hasattr(widget, "shadow_softness"):
                        widget.shadow_softness = 0
                    if hasattr(widget, "shadow_color"):
                        widget.shadow_color = (0, 0, 0, 0)
                # EXCEPTION-AUDIT: bilinçli geniş — yukarıdaki gerekçe.
                except Exception as exc:
                    failures.append(exc)
        if failures:
            from utils.logging_config import get_logger
            get_logger().warning(
                "%d kartın gölge/renk normalizasyonu yapılamadı; ilki: %r",
                len(failures), failures[0])

    def _resync_text_fields(self):
        if not self.root:
            return
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

        log_dir = os.path.expanduser("~/.kivy/logs")
        if not os.path.exists(log_dir):
            return

        total_size = sum(
            os.path.getsize(os.path.join(log_dir, f))
            for f in os.listdir(log_dir)
            if os.path.isfile(os.path.join(log_dir, f))
        )
        if total_size > 5 * 1024 * 1024:
            for f in glob.glob(os.path.join(log_dir, "*.txt")):
                try:
                    os.remove(f)
                except Exception:
                    from utils.logging_config import get_logger
                    get_logger().exception("Eski Kivy log dosyası silinemedi")
            print("Purged Kivy logs due to size > 5MB")

    def vacuum_database(self):
        import threading

        def _work():
            try:
                with managed_connection() as conn:
                    conn.execute("VACUUM")
                    conn.commit()
                print("Database VACUUM completed.")
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("VACUUM failed")

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return thread

    def write_daily_balance_snapshot(self):
        try:
            write_daily_snapshot()
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Günlük bakiye snapshot'ı yazılamadı")

    # -------------------------------------------------------------------------
    # Metrics & Dashboard Updates
    # -------------------------------------------------------------------------
    def update_metrics_and_goals(self):
        def _error(exc):
            if isinstance(exc, FinancialDataIntegrityError):
                from utils.logging_config import log_integrity_error
                error_id = log_integrity_error(exc)
                self._apply_dashboard_integrity_error(error_id)
            else:
                from utils.logging_config import get_logger

                get_logger().exception(
                    "Dashboard metrik görevi başarısız.",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

        self.background_tasks.submit(
            "dashboard-metrics",
            lambda cancel_event: self._compute_dashboard_metrics(),
            on_success=self._apply_dashboard_metrics,
            on_error=_error,
            replace=True,
            is_target_alive=lambda: bool(self.root),
        )

    def _compute_dashboard_metrics(self):
        # ÖNBELLEK. Bu fonksiyonun maliyetinin ~%99'u AES-GCM şifre çözme
        # (10.000 işlemli bir profilde 10.800 `decrypt` çağrısı, ~318 ms).
        # Tutarlar şifreli TEXT olduğu için SQL'de toplanamıyor; tek çare
        # her satırı Python'da çözmek. Dolayısıyla asıl kazanç çözmeyi
        # hızlandırmak değil, GEREKMEDİKÇE HİÇ YAPMAMAK.
        #
        # Anahtardaki üç bileşenin her biri gerekli:
        #   * revision — bakiyeye dokunan her yazım `record_balance_event`
        #     üzerinden artırır (defter değişmezi), ayrıca kategori
        #     `importance` değişimi (bkz. mark_financial_data_changed).
        #   * filtre   — "Bugün/1 Hafta/…" dönem toplamlarını değiştirir.
        #   * tarih    — gün dönünce "Bugün" penceresi kayar, veri
        #     değişmemiş olsa bile sonuç eskir.
        from services.asset_service import get_financial_data_revision

        cache_key = (
            get_financial_data_revision(),
            getattr(self, "home_filter", "Bugün"),
            datetime.date.today().isoformat(),
        )
        cached = getattr(self, "_dashboard_metrics_cache", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]

        with managed_connection() as conn:
            rows = conn.execute(f"""
                SELECT t.id, t.amount, t.type,
                       IFNULL(c.importance, 'extra') AS importance
                FROM transactions t
                LEFT JOIN categories c ON t.category = c.name
                WHERE {COMPLETED_TX_T}
            """).fetchall()

        from services.financial_summary_service import summarize_transactions
        summary = summarize_transactions(rows)
        total_income = summary.total_income
        total_expense = summary.total_expense
        from services.queries import DashboardService

        from utils.financial_decimal import decimal_from

        # Accounts are the authoritative wallet balance.  Reconstructing the
        # total from income/expense rows misses non-transaction ledger moves
        # such as savings deposits and can diverge from the Accounts screen.
        total_balance = decimal_from(DashboardService.get_total_balance())

        filter_text = getattr(self, "home_filter", "Bugün")
        from services.dashboard_period_service import (
            calculate_balance_change,
            period_bounds,
        )
        period_start, period_end = period_bounds(filter_text)

        with managed_connection() as conn2:
            if period_start is None:
                period_rows = conn2.execute(
                    f"SELECT id, amount, type, 'extra' AS importance "
                    f"FROM transactions WHERE {COMPLETED_TX}"
                ).fetchall()
            else:
                period_rows = conn2.execute(
                    f"SELECT id, amount, type, 'extra' AS importance "
                    f"FROM transactions WHERE date(transaction_date) BETWEEN ? AND ?"
                    f" AND {COMPLETED_TX}",
                    (period_start.isoformat(), period_end.isoformat()),
                ).fetchall()
        period = summarize_transactions(period_rows)
        period_income = period.total_income
        period_expense = period.total_expense
        period_net = period.net

        with managed_connection() as conn_pred:
            rows = conn_pred.execute(f"""
                SELECT id, type, amount, 'extra' AS importance
                FROM transactions
                WHERE date(transaction_date) >=
                      date('now', '-30 days', 'localtime')
                  AND {COMPLETED_TX}
            """).fetchall()
        recent = summarize_transactions(rows)
        daily_income = recent.total_income / 30
        daily_expense = recent.total_expense / 30

        try:
            period_change = calculate_balance_change(
                filter_text,
                total_balance,
                today=period_end,
            )
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Dönem bakiye değişimi hesaplanamadı")
            period_change = {
                "nominal_change": None,
                "percentage": None,
            }

        metrics = {
            "filter_text": filter_text,
            "total_income": total_income,
            "total_expense": total_expense,
            "total_balance": total_balance,
            "period_income": period_income,
            "period_expense": period_expense,
            "period_net": period_net,
            "balance_change": period_change["nominal_change"],
            "projection_daily_income": daily_income,
            "projection_daily_expense": daily_expense,
            "change_rate": period_change["percentage"],
        }
        # Yalnızca HATASIZ tamamlanan hesap önbelleğe alınır: yukarıdaki
        # `summarize_transactions` bozuk bir kayıtta
        # `FinancialDataIntegrityError` fırlatıyor ve o durumda buraya hiç
        # gelinmiyor — yani hatalı bir sonuç asla önbelleğe girmez.
        self._dashboard_metrics_cache = (cache_key, metrics)
        return metrics

    def _apply_dashboard_integrity_error(self, error_id):
        if not self.root:
            return
        unavailable = translate("Bazı kayıtlar okunamadığı için gösterilemiyor")
        for widget_id in (
            "home_total_balance",
            "total_card_amount",
            "period_income_label",
            "period_expense_label",
            "period_net_label",
            "metric_val_income",
            "metric_val_expense",
            "metric_val_savings",
            "metric_val_trend",
        ):
            widget = self.root.ids.get(widget_id)
            if widget is not None:
                widget.text = "—"
        toast(f"{unavailable} (Hata: {error_id})")

    def _apply_dashboard_metrics(self, m):
        # A replaced background job may still finish after the user chooses a
        # new filter.  Never let its old label/value pair overwrite the active
        # period's UI.
        if m.get("filter_text") != getattr(self, "home_filter", "Bugün"):
            return
        if not self.root:
            return

        filter_text = m["filter_text"]
        total_balance = m["total_balance"]
        self._scenario_base_metrics = {
            "base_balance": total_balance,
            "base_daily_income": m.get("projection_daily_income", 0.0),
            "base_daily_expense": m.get("projection_daily_expense", 0.0),
        }
        period_net = m["period_net"]
        balance_change = m.get("balance_change")

        def _set_changed(widget, prop, value):
            if getattr(widget, prop, None) != value:
                setattr(widget, prop, value)

        try:

            def _fmt(v):
                return (
                    f"₺{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )

            _set_changed(
                self.root.ids.period_income_label, "text", _fmt(m["period_income"])
            )
            _set_changed(
                self.root.ids.period_expense_label, "text", _fmt(m["period_expense"])
            )

            net_lbl = self.root.ids.period_net_label
            _set_changed(
                net_lbl,
                "text",
                ("+ " if period_net >= 0 else "- ") + _fmt(abs(period_net)),
            )
            if period_net > 0:
                net_color = ftheme.accent(self.theme_cls, "green")
            elif period_net < 0:
                net_color = ftheme.accent(self.theme_cls, "red")
            else:
                net_color = ftheme.accent(self.theme_cls, "muted")
            _set_changed(net_lbl, "text_color", net_color)

            formatted_balance = (
                f"{total_balance:,.2f} ₺".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            _set_changed(self.root.ids.home_total_balance, "text", formatted_balance)
            _set_changed(self.root.ids.total_card_amount, "text", formatted_balance)

            try:
                warning_row = self.root.ids.negative_balance_warning
                if total_balance < 0:
                    _set_changed(warning_row, "height", dp(22))
                    _set_changed(warning_row, "opacity", 1)
                else:
                    _set_changed(warning_row, "height", 0)
                    _set_changed(warning_row, "opacity", 0)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Negatif bakiye uyarı satırı güncellenemedi")

            localized_filter = translate(filter_text)
            _set_changed(
                self.root.ids.home_change_title,
                "text",
                f"{translate('Değişim')} ({localized_filter})",
            )
            _set_changed(self.root.ids.today_card_title, "text", localized_filter)

            displayed_change = period_net if balance_change is None else balance_change
            prefix = "+" if displayed_change > 0 else ""
            formatted_period = (
                f"{displayed_change:,.2f} ₺".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            _set_changed(
                self.root.ids.today_card_amount, "text", f"{prefix}{formatted_period}"
            )

            if total_balance > 0:
                self.home_circle_color = (0.18, 0.8, 0.25, 1)
            elif total_balance < 0:
                self.home_circle_color = (0.9, 0.2, 0.2, 1)
            else:
                self.home_circle_color = (0.5, 0.5, 0.5, 0.2)

            if hasattr(self.root.ids, "balance_circle"):
                self.root.ids.balance_circle.canvas.ask_update()

            try:
                self._liquid_balance_cache = total_balance
                if not hasattr(self, "_assets_cache") or not self._assets_cache:
                    self._update_wealth_label(total_balance, None)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Servet etiketi güncellenemedi")

            savings_key = (
                round(total_balance, 2),
                repr(getattr(self, "savings_goals", [])),
            )
            if savings_key != getattr(self, "_last_savings_render_key", None):
                self._last_savings_render_key = savings_key
                Clock.schedule_once(
                    lambda dt: self.render_savings_goals(total_balance), 0
                )

        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Dashboard metrikleri uygulanamadı")

        if "metric_val_income" in self.root.ids:
            total_income = m["total_income"]
            total_expense = m["total_expense"]

            self.root.ids.metric_val_income.text = (
                f"{total_income:,.2f} ₺".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            self.root.ids.metric_val_expense.text = (
                f"{total_expense:,.2f} ₺".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

            if total_income > 0:
                savings_rate = ((total_income - total_expense) / total_income) * 100
                self.root.ids.metric_val_savings.text = f"%{savings_rate:.1f}".replace(
                    ".", ","
                )
            else:
                self.root.ids.metric_val_savings.text = "%0,0"

            if "metric_val_trend" in self.root.ids:
                aim_text = (
                    f"{total_income:,.0f} ₺".replace(",", ".")
                    if total_income > 0
                    else translate("Veri Yok")
                )
                self.root.ids.metric_val_trend.text = aim_text

            for card_id in (
                "metric_card_income",
                "metric_card_expense",
                "metric_card_savings",
                "metric_card_trend",
            ):
                card = self.root.ids.get(card_id)
                if card is not None:
                    card.opacity = 1

        self._apply_change_rate(m.get("change_rate"))

    def _fmt_tr(self, value: float) -> str:
        return format_try(value)

    def _update_wealth_label(self, total_wealth: float, today_pnl):
        try:
            lbl = self.root.ids.wealth_amount_label
            pnl = self.root.ids.wealth_daily_pnl_label
            eye = self.root.ids.wealth_eye_btn

            if not self._wealth_visible:
                lbl.text = "₺***.***,**"
                pnl.text = ""
                eye.icon = "eye-off-outline"
                return

            eye.icon = "eye-outline"
            lbl.text = self._fmt_tr(total_wealth)

            if today_pnl is None:
                pnl.text = translate("Varlık fiyatları hesaplanıyor...")
                pnl.text_color = ftheme.accent(self.theme_cls, "muted")
            else:
                pct = (
                    (today_pnl / (total_wealth - today_pnl) * 100)
                    if (total_wealth - today_pnl) != 0
                    else 0.0
                )
                sign = "+" if today_pnl >= 0 else "-"
                c_sign = "+" if pct >= 0 else "-"
                pnl.text = translate(
                    f"{sign}{self._fmt_tr(abs(today_pnl))} ({c_sign}{abs(pct):.2f}%) Bugün"
                )

                if today_pnl > 0:
                    pnl.text_color = ftheme.accent(self.theme_cls, "green")
                elif today_pnl < 0:
                    pnl.text_color = ftheme.accent(self.theme_cls, "red")
                else:
                    pnl.text_color = ftheme.accent(self.theme_cls, "muted")
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Günlük kâr/zarar rengi uygulanamadı")

    def toggle_wealth_visibility(self):
        self._wealth_visible = not self._wealth_visible
        self.update_wealth_card(
            self._assets_cache,
            getattr(self, "_today_liquid_delta_cache", 0.0),
        )

    def _compute_today_liquid_delta(self):
        with managed_connection() as conn_t:
            rows = conn_t.execute(
                "SELECT id, amount, type, 'extra' AS importance "
                "FROM transactions "
                "WHERE date(transaction_date) = date('now', 'localtime') "
                f"AND {COMPLETED_TX}"
            ).fetchall()
        from services.financial_summary_service import summarize_transactions

        return summarize_transactions(rows).net

    def update_wealth_card(self, enriched_assets, today_liquid_delta=None):
        from utils.financial_decimal import decimal_from

        liquid_cash = decimal_from(
            getattr(self, "_liquid_balance_cache", 0)
        )

        portfolio_live = sum(
            (
                decimal_from(a["total_value"])
                for a in enriched_assets
                if a.get("total_value") is not None
            ),
            decimal_from(0),
        )
        total_wealth = liquid_cash + portfolio_live

        asset_pnl = sum(
            (
                decimal_from(a["pnl_amount"])
                for a in enriched_assets
                if a.get("pnl_amount") is not None
            ),
            decimal_from(0),
        )

        if today_liquid_delta is None and enriched_assets:
            today_liquid_delta = self._compute_today_liquid_delta()
        if today_liquid_delta is None:
            today_liquid_delta = decimal_from(0)
        else:
            today_liquid_delta = decimal_from(today_liquid_delta)

        self._today_liquid_delta_cache = today_liquid_delta

        today_pnl = asset_pnl + today_liquid_delta
        self._update_wealth_label(total_wealth, today_pnl if enriched_assets else None)

    # -------------------------------------------------------------------------
    # Charting & Calculations
    # -------------------------------------------------------------------------
    def safe_refresh_charts(self):
        self.refresh_dashboard_data()

    def calculate_monthly_change_rate(self):
        """Compatibility wrapper for callers that still use the old name."""
        from services.dashboard_period_service import calculate_balance_change
        from services.queries import DashboardService

        result = calculate_balance_change(
            getattr(self, "home_filter", "Bugün"),
            DashboardService.get_total_balance(),
        )
        return result["percentage"]

    def _apply_change_rate(self, rate):
        try:
            if self.root and "change_rate_label" in self.root.ids:
                label = self.root.ids.change_rate_label
                if rate is None:
                    label.text = "—"
                    label.text_color = ftheme.accent(self.theme_cls, "muted")
                elif rate > 0:
                    label.text = f"+%{rate:.1f}"
                    label.text_color = ftheme.accent(self.theme_cls, "green")
                elif rate < 0:
                    label.text = f"-%{abs(rate):.1f}"
                    label.text_color = ftheme.accent(self.theme_cls, "red")
                else:
                    label.text = "%0.0"
                    label.text_color = ftheme.accent(self.theme_cls, "muted")
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Error updating change rate UI")

    # -------------------------------------------------------------------------
    # List & Navigation Interactions
    # -------------------------------------------------------------------------
    _HOME_FILTER_KEYS = ("Bugün", "1 Hafta", "1 Ay", "1 Yıl", "Hayat Boyu")

    def change_home_filter(self, text):
        canonical = next(
            (key for key in self._HOME_FILTER_KEYS if self.tr(key) == text),
            text,
        )
        self.home_filter = canonical
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
            bg_inactive = ftheme.inactive_control_bg(self.theme_cls)

            for name, btn in buttons.items():
                if name == getattr(self, "home_filter", "Bugün"):
                    btn.md_bg_color = self.theme_cls.primary_color
                    btn.text_color = ftheme.on_primary(self.theme_cls)
                else:
                    btn.md_bg_color = bg_inactive
                    btn.text_color = ftheme.inactive_control_text(self.theme_cls)

            # The compact control above the summary cards is a separate KivyMD
            # widget. Programmatic changes (lower filter row, capture tooling,
            # restored state) do not move its switch automatically.
            segment_items = {
                "Bugün": self.root.ids.segment_filter_today,
                "1 Hafta": self.root.ids.segment_filter_week,
                "1 Ay": self.root.ids.segment_filter_month,
                "1 Yıl": self.root.ids.segment_filter_year,
            }
            selected = segment_items.get(getattr(self, "home_filter", "Bugün"))
            segmented = self.root.ids.home_period_control
            if (
                selected is not None
                and segmented.current_active_segment is not selected
            ):
                segmented.current_active_segment = selected
                segmented.animation_segment_switch(selected)
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Filtre butonları görünümü eşitlenemedi")

    def update_sg_period(self, segment, item):
        self.sg_period = item.text

    def refresh_dashboard_data(self, list_filter=None, reuse_if_fresh=False):
        from services.asset_service import financial_chart_cache_key

        dashboard_key = financial_chart_cache_key(
            getattr(self, "home_filter", "Bugün")
        )
        if (
            reuse_if_fresh
            and getattr(self, "_dashboard_rendered_cache_key", None)
            == dashboard_key
        ):
            return False

        try:
            self.update_metrics_and_goals()
            if self.root and "chart_master_box" in self.root.ids:
                self.root.ids.chart_master_box.refresh_dashboard(
                    getattr(self, "home_filter", "Bugün")
                )
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Error updating UI metrics")

        try:
            self.refresh_insights()
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Error refreshing insights")

        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")
        self._refresh_recent_transactions(list_filter)
        self._dashboard_rendered_cache_key = dashboard_key
        return True

    # -------------------------------------------------------------------------
    # [ MADDE 1 DÜZELTMESİ ]: Bozuk İşlemlerin Yakalanması ve UI'a İletilmesi
    # -------------------------------------------------------------------------
    def _refresh_recent_transactions(self, list_filter=None):
        import threading

        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")

        def fetch_task():
            try:
                select_body = (
                    "SELECT type, category, amount, description,"
                    " strftime('%d/%m %H:%M', transaction_date) FROM transactions"
                )
                date_conds = {
                    "Günlük": "date(transaction_date) = date('now', 'localtime')",
                    "Bugün": "date(transaction_date) = date('now', 'localtime')",
                    "1 Hafta": "date(transaction_date) >= date('now', '-7 days', 'localtime')",
                    "Haftalık": "date(transaction_date) >= date('now', '-7 days', 'localtime')",
                    "1 Ay": "strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime')",
                    "Aylık": "strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime')",
                }
                where_parts = [COMPLETED_TX]
                date_cond = date_conds.get(list_filter)
                if date_cond:
                    where_parts.insert(0, date_cond)
                query = (
                    f"{select_body} WHERE {' AND '.join(where_parts)}"
                    " ORDER BY id DESC LIMIT 15"
                )
                with managed_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query)
                    transactions_raw = cursor.fetchall()

                processed_items = []
                for t_type, category, amount_enc, desc_enc, t_date in transactions_raw:
                    is_corrupted = False

                    # Şifre çözme denemesi
                    try:
                        dec_amt = float(decrypt(str(amount_enc), SECRET_KEY))
                    except (ValueError, TypeError):
                        dec_amt = 0.0
                        is_corrupted = True

                    try:
                        dec_desc = decrypt(str(desc_enc), SECRET_KEY) if desc_enc else ""
                    except (ValueError, TypeError):
                        dec_desc = ""
                        is_corrupted = True

                    processed_items.append(
                        (t_type, category, dec_amt, dec_desc, t_date, is_corrupted)
                    )

                Clock.schedule_once(
                    lambda dt: self._render_recent_transactions(processed_items), 0
                )
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Error fetching recent transactions")

        threading.Thread(target=fetch_task, daemon=True).start()

    def _render_recent_transactions(self, transactions):
        try:
            recent_list = self.root.ids.recent_transactions_list
            data = []
            brand_names_to_prefetch = set()
            from services.brand_icon_service import (
                classify_brand,
                resolve_cached_brand_icon_path,
            )

            icon_mapping = {
                "su": ("water", (0.13, 0.59, 0.95, 1)),
                "fatura": ("receipt", (0.4, 0.4, 0.4, 1)),
                "freelance": ("laptop-account", (0.1, 0.7, 0.7, 1)),
                "maaş": ("bank", (0.18, 0.8, 0.25, 1)),
                "dijital platformlar": ("youtube-tv", (0.6, 0.2, 0.8, 1)),
                "market": ("basket", (0.95, 0.6, 0.1, 1)),
                "kira": ("home", (0.7, 0.3, 0.3, 1)),
                "ulaşım": ("bus", (0.3, 0.3, 0.3, 1)),
                "sağlık": ("hospital-box", (0.9, 0.1, 0.1, 1)),
                "eğitim": ("school", (0.2, 0.4, 0.8, 1)),
                "hisse/varlık": ("chart-line", (0.08, 0.72, 0.42, 1)),
            }

            for t_type, category, amount, decrypted_desc, t_date, is_corrupted in transactions:
                cat_lower = category.lower() if category else ""
                icon_data = next(
                    (v for k, v in icon_mapping.items() if k in cat_lower), None
                )
                brand_text = f"{decrypted_desc or ''} {category or ''}".strip()
                brand_icon = resolve_cached_brand_icon_path(brand_text)
                brand_key, _ = classify_brand(brand_text)
                if brand_key and not brand_icon:
                    brand_names_to_prefetch.add(brand_text)

                if is_corrupted:
                    icon_name, icon_col = "alert-circle-outline", (0.9, 0.1, 0.1, 1)
                    amount_text = translate("[color=#D32F2F]⚠️ Bozuk Kayıt[/color]")
                    display_cat = translate("Veri Okunamadı")
                else:
                    display_cat = translate(category)
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
                        amount_text = translate(
                            f"[color=#0277BD]- ₺{amount:,.2f} Yatırım[/color]"
                        )
                    elif category == "Varlık Satışı":
                        amount_text = translate(
                            f"[color=#2E7D32]+ ₺{amount:,.2f} Satış[/color]"
                        )
                    elif t_type == "income":
                        amount_text = f"[color=#2E7D32]+ ₺{amount:,.2f}[/color]"
                    else:
                        amount_text = f"[color=#D32F2F]- ₺{amount:,.2f}[/color]"

                data.append(
                    {
                        "text": display_cat,
                        "secondary_text": f"{t_date[:10]} | {amount_text}",
                        "icon_source": brand_icon or "" if not is_corrupted else "",
                        "icon_name": icon_name,
                        "icon_color": list(icon_col),
                    }
                )

            recent_list.data = data
            if brand_names_to_prefetch:
                self._prefetch_recent_brand_icons(brand_names_to_prefetch, transactions)
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Error rendering recent UI")

    def _prefetch_recent_brand_icons(self, brand_names, transactions):
        import threading
        from services.brand_icon_service import fetch_and_cache_brand_icon

        def worker():
            any_success = False
            for name in brand_names:
                if fetch_and_cache_brand_icon(name):
                    any_success = True
            if any_success:
                Clock.schedule_once(
                    lambda dt: self._render_recent_transactions(transactions), 0
                )

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------------------
    # Authentication & Profile
    # -------------------------------------------------------------------------
    def authentication_screen(self):
        try:
            if self.config_store.exists("security"):
                security = self.config_store.get("security")
                if (
                    security.get("is_set") is True
                    and security.get("pin_hash")
                    and security.get("salt")
                ):
                    return "login"
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Güvenlik kaydı okunamadı; kurulum ekranına düşülüyor")
        return "pin_setup"

    def route_after_auth(self):
        try:
            from services.account_service import AccountService

            if not AccountService.has_any_account():
                return "account_setup"
        except Exception as exc:
            from utils.logging_config import get_logger
            get_logger().exception("Hesap kontrolü yapılamadı")
        return "home"

    def create_first_account(self):
        from services.account_service import AccountService, CHECKING

        name_field = self.root.ids.first_account_name_input
        balance_field = self.root.ids.first_account_balance_input
        error = self.root.ids.first_account_error_label

        raw_balance = (balance_field.text or "0").strip().replace(",", ".")
        try:
            initial_balance = float(raw_balance or 0)
        except ValueError:
            error.text = translate("Geçerli bir tutar girin!")
            return

        try:
            AccountService.create_account(
                name=name_field.text,
                account_type=CHECKING,
                initial_balance=initial_balance,
            )
        except ValueError as exc:
            error.text = translate(str(exc))
            return

        error.text = ""
        self.root.ids.screen_manager.current = "home"
        Clock.schedule_once(lambda dt: self.render_accounts(), 0)
        Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0.05)

    def setup_pin(self):
        pin = self.root.ids.pin_setup_input.text.strip()
        confirmation = self.root.ids.pin_confirm_input.text.strip()
        error = self.root.ids.pin_setup_error_label

        is_valid, policy_error = PasswordPolicy.validate(pin)
        if not is_valid:
            error.text = translate(policy_error)
            return
        if pin != confirmation:
            error.text = translate("Şifreler eşleşmiyor.")
            return

        salt = SecurityService.generate_salt()
        pin_hash = SecurityService.hash_password(pin, salt)
        self.config_store.put("security", pin_hash=pin_hash, salt=salt, is_set=True)
        error.text = ""
        self.root.ids.pin_setup_input.text = ""
        self.root.ids.pin_confirm_input.text = ""
        self.root.ids.screen_manager.current = self.route_after_auth()

    def open_change_pin_dialog(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.metrics import dp
        
        content = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None, height=dp(160))
        self._new_pin_input = MDTextField(
            hint_text=translate("Yeni Şifre"),
            password=True,
            max_text_length=32,
            multiline=False,
            write_tab=False,
            helper_text=translate("En az 4 karakter, 1 büyük harf ve 1 özel karakter"),
            helper_text_mode="persistent"
        )
        self._new_pin_confirm = MDTextField(
            hint_text=translate("Yeni Şifre Tekrar"),
            password=True,
            max_text_length=32,
            multiline=False,
            write_tab=False
        )
        content.add_widget(self._new_pin_input)
        content.add_widget(self._new_pin_confirm)

        self._change_pin_dialog = MDDialog(
            title=translate("Şifre Değiştir"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=translate("İPTAL"),
                    on_release=lambda _b: self._change_pin_dialog.dismiss()
                ),
                MDRaisedButton(
                    text=translate("KAYDET"),
                    on_release=self._apply_new_pin
                )
            ]
        )
        self._change_pin_dialog.open()

    def _apply_new_pin(self, _button):
        pin = self._new_pin_input.text.strip()
        confirmation = self._new_pin_confirm.text.strip()

        from utils.toast import toast

        is_valid, policy_error = PasswordPolicy.validate(pin)
        if not is_valid:
            toast(translate(policy_error))
            return

        if pin != confirmation:
            toast(translate("Şifreler eşleşmiyor."))
            return

        salt = SecurityService.generate_salt()
        pin_hash = SecurityService.hash_password(pin, salt)
        self.config_store.put("security", pin_hash=pin_hash, salt=salt, is_set=True)

        self._change_pin_dialog.dismiss()
        self._change_pin_dialog = None

        toast(translate("Şifre başarıyla değiştirildi. Lütfen tekrar giriş yapın."))
        
        # Çıkış yap (logout)
        self.root.ids.password_input.text = ""
        self.root.ids.screen_manager.current = "login"

    def check_login(self):
        pin = self.root.ids.password_input.text.strip()
        if self.authentication_screen() != "login":
            self.root.ids.screen_manager.current = "pin_setup"
            return

        throttle_state = (
            self.config_store.get("security_throttle")
            if self.config_store.exists("security_throttle") else {}
        )
        remaining = LoginThrottle.seconds_remaining(throttle_state)
        if remaining > 0:
            self._handle_failed_login(message=translate(
                f"Çok fazla hatalı deneme. {int(remaining) + 1} saniye sonra tekrar deneyin."
            ))
            return

        security = self.config_store.get("security")
        if SecurityService.verify_password(pin, security["salt"], security["pin_hash"]):
            if SecurityService.needs_upgrade(security["pin_hash"]):
                new_hash = SecurityService.hash_password(pin)
                self.config_store.put(
                    "security", pin_hash=new_hash,
                    salt=security["salt"], is_set=True,
                )
            self.config_store.put(
                "security_throttle", **LoginThrottle.record_success()
            )
            self._handle_successful_login()
        else:
            new_throttle = LoginThrottle.record_failure(throttle_state)
            self.config_store.put("security_throttle", **new_throttle)
            new_remaining = LoginThrottle.seconds_remaining(new_throttle)
            if new_remaining > 0:
                self._handle_failed_login(message=translate(
                    f"Çok fazla hatalı deneme. {int(new_remaining) + 1} saniye sonra tekrar deneyin."
                ))
            else:
                self._handle_failed_login()

    def _handle_successful_login(self):
        self.root.ids.login_error_label.text = ""
        self.root.ids.password_input.text = ""
        self.root.ids.screen_manager.current = self.route_after_auth()

    def _handle_failed_login(self, message=None):
        self.root.ids.login_error_label.text = message or translate("Hatalı Şifre!")

        pwd_container = self.root.ids.password_container

        Animation.cancel_all(pwd_container)

        if not hasattr(pwd_container, "anim_original_x"):
            pwd_container.anim_original_x = pwd_container.x

        def _shake_anim(orig_x):
            return (
                Animation(x=orig_x + 10, duration=0.05)
                + Animation(x=orig_x - 10, duration=0.05)
                + Animation(x=orig_x + 10, duration=0.05)
                + Animation(x=orig_x - 10, duration=0.05)
                + Animation(x=orig_x, duration=0.05)
            )

        anim_pwd = _shake_anim(pwd_container.anim_original_x)

        def clear_original_x(*args):
            if hasattr(pwd_container, "anim_original_x"):
                del pwd_container.anim_original_x

        anim_pwd.bind(on_complete=clear_original_x)
        anim_pwd.start(pwd_container)

    def admin_logout(self):
        if self.root:
            self.root.ids.password_input.text = ""
            self.root.ids.screen_manager.current = self.authentication_screen()

    # -------------------------------------------------------------------------
    # Categories & AI Insights
    # -------------------------------------------------------------------------
    def load_categories(self, cat_type=None):
        if cat_type:
            self.active_category_type = cat_type

        settings_list = self.root.ids.settings_list
        settings_list.clear_widgets()

        self._category_load_generation = getattr(self, "_category_load_generation", 0) + 1
        generation = self._category_load_generation

        def _fetch(dt):
            with managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, type, importance FROM categories WHERE type = ? ORDER BY name",
                    (self.active_category_type,),
                )
                categories = cursor.fetchall()
            self._add_categories_incrementally(settings_list, categories, generation)

        Clock.schedule_once(_fetch, 0.1)

    _CATEGORY_BATCH_SIZE = 8

    def _add_categories_incrementally(self, settings_list, categories, generation, index=0):
        if generation != self._category_load_generation:
            return
        end = min(index + self._CATEGORY_BATCH_SIZE, len(categories))
        for cat_name, cat_type_val, cat_imp in categories[index:end]:
            item = CategorySettingItem(
                cat_name=cat_name, cat_type=cat_type_val, cat_importance=cat_imp
            )
            settings_list.add_widget(item)
        if end < len(categories):
            Clock.schedule_once(
                lambda dt: self._add_categories_incrementally(
                    settings_list, categories, generation, end
                ),
                0,
            )

    def update_category_importance(self, category_name, is_active):
        new_importance = "main" if is_active else "extra"
        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE categories SET importance = ? WHERE name = ?",
                (new_importance, category_name),
            )
            conn.commit()

        # `importance`, `summarize_transactions`'ın main/extra kovalarını
        # belirliyor — yani bakiye hiç değişmese de dashboard ÖZETİ değişir.
        # Sürüm artmazsa `_compute_dashboard_metrics` önbelleği bayat kalır.
        from services.asset_service import mark_financial_data_changed
        mark_financial_data_changed()

        pending = getattr(self, "_category_chart_refresh_event", None)
        if pending is not None:
            pending.cancel()

        def refresh(_dt):
            self._category_chart_refresh_event = None
            self.safe_refresh_charts()

        self._category_chart_refresh_event = Clock.schedule_once(refresh, 0.25)

    def generate_financial_advice(self, *args):
        import threading

        self._advice_generation = getattr(self, "_advice_generation", 0) + 1
        generation = self._advice_generation

        def _work():
            try:
                advice_text = self._compute_financial_advice_text()
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Finansal tavsiye hesaplanamadı")
                return

            def _apply(dt):
                if generation != self._advice_generation:
                    return
                self._apply_financial_advice_text(advice_text)

            Clock.schedule_once(_apply, 0)

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return thread

    def _compute_financial_advice_text(self):
        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT category, amount FROM transactions WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') AND {COMPLETED_TX}"
            )
            expense_rows_this_month = cursor.fetchall()

            cat_sums, this_month_exp = {}, 0.0
            for cat, amount in expense_rows_this_month:
                try:
                    val = float(decrypt(str(amount), SECRET_KEY))
                except (ValueError, TypeError):
                    val = 0.0
                cat_sums[cat] = cat_sums.get(cat, 0.0) + val
                this_month_exp += val

            highest_cat_name = (
                max(cat_sums, key=lambda k: cat_sums[k]) if cat_sums else "Yok"
            )

            cursor.execute(
                f"SELECT amount FROM transactions WHERE type='expense' AND strftime('%m', transaction_date) = strftime('%m', 'now', '-1 month', 'localtime') AND {COMPLETED_TX}"
            )
            last_month_exp = sum(
                float(decrypt(str(amt[0]), SECRET_KEY))
                for amt in cursor.fetchall()
                if amt[0]
            )

            cursor.execute(
                f"SELECT amount FROM transactions WHERE type='income' AND strftime('%m', transaction_date) = strftime('%m', 'now', 'localtime') AND {COMPLETED_TX}"
            )
            this_month_inc = sum(
                float(decrypt(str(amt[0]), SECRET_KEY))
                for amt in cursor.fetchall()
                if amt[0]
            )

        if last_month_exp > 0:
            change_percent = ((this_month_exp - last_month_exp) / last_month_exp) * 100
            change_text = (
                translate(f"%{change_percent:.1f} arttı")
                if change_percent > 0
                else translate(f"%{abs(change_percent):.1f} azaldı")
            )
        else:
            change_text = translate("karşılaştırılacak veri yok")

        savings_rate = (
            ((this_month_inc - this_month_exp) / this_month_inc) * 100
            if this_month_inc > 0
            else 0
        )

        advice_text = translate(
            f"Bu ay harcamalarınız geçen döneme kıyasla {change_text}.\n"
            f"En çok harcama yapılan alan: {translate(highest_cat_name)}.\n"
            f"Bu ayki net tasarruf oranınız: %{savings_rate:.1f}. Harika birikim dönemi!"
        )

        forecast_text, forecast_state = self._compute_monthly_forecast_text()
        self._advice_forecast_state = forecast_state
        return advice_text + "\n\n" + forecast_text

    def _compute_monthly_forecast_text(self):
        from services.insights_service import generate_monthly_forecast

        def _fmt(v):
            return (
                f"{v:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            )

        forecast = generate_monthly_forecast()
        if forecast["insufficient_data"]:
            return (
                translate(
                    "Son 3 ayın istatistiğine göre ay sonu öngörüsü: "
                    "en az 3 aylık işlem geçmişi biriktiğinde burada görünecek."
                ),
                "neutral",
            )

        month_end = _fmt(forecast["projected_month_end_balance"])
        surplus = forecast["projected_surplus"]

        if forecast["projected_month_end_balance"] < 0:
            return (
                translate(
                    "Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin {month_end} "
                    "olması bekleniyor. Dikkat: Model bakiyenizin eksiye düşebileceğini "
                    "gösteriyor, harcamalarınızı gözden geçirin."
                ).format(month_end=month_end),
                "negative",
            )
        if surplus < 0:
            return (
                translate(
                    "Son 3 ayın istatistiğine göre mevcut harcama eğiliminiz sürerse bu "
                    "ay sonunda bakiyeniz {month_end} seviyesine gerileyebilir."
                ).format(month_end=month_end),
                "warning",
            )
        if surplus > 0 and forecast["savings_rate"] >= 0.10:
            return (
                translate(
                    "Son 3 ayın istatistiğine göre bu ay sonunda cebinizde {month_end} "
                    "kalacak; bunu bir yatırım aracı olarak değerlendirebilirsiniz."
                ).format(month_end=month_end),
                "positive",
            )
        return (
            # `f` ÖNEKİ YOK, bilerek: `{month_end}` çeviriden SONRA
            # doldurulmalı. Tutar önce enterpole edilirse ortaya her seferinde
            # farklı bir dize çıkar, sözlükteki statik şablonla eşleşmez ve
            # İngilizce arayüzde Türkçe metin görünür (v0.0.4'te düzeltilen
            # hata buydu). Eski `f` öneki etkisizdi — bu parçada hiç
            # placeholder yok — ama yanıltıcıydı.
            translate(
                "Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin yaklaşık "
                "{month_end} olması bekleniyor."
            ).format(month_end=month_end),
            "neutral",
        )

    def _apply_financial_advice_text(self, advice_text):
        state_colors = {
            "positive": "green",
            "warning": "amber",
            "negative": "red",
            "neutral": "blue",
        }
        state_icons = {
            "positive": "trending-up",
            "warning": "trending-down",
            "negative": "alert-circle-outline",
            "neutral": "robot-outline",
        }
        state = getattr(self, "_advice_forecast_state", "neutral")

        try:
            app = MDApp.get_running_app()
            if app and app.root and "prediction_text" in app.root.ids:
                app.root.ids.prediction_text.text = advice_text
                app.root.ids.prediction_icon.icon = state_icons[state]
                app.root.ids.prediction_icon.text_color = ftheme.accent(
                    app.theme_cls, state_colors[state]
                )
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Finansal tavsiye metni arayüze yazılamadı")

    # -------------------------------------------------------------------------
    # Dialogs & Reset Functionality
    # -------------------------------------------------------------------------
    def contact_us(self):
        """Destek/geri bildirim kanalını açar.

        E-posta yerine GitHub: proje zaten herkese açık geliştiriliyor, sorunlar
        orada izleniyor ve bir issue hem yanıtlanabilir hem başkalarına görünür
        olur — support@ kutusuna giden mesaj ikisini de sağlamıyordu.
        """
        import webbrowser

        def open_github(_button):
            webbrowser.open(ARCHLENCE_GITHUB_URL)
            if hasattr(self, "contact_dialog"):
                self.contact_dialog.dismiss()

        self.contact_dialog = MDDialog(
            title=translate("Bize Ulaşın"),
            text=translate(
                "Soru, öneri ve hata bildirimleri için GitHub sayfamızı "
                "kullanabilirsiniz:\n\n[b]github.com/superuser-d0/archlence[/b]"
            ),
            buttons=[
                ftheme.secondary_button(
                    translate("KAPAT"),
                    self.theme_cls,
                    on_release=lambda x: self.contact_dialog.dismiss(),
                ),
                ftheme.primary_button(
                    translate("GITHUB'DA AÇ"),
                    self.theme_cls,
                    on_release=open_github,
                ),
            ],
        )
        if hasattr(self.contact_dialog, "ids") and "text" in self.contact_dialog.ids:
            self.contact_dialog.ids.text.markup = True
        self.contact_dialog.open()

    def confirm_delete_all_data(self):
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height="60dp")
        self.reset_input = MDTextField(
            hint_text=translate("SİL yazınız"),
            helper_text=translate("Onaylamak için büyük harflerle SİL yazın"),
            helper_text_mode="persistent",
        )
        content.add_widget(self.reset_input)

        self.reset_dialog = MDDialog(
            title=translate("Tüm Verileri Sıfırla"),
            text=translate(
                "Tüm işlemler, varlıklar, borçlar ve hedefler kalıcı olarak silinecektir. Emin misiniz?"
            ),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    translate("İPTAL"),
                    self.theme_cls,
                    on_release=lambda x: self.reset_dialog.dismiss(),
                ),
                ftheme.danger_button(
                    translate("SİL"), self.theme_cls, on_release=self.delete_all_data
                ),
            ],
        )
        self.reset_dialog.open()

    def delete_all_data(self, *args):
        expected_confirmation = "DELETE" if self.language == "en" else "SİL"
        if (
            hasattr(self, "reset_input")
            and self.reset_input.text.strip().upper() != expected_confirmation
        ):
            toast(translate("Silme işlemi iptal edildi. Onay için SİL yazmalısınız."))
            return
        try:
            if hasattr(self, "store"):
                self.store.clear()
            self.savings_goals = []

            with managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """)
                table_names = [row["name"] for row in cursor.fetchall()]
                for table_name in table_names:
                    safe_name = table_name.replace('"', '""')
                    cursor.execute(f'DELETE FROM "{safe_name}"')
                cursor.execute("DELETE FROM sqlite_sequence")
                conn.commit()

            initialize_database()
            if self.config_store.exists("security"):
                self.config_store.delete("security")

            from services.asset_service import (
                invalidate_asset_data_cache,
                start_data_warmup,
            )

            invalidate_asset_data_cache()
            self._liquid_balance_cache = 0.0
            self._today_liquid_delta_cache = 0.0
            self._assets_cache = []
            self._asset_ui_loaded_at = 0.0
            self._asset_load_inflight = False
            self._asset_load_generation = getattr(self, "_asset_load_generation", 0) + 1
            self._asset_render_generation = (
                getattr(self, "_asset_render_generation", 0) + 1
            )
            self._recurring_candidates = []
            self._insights_generation = getattr(self, "_insights_generation", 0) + 1

            if hasattr(self, "render_accounts"):
                self.render_accounts()
            start_data_warmup(
                callback=(
                    lambda: (
                        self.render_accounts()
                        if hasattr(self, "render_accounts")
                        else None
                    )
                )
            )

            self.refresh_dashboard_data()

            # `refresh_dashboard_data` bu İKİSİNİ KAPSAMIYOR — ikisi de
            # yalnızca açılışta (on_start) ve kendi tetikleyicilerinde
            # (işlem ekleme / varlık satışı) çalışıyor. Sıfırlamadan sonra
            # çağrılmadıkları için ekranda SİLİNMİŞ verinin sonucu kalıyordu:
            # "Algoritmik Öngörü" eski harcama yorumunu, "Varlık Geçmişi"
            # eski satırları göstermeye devam ediyordu (ölçüldü).
            self.generate_financial_advice()
            if hasattr(self, "load_asset_history"):
                self.load_asset_history()

            if "wealth_balance" in self.root.ids:
                self.root.ids.wealth_balance.text = "₺0.00"
                self.root.ids.wealth_pnl.text = "+₺0.00 / %0.00"
            if "budget_list" in self.root.ids:
                self.root.ids.budget_list.clear_widgets()

            toast(translate("Tüm veriler başarıyla silindi!"))
            if hasattr(self, "reset_dialog"):
                self.reset_dialog.dismiss()
            self.root.ids.screen_manager.current = "pin_setup"
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("Factory reset failed")


# =========================================================================
# 7. RUNNER ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    if _KivyWindow is None:
        print("ARCHLENCE_HEADLESS=1: GUI başlatılmadı, çıkılıyor.")
        raise SystemExit(0)

    from utils.single_instance import (
        AlreadyRunningError,
        SingleInstanceLock,
        notify_already_running,
    )

    _instance_lock = SingleInstanceLock(
        os.path.join(data_dir(), "archlence.instance.lock")
    )
    try:
        _instance_lock.acquire()
    except AlreadyRunningError as exc:
        notify_already_running(str(exc))
        raise SystemExit(2) from exc
    try:
        ArchlenceApp().run()
    finally:
        _instance_lock.release()
