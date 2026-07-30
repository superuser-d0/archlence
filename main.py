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

from utils.app_paths import data_dir, log_dir, migrate_legacy_path, resource_dir

# Bu dosyanın kendi dizini — eski (paketlenmiş kurulumda genelde salt-okunur)
# konumları migrate_legacy_path çağrılarında kaynak olarak kullanmak için.
# docs/ROADMAP.md Faz 1 madde 4.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ÇÖKME DÜZELTMESİ (gerçek bir Windows kurulumunda ampirik olarak üretildi):
# main.py'nin geri kalanı — `Builder.load_file("ui/tools.kv")`,
# `database/db.py::NETWORK_LOGOS`, ui/components.py'nin KV'ye gömülü
# "assets/blank.png" gibi literalleri — hep GÖRELİ yol kullanıyor, yani
# çalışma dizininin (cwd) kurulum klasörüyle aynı olduğunu VARSAYIYOR. Bu
# geliştirmede doğru (uygulama repo kökünden çalıştırılır) ama paketlenmiş
# bir `.exe` Başlat Menüsü/masaüstü kısayolundan ya da Inno Setup'ın
# kurulum-sonu "Başlat" adımından açıldığında Windows/Inno Setup çalışma
# dizinini kurulum klasörüyle aynı yapacağını GARANTİ ETMEZ. Sonuç: gerçek
# bir kullanıcı kurulumunda `FileNotFoundError: [Errno 2] No such file or
# directory: 'ui/tools.kv'` ile açılışta çöküyordu.
#
# Her göreli-yol referansını tek tek mutlak yola çevirmek yerine (bazıları
# .kv dosyalarına GÖMÜLÜ literal string, Python'dan dokunulamaz — bkz.
# ui/components.py), süreç HER ŞEYDEN ÖNCE doğru dizine geçiyor. Bu, tüm
# göreli referansları TEK bir yerden, hiçbirini teker teker bulmaya
# gerek kalmadan düzeltiyor. Kivy/KivyMD importlarından ÖNCE yapılmalı ki
# onların kendi olası göreli-yol varsayımları da doğru cwd'yi görsün.
os.chdir(resource_dir())

# =========================================================================
# 2. CRASH REPORTING & EARLY CONFIGURATION
# =========================================================================
# Crash reporting: Kivy'nin stderr yakalamasını susturduğu için çökmelerin
# loglanması. Faz 1 madde 4: artık _APP_DIR yerine platformdirs'in log
# dizininde — paketlenmiş bir Windows kurulumunda _APP_DIR genelde
# salt-okunur, crash.log tam da çökmeleri yakalaması gereken an sessizce
# açılamayabilirdi.
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
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _log_unhandled_exception

# docs/ROADMAP.md Faz 1 madde 2. Eskiden burada "DISPLAY yoksa
# KIVY_WINDOW=mock yap" mantığı vardı. İKİ AYRI SEBEPTEN BOZUKTU:
#
#   1) DISPLAY, X11/Linux'a özgü bir kural — Windows'ta HİÇBİR ZAMAN set
#      edilmez (kendi native pencere API'sini kullanır, X11'e ihtiyacı
#      yoktur). Yani bu kod, HER Windows kurulumunda koşulsuz "mock"a
#      düşüyordu.
#   2) "mock", Kivy 2.3.1'de GERÇEK bir pencere sağlayıcısı DEĞİL — gerçek
#      liste yalnızca egl_rpi/sdl2/x11 (bkz. kivy/core/window/__init__.py,
#      window_impl). `KIVY_WINDOW=mock`, Kivy'nin arama listesini "mock"
#      ile kısıtlıyor; hiçbir gerçek sağlayıcı bu listede olmadığından
#      core_select_lib hiçbirini DENEMEDEN "Unable to find any valuable
#      Window provider" diye loglayıp `Window`'u SESSİZCE `None` yapıyor —
#      EXCEPTION FIRLATMIYOR (bkz. kivy/core/__init__.py::core_select_lib,
#      bulunamama yolunda hiçbir raise yok, fonksiyon sessizce döner).
#
# Sonuç, ampirik olarak doğrulandı: aşağıdaki try/except bu hatayı HİÇ
# YAKALAYAMIYORDU (import başarıyla dönüyor, yalnızca değeri None oluyor),
# ve dosyanın en altındaki asıl giriş noktası da `_KivyWindow is None`
# ise `raise SystemExit(0)` ile BAŞARI kodu döndürüyordu — `console=False`
# olduğu için bu hiçbir yerde görünmeden. Yani DISPLAY'i olmayan HER
# platformda (= her Windows kurulumunda) paketlenmiş .exe muhtemelen
# hiçbir pencere göstermeden "başarıyla" kapanıyordu.
#
# Düzeltme: KIVY_WINDOW'a hiç dokunulmuyor — Kivy kendi doğal sağlayıcı
# aramasını (sdl2 vb.) çalıştırsın. Headless çalışma artık DISPLAY
# TAHMİNİYLE değil, açık bir bayrakla (ARCHLENCE_HEADLESS=1) kontrol
# ediliyor — ve o bayrak "hangi sağlayıcıyı dene"yi değil, "pencere
# KURULAMAZSA sessizce mi devam et yoksa görünür şekilde mi patla"yı
# belirliyor (aşağıdaki try/except'lere bak).
if not os.environ.get("KIVY_NO_ARGS"):
    os.environ["KIVY_NO_ARGS"] = "1"

ARCHLENCE_HEADLESS = os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in (
    "1", "true", "yes",
)

if ARCHLENCE_HEADLESS:
    os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
    os.environ.setdefault("KIVY_DPI", "96")
    # Bir CI/test ortamının çoğunda GERÇEK bir display sunucusu (X11/
    # Wayland) yok. Bu durumda arama listesi kısıtlanmazsa Kivy, SDL2
    # denemesinden sonra ham (SDL2 tabanlı olmayan) `x11` sağlayıcısına
    # düşüyor; o sağlayıcı düşük seviye bir Xlib connect() çağrısı yapıyor
    # ve display yoksa SÜRECİ OS SEVİYESİNDE ÇÖKERTİYOR (exit code 102,
    # "Couldn't connect to X server") — bu, aşağıdaki try/except'in asla
    # yakalayamayacağı bir C-seviyesi çökme, Python istisnası değil. GitHub
    # Actions'ın ubuntu-latest runner'ında ampirik olarak doğrulandı (PR
    # #16'nın ilk CI çalışması tam olarak bu şekilde kırmızı oldu).
    #
    # Düzeltme: arama listesini yalnızca `sdl2`'ye kısıtla (çökmeye sebep
    # olan ham x11 sağlayıcısına hiç ulaşılmıyor) ve SDL2'ye kendi resmi
    # desteklenen headless video sürücüsünü (`dummy`) ver — bu, herhangi
    # bir display olmadan çalışır ve başarısız olursa PYTHON SEVİYESİNDE
    # bir RuntimeError fırlatır (aşağıdaki `except (ImportError,
    # RuntimeError)` bunu düzgünce yakalar). Bu, eski `KIVY_WINDOW=mock`
    # ile AYNI ŞEY DEĞİL: "sdl2" gerçek bir sağlayıcı, "dummy" gerçek ve
    # belgelenmiş bir SDL2 sürücüsü, ve ikisi de yalnızca
    # ARCHLENCE_HEADLESS AÇIKÇA istendiğinde devreye giriyor — DISPLAY
    # yokluğundan tahmin edilmiyor.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("KIVY_WINDOW", "sdl2")

# =========================================================================
# 3. KIVY / KIVYMD IMPORTS
# =========================================================================
from kivy.config import Config

Config.set("kivy", "log_level", "error")  # Only log errors
Config.set("kivy", "log_maxfiles", 2)  # Keep only 2 log files
# Kivy'nin mouse provider'ı varsayılan olarak sağ/orta tık ve Ctrl+sol tık
# hareketlerini sahte çoklu-dokunma olarak yorumlayıp ekrana kırmızı temas
# halkaları çizer. Alt-Tab sonrasında SDL modifier durumu takılı kaldığında
# düz sol tıklar da bu moda sızabiliyor ve halkalar pencere boyunca kalıyor.
# Archlence mouse ile multitouch emülasyonu kullanmıyor; gerçek dokunmatik
# sağlayıcıları (hidinput/mtdev) bu ayardan bağımsızdır.
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
        # Kivy kendi sağlayıcı aramasını (egl_rpi/sdl2/x11) denedi ama
        # hiçbiri kurulamadı — bu import EXCEPTION FIRLATMAZ (bkz. yukarıdaki
        # ARCHLENCE_HEADLESS notu), `Window` sessizce None olur. Bunu
        # açıkça kontrol etmezsek, gerçek bir masaüstünde pencere
        # kurulamadığında kod sessizce ilerler ve çok daha sonra, alakasız
        # bir yerde `NoneType has no attribute ...` ile çöker.
        raise RuntimeError(
            "Kivy herhangi bir pencere sağlayıcısı bulamadı "
            "(egl_rpi/sdl2/x11 hiçbiri kullanılamadı)."
        )
except (ImportError, RuntimeError):
    if not ARCHLENCE_HEADLESS:
        # ARCHLENCE_HEADLESS açıkça istenmediyse bu SESSİZCE geçiştirilecek
        # bir şey değil — kullanıcı "uygulama hiçbir şey yapmadan kapandı"
        # yerine gerçek hatayı görmeli (docs/ROADMAP.md Faz 1 madde 2).
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
    from kivymd.toast import toast
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
    # ImportError: kivymd genuinely missing/broken. AttributeError: bir
    # kivymd sürüm uyuşmazlığı, yukarıdaki adlardan birini kaldırmış/
    # taşımış olabilir — ikisi de "gerçekten kurulamadı" kategorisi.
    # `except BaseException` eskiden buraya TAMAMEN alakasız bir hatayı
    # (ör. bir programlama bug'ı) da düşürüp aynı sessiz fallback'e
    # sokabilirdi.
    if not ARCHLENCE_HEADLESS:
        # bkz. yukarıdaki Window guard'ındaki aynı gerekçe: gerçek bir
        # masaüstünde bu sessizce geçiştirilmez.
        raise
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

    def toast(*args, **kwargs):
        return None


# =========================================================================
# 4. LOCAL MODULE IMPORTS
# =========================================================================
from utils.crypto import decrypt, key_protection_status
from database.init_db import initialize_database
from database.db import (
    get_connection,
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
from security.security_service import LoginThrottle, SecurityService
from services.history_service import write_daily_snapshot

# =========================================================================
# 5. CONSTANTS
# =========================================================================
SECRET_KEY = "fi" + "nora_secure_2026"


def _resolve_config_path():
    """docs/ROADMAP.md Faz 1 madde 4. Kalıcı config JSON dosyasının yolunu
    çözer; gerekiyorsa eski konumlardan (önce eski "finora" adı, sonra
    _APP_DIR'den kullanıcı-veri dizinine) tek seferlik migration yapar.
    ARCHLENCE_CONFIG_PATH açıkça set edildiyse OLDUĞU GİBİ kullanılır
    (migration atlanır) — testler ve ileri düzey override için.

    self'e ihtiyacı olmayan saf bir fonksiyon: gerçek bir Kivy penceresi
    kurmadan doğrudan çağrılıp test edilebilir (bkz.
    tests/test_app_paths_wiring.py)."""
    override = os.environ.get("ARCHLENCE_CONFIG_PATH")
    if override:
        return override

    target_path = os.path.join(data_dir(), "archlence_config.json")
    legacy_path = os.path.join(_APP_DIR, "archlence_config.json")
    legacy_finora_path = os.path.join(_APP_DIR, "fi" + "nora_config.json")

    # _APP_DIR'a HİÇ YAZMIYORUZ. Önceki hâli, eski "finora" dosyasını önce
    # _APP_DIR içinde yeni ada kopyalayıp sonra oradan taşıyordu — yani
    # paketlenmiş bir Windows kurulumunda SALT-OKUNUR olan kurulum
    # dizinine yazmaya çalışıyordu, tam da madde 4'ün ortadan kaldırmak
    # için var olduğu şeyi yaparak. Artık her iki eski konumdan da DOĞRUDAN
    # hedefe kopyalanıyor: önce yeni ad denenir, o taşınmadıysa (yoksa)
    # eski "finora" adı denenir. Hedef zaten varsa ikisi de hiçbir şey
    # yapmaz (migrate_legacy_path'in kendi guard'ı).
    if not migrate_legacy_path(legacy_path, target_path):
        migrate_legacy_path(legacy_finora_path, target_path)
    return target_path


def _resolve_savings_store_path():
    """docs/ROADMAP.md Faz 1 madde 4. `_resolve_config_path` ile aynı
    gerekçe, "finora" adı geçmişi olmayan tek dosya için."""
    legacy_path = os.path.join(_APP_DIR, "savings_goals.json")
    target_path = os.path.join(data_dir(), "savings_goals.json")
    migrate_legacy_path(legacy_path, target_path)
    return target_path


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

    _wealth_visible = True
    _liquid_balance_cache = 0.0
    _assets_cache = []

    # -------------------------------------------------------------------------
    # Lifecycle & Initialization
    # -------------------------------------------------------------------------
    @staticmethod
    def _warm_crypto_key_in_background():
        """PBKDF2 anahtar türetmesini (utils/crypto.py::_get_key) VE AEAD
        anahtar dosyası okumasını (`_get_aead_key`) arka planda önceden
        tetikler.

        DÜZELTME (performans): `encrypt`/`decrypt` her çağrıda 1 milyon
        iterasyonlu PBKDF2'yi YENİDEN çalıştırmaz — `functools.lru_cache` ile
        önbelleklenir — ama SÜRECİN İLK çağrısı bu maliyeti (~250ms, ölçüldü)
        öder. O ilk çağrı hangi thread'den gelirse o thread bloklanıyordu;
        pratikte neredeyse her zaman ana thread kazanıyordu çünkü `build()`
        senkron devam ederken arka plan thread'lerinin (varsa) başlaması bir
        kare gecikiyordu. Bu fonksiyon o yarışı BİLEREK arka plana kaydırır:
        `build()`'in ilk satırında çağrılır, böylece pencere görünür olana
        kadar anahtar çoktan ısınmış olur.

        AEAD ENTEGRASYONU NOTU (Faz 1 madde 5, PR #22): eskiden burada
        `decrypt(encrypt("archlence-warmup"))` çağrılıyordu — `encrypt()`
        artık HER ZAMAN yeni AEAD şemasını ürettiği için bu round-trip
        `_get_key`'e (PBKDF2) hiç UĞRAMAZ oldu, yani ısıtma sessizce
        işlevsiz kalırdı (bkz. tests/test_startup_performance.py, bu
        regresyonu yakaladı). `_get_key`'in kendisi hâlâ gerekli: var olan
        her eski-format satırın (AEAD'e henüz yeniden yazılmamış her
        transactions/active_debts/... kaydı) İLK çözülüşü hâlâ bu yoldan
        geçiyor. Doğrudan çağrılıyor — dolaylı bir round-trip'e güvenmek
        yerine.
        """
        import threading
        from utils.crypto import DEFAULT_PASSWORD, _get_aead_key, _get_key

        def _warm():
            try:
                _get_key(DEFAULT_PASSWORD)
                _get_aead_key()
            except Exception:
                pass

        thread = threading.Thread(target=_warm, daemon=True)
        thread.start()
        return thread

    def build(self):
        # Kivy'nin varsayılan 20 pre-frame iterasyonu, Archlence'ın iç içe
        # KivyMD/uyarlanabilir layout ağacı ilk kez ölçülürken zaman zaman
        # yetmiyor. Uygulama tarafında -1 ile kendini planlayan bir callback
        # yok; bu sınır yalnızca Builder'ın sonlu yerleşim zincirinin aynı
        # karede tamamlanabilmesi için ölçülü biçimde yükseltilir.
        Clock.max_iteration = 50
        self._warm_crypto_key_in_background()
        # docs/ROADMAP.md Faz 1 madde 4. initialize_database()'DEN ÖNCE:
        # eski BASE_DIR/finance.db varsa (var olan bir kurulumdan geçiş)
        # yeni kullanıcı-veri konumuna taşınır. Zaten yeni konumda bir DB
        # varsa (taze kurulum ya da önceki bir çalıştırmada zaten taşındı)
        # hiçbir şey yapmaz.
        migrate_legacy_database_location()
        initialize_database()
        self.store = JsonStore(_resolve_savings_store_path())
        if self.store.exists("goals"):
            self.savings_goals = self.store.get("goals")["data"]

        # KivyMD 1.2'nin tema renk animasyonları hızlı geçişlerde üst üste
        # binerek bazı label'ları eski zemin rengine/şeffaflığa bırakabiliyor.
        # Uygulamanın kendi geçişi yeterli; metin renkleri atomik güncellenir.
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
        # tools.kv ÖNCE yüklenir: dashboard.kv içinde BudgetPlannerPanel ve
        # BudgetSummaryCard örnekleniyor, kuralları önceden tanımlı olmalı.
        Builder.load_file("ui/tools.kv")
        root = Builder.load_file("ui/dashboard.kv")
        root.ids.screen_manager.current = self.authentication_screen()
        return root

    def tr(self, text, language=None):
        """KV ve Python arayüzünün ortak çeviri giriş noktası."""
        return translate(text, language or self.language)

    def set_language(self, code, persist=True):
        """Uygulama dilini anında değiştirir ve tercihi kalıcılaştırır."""
        self.language = set_active_language(code)
        if persist:
            try:
                self.config_store.put("language", code=self.language)
            except Exception as e:
                print("Dil tercihi kaydedilemedi:", e)

        # Python tarafında üretilen kartları seçilen dille yeniden oluştur.
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
            # KV property'leri doğru dili aynı anda alır; KivyMD 1.2'nin
            # önceden oluşturduğu bottom-navigation header/Label texture'ları
            # ise bazen bir sonraki gerçek çizim karesine kadar eski dokuyu
            # taşır. Property state'i ile piksel çıktısını aynı karede
            # uzlaştır; tema değişimindeki _refresh_text_textures ile aynı
            # sınıf güvenli tazeleme.
            Clock.schedule_once(self._refresh_language_widgets, 0)

    def _refresh_language_widgets(self, *args):
        """Dil property'leri değiştikten sonra KivyMD kopya/dokularını uzlaştır."""
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
        """Türkçe/İngilizce dil seçicisini açar."""
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

        # DÜZELTME: Araçlar ızgarasındaki TÜM kareler düz MDCard + `on_release:`
        # idi — ripple_behavior ButtonBehavior miras almadığından bu SESSİZCE
        # hiç ateşlenmiyordu (bkz. ui/theme.py::bind_card_tap docstring'i,
        # aynı kökten "Daha fazla seçenek"/tutar alanı hatalarıyla). KV'deki
        # ölü `on_release:` satırları kaldırıldı, gerçek tıklama burada
        # kuruluyor. Kart-callback eşlemesi tek yerde tutulsun diye liste.
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
                print(f"'{card_id}' karesi tıklanabilir yapılamadı:", e)

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("peewee").setLevel(logging.CRITICAL)

        self.purge_logs()
        self.vacuum_database()

        from services.asset_service import start_data_warmup

        start_data_warmup()

        self.write_daily_balance_snapshot()
        # Aktif ay/yıl state'ini kur. Panel açılışta ızgarada olmadığından ay
        # butonları burada çizilmez; planlayıcı diyaloğu açılınca kurulur.
        self.setup_dynamic_months()
        self.safe_refresh_charts()
        self.load_recent_transactions("Günlük")
        self.generate_financial_advice()
        self.load_active_debts()
        self.load_active_assets()
        self.load_asset_history()
        # Bekleyen özeti burada ayrıca çağrılmaz: process_due_auto_deductions
        # vadesi geleni bakiyeye işledikten SONRA kendisi tetikliyor, yoksa
        # paralel okuma uzlaştırılmış kayıtları hâlâ bekleyen gösterebilirdi.
        self.process_due_auto_deductions()

    def on_stop(self):
        """Kivy'nin kapanış kancası — süreç ömrüne bağlanmış zamanlayıcıları
        bırakır. `stop_active_assets_refresh` olmadan hesaplar görünümündeki
        60 saniyelik `Clock.schedule_interval` hiçbir yerde iptal edilmiyordu
        (bkz. mixins/account_mixin.py); kapanış sırasında tetiklenmeye devam
        edip yıkılmakta olan DB/arayüze dokunabilirdi."""
        try:
            self.stop_active_assets_refresh()
        except Exception as exc:
            # Kapanış yolu hiçbir koşulda hata fırlatmamalı.
            print("Arka plan tazeleme durdurulamadı:", exc)

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
                try:
                    self.config_store.put("display", style=desired_style)
                except Exception as e:
                    print("Görünüm tercihi kaydedilemedi:", e)
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
        if self.root:
            chart_box = self.root.ids.get("chart_master_box")
            if chart_box is not None and hasattr(chart_box, "refresh_theme"):
                try:
                    chart_box.refresh_theme()
                except Exception as exc:
                    print("Tema sonrası grafikler yenilenemedi:", exc)
            for widget in self.root.walk():
                if isinstance(widget, HorizontalBarChart):
                    try:
                        widget.update_chart()
                    except Exception as exc:
                        print("Tema sonrası çubuk grafik yenilenemedi:", exc)
                elif isinstance(widget, ScenarioComparisonChart):
                    try:
                        widget.draw_immediate()
                    except Exception as exc:
                        print("Tema sonrası senaryo grafiği yenilenemedi:", exc)
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
                    if hasattr(widget, "_archlence_tint"):
                        refresh_card_theme(widget, self.theme_cls)
                    widget.elevation = 0
                    if hasattr(widget, "shadow_softness"):
                        widget.shadow_softness = 0
                    if hasattr(widget, "shadow_color"):
                        widget.shadow_color = (0, 0, 0, 0)
                except Exception:
                    pass

    def _resync_text_fields(self):
        if not self.root:
            return
        # set_default_colors(), Archlence'nın kontrast renklerini KivyMD
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
                    pass
            print("Purged Kivy logs due to size > 5MB")

    def vacuum_database(self):
        """VACUUM'u arka planda çalıştırır.

        DÜZELTME (performans): eskiden bu, pencere zaten görünür olduktan
        SONRA (`on_start()` içinde) ana thread'de senkron çalışıyordu.
        Maliyeti veritabanı dosya boyutuyla orantılı olduğundan (VACUUM tüm
        dosyayı yeniden yazar) küçük test veritabanında (~20ms) fark
        edilmiyordu ama aylarca veri biriktirmiş gerçek bir kullanıcıda
        büyüyebilirdi. Diğer arka plan DB işlemleriyle AYNI eşzamanlılık
        modelini kullanır (ayrı bağlantı + `get_connection()`'ın kendi
        `timeout` ayarı kilit çakışmalarını tolere eder).
        """
        import threading

        def _work():
            try:
                with managed_connection() as conn:
                    conn.execute("VACUUM")
                    conn.commit()
                print("Database VACUUM completed.")
            except Exception as e:
                print(f"VACUUM failed: {e}")

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return thread

    def write_daily_balance_snapshot(self):
        try:
            write_daily_snapshot()
        except Exception as e:
            print("Günlük bakiye snapshot'ı yazılamadı:", e)

    # -------------------------------------------------------------------------
    # Metrics & Dashboard Updates
    # -------------------------------------------------------------------------
    def update_metrics_and_goals(self):
        """Tüm SQL taramalarını ve şifre çözmeyi arka plan thread'inde bitirir;
        sonuç hazır olunca arayüze TEK Clock çağrısıyla property güncellemesi
        yapar. (Eski sürüm bu taramaları ana thread'de koşturuyordu — sekme
        geçişindeki donmanın ana kaynağı buydu.)"""
        import threading

        self._metrics_generation = getattr(self, "_metrics_generation", 0) + 1
        generation = self._metrics_generation

        def _work():
            try:
                payload = self._compute_dashboard_metrics()
            except FinancialDataIntegrityError as exc:
                from utils.logging_config import log_integrity_error
                error_id = log_integrity_error(exc)
                Clock.schedule_once(
                    lambda dt: self._apply_dashboard_integrity_error(error_id),
                    0,
                )
                return
            except Exception as e:
                print("Metrik hesaplama hatası:", e)
                return

            def _apply(dt):
                if generation != self._metrics_generation:
                    return  # bayat sonuç — daha yeni bir tazeleme başladı
                self._apply_dashboard_metrics(payload)

            Clock.schedule_once(_apply, 0)

        threading.Thread(target=_work, daemon=True).start()

    def _compute_dashboard_metrics(self):
        """Yalnızca veri üretir, hiçbir widget'a dokunmaz (thread güvenli)."""
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
        total_income = float(summary.total_income)
        total_expense = float(summary.total_expense)
        # "Cüzdanım" toplamı, işlem nakit-akışına (gelir − gider) hesapların
        # AÇILIŞ bakiyelerini de ekler. Açılış bakiyesi transactions'a değil
        # accounts.balance + balance_events'e yazıldığından, bu taban olmadan
        # açılış tutarı "Kartlarım"da görünüp "Cüzdanım"da görünmüyordu.
        from services.queries import DashboardService

        opening_baseline = DashboardService.get_opening_baseline()
        total_balance = total_income - total_expense + opening_baseline

        filter_text = getattr(self, "home_filter", "Bugün")

        period_income = period_expense = period_net = 0.0
        try:
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

            with managed_connection() as conn2:
                period_rows = conn2.execute(
                    f"SELECT amount, type FROM transactions"
                    f" WHERE date(transaction_date) {date_cond}"
                    f" AND {COMPLETED_TX}"
                ).fetchall()
            for t_amt, t_typ in period_rows:
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
        except Exception:
            pass

        # ── 30 günlük ODE projeksiyonu girdileri ─────────────────────────────
        inc_30 = exp_30 = 0.0
        try:
            with managed_connection() as conn_pred:
                rows = conn_pred.execute(f"""
                    SELECT type, amount
                    FROM transactions
                    WHERE date(transaction_date) >=
                          date('now', '-30 days', 'localtime')
                      AND {COMPLETED_TX}
                """).fetchall()

            for t_type, amount in rows:
                try:
                    val = float(decrypt(str(amount), SECRET_KEY))
                except Exception:
                    val = 0.0
                if t_type in ("income", "Gelir"):
                    inc_30 += val
                elif t_type in ("expense", "Gider"):
                    exp_30 += val
        except Exception:
            pass

        daily_income = inc_30 / 30.0
        daily_expense = exp_30 / 30.0

        try:
            change_rate = self.calculate_monthly_change_rate()
        except Exception as e:
            print("Değişim oranı hesaplanamadı:", e)
            change_rate = None

        return {
            "filter_text": filter_text,
            "total_income": total_income,
            "total_expense": total_expense,
            "total_balance": total_balance,
            "period_income": period_income,
            "period_expense": period_expense,
            "period_net": period_net,
            "projection_daily_income": daily_income,
            "projection_daily_expense": daily_expense,
            "change_rate": change_rate,
        }

    def _apply_dashboard_integrity_error(self, error_id):
        """Invalidate financial totals instead of displaying partial zeros."""
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
        """Hazır metrik paketini arayüze TEK seferde, yalnızca property
        güncelleyerek yazar. Widget silinmez/taşınmaz ve konum animasyonu
        yoktur: eski y-kaydırmalı kart animasyonu, kartları layout kontrolünden
        çıkarıp grafiklerin üzerine bindiriyordu (overlap/Z-index hatası)."""
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
                pass

            localized_filter = translate(filter_text)
            _set_changed(
                self.root.ids.home_change_title,
                "text",
                f"{translate('Değişim')} ({localized_filter})",
            )
            _set_changed(self.root.ids.today_card_title, "text", localized_filter)

            prefix = "+" if period_net > 0 else ""
            formatted_period = (
                f"{period_net:,.2f} ₺".replace(",", "X")
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
                pass

            savings_key = (
                round(total_balance, 2),
                repr(getattr(self, "savings_goals", [])),
            )
            if savings_key != getattr(self, "_last_savings_render_key", None):
                self._last_savings_render_key = savings_key
                # Savings cards are expensive; run only when their actual input
                # changed and yield one frame after primary dashboard labels.
                Clock.schedule_once(
                    lambda dt: self.render_savings_goals(total_balance), 0
                )

        except Exception:
            pass

        # ── Alt metrik kartları: KV'de sabit yerlerinde, tek seferde dolar ───
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

        if m.get("change_rate") is not None:
            self._apply_change_rate(m["change_rate"])

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
            pass

    def toggle_wealth_visibility(self):
        # DÜZELTME (kasma): today_liquid_delta hiç verilmeden çağrıldığında
        # update_wealth_card "eski senkron çağıranlar için" yolu izleyip
        # _compute_today_liquid_delta()'yı DOĞRUDAN UI thread'inde
        # çalıştırıyordu (DB sorgusu + N adet decrypt) — göz ikonuna her
        # basışta. Görünürlük değiştirmek yeni veri gerektirmez; son bilinen
        # değeri (update_wealth_card'ın kendisi her çağrıda önbelleğe alır)
        # yeniden kullanmak yeterli.
        self._wealth_visible = not self._wealth_visible
        self.update_wealth_card(
            self._assets_cache,
            getattr(self, "_today_liquid_delta_cache", 0.0),
        )

    def _compute_today_liquid_delta(self):
        """Bugünkü nakit hareket toplamı (gelir − gider). Yalnızca veri üretir;
        arka plan thread'inden çağrılabilir."""
        today_liquid_delta = 0.0
        with managed_connection() as conn_t:
            rows = conn_t.execute(
                "SELECT amount, type FROM transactions "
                "WHERE date(transaction_date) = date('now', 'localtime') "
                f"AND {COMPLETED_TX}"
            ).fetchall()
        for t_amt, t_typ in rows:
            try:
                val = float(decrypt(str(t_amt), SECRET_KEY))
            except Exception:
                val = 0.0
            if t_typ in ("income", "Gelir"):
                today_liquid_delta += val
            elif t_typ in ("expense", "Gider"):
                today_liquid_delta -= val
        return today_liquid_delta

    def update_wealth_card(self, enriched_assets, today_liquid_delta=None):
        """Toplam Varlık kartını günceller. `today_liquid_delta` arka planda
        hesaplanıp verilmişse DB'ye hiç dokunulmaz; verilmemişse (eski senkron
        çağıranlar için) yalnızca gerektiğinde yerinde hesaplanır."""
        liquid_cash = getattr(self, "_liquid_balance_cache", 0.0)

        portfolio_live = sum(
            a["total_value"]
            for a in enriched_assets
            if a.get("total_value") is not None
        )
        total_wealth = liquid_cash + portfolio_live

        asset_pnl = sum(
            a["pnl_amount"] for a in enriched_assets if a.get("pnl_amount") is not None
        )

        if today_liquid_delta is None and enriched_assets:
            try:
                today_liquid_delta = self._compute_today_liquid_delta()
            except Exception:
                today_liquid_delta = 0.0
        if today_liquid_delta is None:
            today_liquid_delta = 0.0
        # toggle_wealth_visibility gibi yeni veri gerektirmeyen çağıranlar
        # (yalnızca görünürlük değişimi) DB'ye hiç dokunmadan bu son bilinen
        # değeri yeniden kullanabilsin diye önbelleğe alınır.
        self._today_liquid_delta_cache = today_liquid_delta

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

        with managed_connection() as conn:
            rows = conn.execute(
                "SELECT amount, type, transaction_date FROM transactions"
                f" WHERE {COMPLETED_TX}"
            ).fetchall()

        current_net = prev_net = 0.0

        for amount_enc, t_type, t_date in rows:
            if not t_date:
                continue
            try:
                t_dt = datetime.datetime.strptime(t_date[:10], "%Y-%m-%d").date()
                amount = float(decrypt(amount_enc, SECRET_KEY))
            except (ValueError, TypeError):
                # ValueError iki kaynaktan gelebilir ve İKİSİ de bu satırın
                # atlanmasını gerektirir: strptime'ın bozuk tarih metnini
                # ayrıştıramaması, ya da float()'ın "[Şifreli Veri]" yer
                # tutucusunu sayıya çevirememesi.
                continue

            val = (
                amount
                if t_type in ("income", "Gelir")
                else -amount if t_type in ("expense", "Gider") else 0.0
            )

            if current_start <= t_dt <= now:
                current_net += val
            elif prev_start <= t_dt < prev_end:
                prev_net += val

        if prev_net == 0:
            change_rate = (
                100.0 if current_net > 0 else -100.0 if current_net < 0 else 0.0
            )
        else:
            change_rate = ((current_net - prev_net) / abs(prev_net)) * 100

        return change_rate

    def _apply_change_rate(self, rate):
        try:
            if self.root and "change_rate_label" in self.root.ids:
                label = self.root.ids.change_rate_label
                if rate > 0:
                    label.text = f"+%{rate:.1f}"
                    label.text_color = ftheme.accent(self.theme_cls, "green")
                elif rate < 0:
                    label.text = f"-%{abs(rate):.1f}"
                    label.text_color = ftheme.accent(self.theme_cls, "red")
                else:
                    label.text = "%0.0"
                    label.text_color = ftheme.accent(self.theme_cls, "muted")
        except Exception as e:
            print("Error updating change rate UI:", e)

    # -------------------------------------------------------------------------
    # List & Navigation Interactions
    # -------------------------------------------------------------------------
    # Zaman filtresi butonları hem sabit Türkçe anahtar (alt satırdaki
    # butonlar) hem de dile göre çevrilen segmented control metniyle
    # çağrılabiliyor; ikincisi İngilizce modda "1 Ay" gibi anahtarlarla asla
    # eşleşmeyeceği için gelen metni önce kanonik Türkçe karşılığına çeviriyoruz.
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
        except Exception:
            pass

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
            # update_metrics_and_goals metrikleri ve değişim oranını aynı
            # arka-plan paketinde hesaplar.
            self.update_metrics_and_goals()
            if self.root and "chart_master_box" in self.root.ids:
                self.root.ids.chart_master_box.refresh_dashboard(
                    getattr(self, "home_filter", "Bugün")
                )
        except Exception as e:
            print("Error updating UI metrics:", e)

        try:
            self.refresh_insights()
        except Exception as e:
            print("Error refreshing insights:", e)

        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")
        self._refresh_recent_transactions(list_filter)
        self._dashboard_rendered_cache_key = dashboard_key
        return True

    def _refresh_recent_transactions(self, list_filter=None):
        """Yalnız son işlemler listesini arka planda yeniler."""
        import threading

        if not list_filter:
            list_filter = getattr(self, "home_filter", "Günlük")

        def fetch_task():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Tek gövde + filtreye özel tarih koşulu: aynı SELECT'i altı kez
                # tekrarlamak, birine status filtresi eklemeyi unutmayı çok
                # kolaylaştırıyordu. "Bekleyen İşlemler" ayrı panelde gösterilir,
                # bu liste yalnızca bakiyeye işlenmiş kayıtları gösterir.
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
                cursor.execute(query)
                transactions_raw = cursor.fetchall()
                conn.close()

                processed_items = []
                for t_type, category, amount_enc, desc_enc, t_date in transactions_raw:
                    # DAR TUTULDU (bkz. docs/ROADMAP.md Faz 2 "except ayrımı",
                    # PR #13). Bu iki blok ÇIPLAK `except:` idi — yani
                    # KeyboardInterrupt/SystemExit/MemoryError'ı bile yutup
                    # 0.0'a düşürüyorlardı. decrypt() kendi içinde asla raise
                    # etmez (bkz. utils/crypto.py), buraya ulaşabilen tek
                    # gerçek hata float()'ın "[Şifreli Veri]" yer tutucusunu
                    # ya da None'ı sayıya çevirememesidir — codebase'in geri
                    # kalanında zaten tam olarak bu iki tipe daraltılmıştı,
                    # yalnızca bu iki satır atlanmıştı.
                    try:
                        dec_amt = float(decrypt(str(amount_enc), SECRET_KEY))
                    except (ValueError, TypeError):
                        dec_amt = 0.0

                    try:
                        dec_desc = (
                            decrypt(str(desc_enc), SECRET_KEY) if desc_enc else ""
                        )
                    except (ValueError, TypeError):
                        dec_desc = ""

                    processed_items.append(
                        (t_type, category, dec_amt, dec_desc, t_date)
                    )

                Clock.schedule_once(
                    lambda dt: self._render_recent_transactions(processed_items), 0
                )
            except Exception as e:
                print("Error fetching recent transactions:", e)

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

            for t_type, category, amount, decrypted_desc, t_date in transactions:
                cat_lower = category.lower() if category else ""
                icon_data = next(
                    (v for k, v in icon_mapping.items() if k in cat_lower), None
                )
                brand_text = f"{decrypted_desc or ''} {category or ''}".strip()
                brand_icon = resolve_cached_brand_icon_path(brand_text)
                brand_key, _ = classify_brand(brand_text)
                if brand_key and not brand_icon:
                    brand_names_to_prefetch.add(brand_text)

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
                        "text": translate(category),
                        "secondary_text": f"{t_date[:10]} | {amount_text}",
                        "icon_source": brand_icon or "",
                        "icon_name": icon_name,
                        "icon_color": list(icon_col),
                    }
                )

            recent_list.data = data
            if brand_names_to_prefetch:
                self._prefetch_recent_brand_icons(brand_names_to_prefetch, transactions)
        except Exception as e:
            print("Error rendering recent UI:", e)

    def _prefetch_recent_brand_icons(self, brand_names, transactions):
        """Eksik işlem markalarını arka planda indirip listeyi bir kez yeniler."""
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
        """Kayıtlı PIN varsa girişe, yoksa ilk kurulum ekranına yönlendirir."""
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
            pass
        return "pin_setup"

    def route_after_auth(self):
        """Kimlik doğrulama sonrası gidilecek ekran: 'account_setup' ya da 'home'.

        Varsayılan hesap seed'i kaldırıldığından taze kurulumda hiç hesap
        olmayabilir. İşlem yazan her akış geçerli bir hesap id'si gerektirir
        (bkz. database/db.py::adjust_account_balance içindeki koruma), bu yüzden
        hesap oluşturulmadan dashboard'a geçilmesine izin verilmez — aksi halde
        kullanıcı gelir/gider girip hata mesajlarıyla karşılaşırdı.
        """
        try:
            from services.account_service import AccountService

            if not AccountService.has_any_account():
                return "account_setup"
        except Exception as exc:
            # Kontrol edilemiyorsa kullanıcıyı kilitlemektense dashboard'a al.
            print("Hesap kontrolü yapılamadı:", exc)
        return "home"

    def create_first_account(self):
        """Onboarding ekranından ilk vadesiz/nakit hesabı oluşturur."""
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
        # Hesap yokken atlanan ilk yükleme adımlarını şimdi çalıştır.
        Clock.schedule_once(lambda dt: self.render_accounts(), 0)
        Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0.05)

    def setup_pin(self):
        pin = self.root.ids.pin_setup_input.text.strip()
        confirmation = self.root.ids.pin_confirm_input.text.strip()
        error = self.root.ids.pin_setup_error_label

        if not pin.isdigit() or len(pin) < 4:
            error.text = translate("PIN en az 4 rakam olmalıdır.")
            return
        if pin != confirmation:
            error.text = translate("PIN'ler eşleşmiyor.")
            return

        salt = SecurityService.generate_salt()
        pin_hash = SecurityService.hash_password(pin, salt)
        self.config_store.put("security", pin_hash=pin_hash, salt=salt, is_set=True)
        error.text = ""
        self.root.ids.pin_setup_input.text = ""
        self.root.ids.pin_confirm_input.text = ""
        self.root.ids.screen_manager.current = self.route_after_auth()

    def check_login(self):
        pin = self.root.ids.password_input.text.strip()
        if self.authentication_screen() != "login":
            self.root.ids.screen_manager.current = "pin_setup"
            return

        # docs/ROADMAP.md Faz 1 madde 6 (Argon2id'den ayrı bırakılan kısım):
        # ardışık başarısız denemelerden sonra artan gecikme/geçici kilit.
        # Kilitliyken PIN HİÇ doğrulanmaz — ne doğru ne yanlış girişin
        # throttle state'ine hiçbir etkisi olmaz, yalnızca kalan süre
        # gösterilir. State kalıcı (config_store'da): uygulamayı yeniden
        # başlatarak bypass edilemesin diye (bkz. LoginThrottle docstring'i).
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
                # docs/ROADMAP.md Faz 1 madde 6: eski SHA-256 hash'i sessizce
                # Argon2id'ye yükselt. Yalnızca DOĞRU PIN girildiğinde
                # tetiklenir (bu if bloğu zaten başarılı doğrulamanın
                # içinde) — offline bir saldırgan doğru PIN'i bilmeden bu
                # yükseltmeyi kendisi tetikleyemez.
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
        # PIN'i olan mevcut kullanıcı da hesapsız kalabilir (verileri sıfırlarsa
        # tüm tablolar boşalır), o yüzden giriş de aynı kapıdan geçer.
        self.root.ids.screen_manager.current = self.route_after_auth()

    def _handle_failed_login(self, message=None):
        self.root.ids.login_error_label.text = message or translate("Hatalı PIN!")

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
        """Kategori Ayarları > Gelir/Gider arasında geçiş.

        DÜZELTME (performans): varsayılan kategori listesi ~30 gelir + ~50
        gider kategorisi içeriyor (bkz. database/init_db.py). Eskiden bu
        fonksiyon hepsini TEK Clock karesinde, düz bir döngüyle inşa
        ediyordu — her `CategorySettingItem` bir `MDSwitch` içeriyor
        (KivyMD'de inşası pahalı bir widget: kendi animasyon/ripple
        durumu var), yani "Gelir"/"Gider"e her basışta 30-50 tane ağır
        widget'ı SENKRON olarak ana thread'de kurmaya çalışıyordu. Bu, tam
        da kullanıcının bildirdiği "basınca donuyor" hissini üretir —
        `update_metrics_and_goals`/`refresh_insights` gibi diğer ekranların
        zaten kaçındığı aynı sınıf hata, yalnızca burası unutulmuştu.

        Asıl maliyet SQL sorgusu değil (küçük bir tablo, mikrosaniyeler
        sürer) — widget inşası. O yüzden çözüm "arka plan thread'i" değil,
        inşayı birkaç kareye YAYMAK: bir kerede `_CATEGORY_BATCH_SIZE`
        kadar widget eklenir, sonraki grup için `Clock.schedule_once(...,
        0)` ile bir sonraki kareye bırakılır — Kivy aradaki karelerde
        girdi/çizim işleyebilir, tek bir kare asla bloklanmaz.

        Jenerasyon sayacı (`_metrics_generation` vb. ile aynı desen):
        kullanıcı Gelir/Gider arasında hızlıca geçiş yaparsa, eski bir
        yükleme artık geçerli olmayan `settings_list`'e widget eklemeye
        devam etmez.
        """
        if cat_type:
            self.active_category_type = cat_type

        settings_list = self.root.ids.settings_list
        settings_list.clear_widgets()

        self._category_load_generation = getattr(self, "_category_load_generation", 0) + 1
        generation = self._category_load_generation

        def _fetch(dt):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type, importance FROM categories WHERE type = ? ORDER BY name",
                (self.active_category_type,),
            )
            categories = cursor.fetchall()
            conn.close()
            self._add_categories_incrementally(settings_list, categories, generation)

        Clock.schedule_once(_fetch, 0.1)

    _CATEGORY_BATCH_SIZE = 8

    def _add_categories_incrementally(self, settings_list, categories, generation, index=0):
        if generation != self._category_load_generation:
            return  # bayat yükleme — kullanıcı zaten başka bir sekmeye geçti
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
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE categories SET importance = ? WHERE name = ?",
            (new_importance, category_name),
        )
        conn.commit()
        conn.close()
        self.safe_refresh_charts()

    def generate_financial_advice(self, *args):
        """3 SQL sorgusu + decrypt döngüsünü arka planda bitirir, sonucu TEK
        Clock çağrısıyla uygular.

        DÜZELTME (performans): eskiden bu metod ana thread'de senkron
        çalışıyordu ve HEM açılışta HEM de her başarılı işlem eklemesinde
        (transaction_mixin.py) çağrılıyordu — yani en sık kullanılan eylemde
        bile bir donma riski taşıyordu. `update_metrics_and_goals`'ta
        zaten kullanılan aynı thread+Clock deseni buraya da uygulanır.
        Ayrıca: decrypt()'in İLK çağrısı ~250ms'lik tek seferlik bir PBKDF2
        anahtar türetmesi yapıyor (bkz. utils/crypto.py) — bu iş artık hangi
        thread'de düşerse düşsün ana thread'i bloklamaz.
        """
        import threading

        self._advice_generation = getattr(self, "_advice_generation", 0) + 1
        generation = self._advice_generation

        def _work():
            try:
                advice_text = self._compute_financial_advice_text()
            except Exception as e:
                print("Finansal tavsiye hesaplanamadı:", e)
                return

            def _apply(dt):
                if generation != self._advice_generation:
                    return  # bayat sonuç — daha yeni bir tazeleme başladı
                self._apply_financial_advice_text(advice_text)

            Clock.schedule_once(_apply, 0)

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()
        return thread

    def _compute_financial_advice_text(self):
        """Yalnızca veri üretir, hiçbir widget'a dokunmaz (thread güvenli)."""
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
        """Son 3 aylık nakit-akışına dayanan ay-sonu bakiye öngörüsü.

        `services.insights_service.generate_monthly_forecast` günlük
        gelir/gider ortalamasını RK4 projeksiyonuyla ay sonuna kadar ileri
        sürer. Yeterli geçmiş yoksa (< ~3 ay) yanıltıcı bir sayı üretmek
        yerine bunu açıkça söyler. Döner: (metin, "positive"|"negative"|
        "warning"|"neutral" durumu — ikon rengi seçimi için).
        """
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
                    f"Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin {month_end} "
                    "olması bekleniyor. Dikkat: Model bakiyenizin eksiye düşebileceğini "
                    "gösteriyor, harcamalarınızı gözden geçirin."
                ),
                "negative",
            )
        if surplus < 0:
            return (
                translate(
                    f"Son 3 ayın istatistiğine göre mevcut harcama eğiliminiz sürerse bu "
                    f"ay sonunda bakiyeniz {month_end} seviyesine gerileyebilir."
                ),
                "warning",
            )
        if surplus > 0 and forecast["savings_rate"] >= 0.10:
            return (
                translate(
                    f"Son 3 ayın istatistiğine göre bu ay sonunda cebinizde {month_end} "
                    "kalacak; bunu bir yatırım aracı olarak değerlendirebilirsiniz."
                ),
                "positive",
            )
        return (
            translate(
                f"Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin yaklaşık "
                f"{month_end} olması bekleniyor."
            ),
            "neutral",
        )

    def _apply_financial_advice_text(self, advice_text):
        """Ana thread'de çağrılır: yalnızca widget güncellemesi yapar."""
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
            pass

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Dialogs & Reset Functionality
    # -------------------------------------------------------------------------
    def contact_us(self):
        import webbrowser

        def send_email(x):
            webbrowser.open("mailto:support@archlence.com")
            if hasattr(self, "contact_dialog"):
                self.contact_dialog.dismiss()

        self.contact_dialog = MDDialog(
            title=translate("Bize Ulaşın"),
            text=translate(
                "Her türlü soru, öneri ve destek için bize aşağıdaki e-posta adresinden ulaşabilirsiniz:\n\n[b]support@archlence.com[/b]"
            ),
            buttons=[
                ftheme.secondary_button(
                    translate("KAPAT"),
                    self.theme_cls,
                    on_release=lambda x: self.contact_dialog.dismiss(),
                ),
                ftheme.primary_button(
                    translate("E-POSTA GÖNDER"), self.theme_cls, on_release=send_email
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

            conn = get_connection()
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
            conn.close()

            # Şema aynı kalır; yalnız varsayılan, kişisel olmayan başlangıç
            # kayıtları yeniden kurulur.
            initialize_database()
            if self.config_store.exists("security"):
                self.config_store.delete("security")

            # DB yeniden seed edilmiş olsa da hesaplar/portföy/içgörüler eski
            # worker snapshot'larından çiziliyor olabilir. Önce bütün kişisel
            # RAM durumunu ve devam eden worker nesillerini geçersiz kıl.
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

            # Invalidate, açık Kartlarım/Hesaplarım ağacındaki kişisel
            # widget'ları aynı karede söker; warm-up yalnız yeni seed
            # hesaplarını yayımladıktan sonra yeniden render eder.
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
            print("Factory reset failed:", e)


# =========================================================================
# 7. RUNNER ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    if _KivyWindow is None:
        # Bu noktaya yalnızca ARCHLENCE_HEADLESS=1 açıkça set edildiyse
        # ulaşılır — aksi hâlde yukarıdaki Window/MDApp guard'ları pencere
        # kurulamadığında zaten görünür bir hatayla dururdu (bkz. docs/
        # ROADMAP.md Faz 1 madde 2). Bilinçli bir headless çağrısı olduğu
        # için burada sessizce (exit 0) çıkmak doğru — bir GERÇEK kullanıcı
        # bu koda hiç ulaşmaz.
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
