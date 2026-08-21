"""Uygulama açılışında yarım kalmış bir restore'u güvenle çözer.

NEDEN AYRI MODÜL: `main.py` Kivy'yi import ediyor, dolayısıyla oradaki bir
fonksiyon başsız (headless) test edilemezdi. Kurtarma, DB/anahtar/config'e
dokunan HER ŞEYDEN önce çalışmak zorunda olduğu için kendi sınırında duruyor
ve doğrudan çağrılabiliyor.

SIRA ZORUNLULUĞU (`main.py::build` içinde):

    run_startup_recovery()          <-- burada
    _warm_crypto_key_in_background()    anahtar yüklenir
    migrate_legacy_database_location()
    initialize_database()               DB açılır, migration koşar
    JsonStore(config)                   config okunur

Kurtarma bu üçünden ÖNCE bitmezse, uygulama yarım bir generation üzerinde
çalışmaya başlar: DB bir yedekten, config başka bir generation'dan olabilir.
"""

from __future__ import annotations

from enum import Enum

from utils.errors import DataMigrationError


class RecoveryOutcome(str, Enum):
    """Açık sözleşme — sessiz `None` dönüşü yok."""

    NOT_REQUIRED = "not-required"
    COMPLETED = "completed"
    MANUAL_INTERVENTION_REQUIRED = "manual-intervention-required"


class StartupRecoveryError(DataMigrationError):
    """Kurtarma güvenle tamamlanamadı; normal açılış SÜRDÜRÜLMEMELİ.

    `DataMigrationError`'dan türüyor ki mevcut hata sınırları bunu zaten
    tanısın, ama ayrı bir tip olarak yakalanabilsin.
    """

    def __init__(self, message, *, outcome):
        super().__init__(message)
        self.outcome = outcome


USER_MESSAGE = (
    "Önceki bir geri yükleme işlemi yarıda kalmış ve otomatik olarak "
    "onarılamadı. Verileriniz olduğu gibi korundu; hiçbir dosyanın üzerine "
    "yazılmadı. Devam etmeden önce yedekleme/kurtarma belgelerine bakın."
)


RECOVERY_FAILURE_TITLE = "Geri yükleme tamamlanamadı"
SCHEMA_TOO_NEW_TITLE = "Veritabanı bu sürümden yeni"
DATA_INTEGRITY_TITLE = "Veritabanı doğrulanamadı"


def build_startup_failure_root(title, message):
    """Açılış hatası için minimal, kendi kendine yeten bir root üretir.

    `ui/dashboard.kv` YÜKLENMEZ ve hiçbir `ids` referansı kullanılmaz: bu
    yüzeyin ayakta olması için uygulamanın geri kalanının hazır olması
    gerekmiyor. Metin root'un İÇİNDE yazılı, yani diyalog hiç açılamasa bile
    kullanıcı ne olduğunu görür.
    """
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label


    root = BoxLayout(orientation="vertical", padding=32, spacing=16)

    heading = Label(
        text=title,
        font_size=24,
        bold=True,
        halign="center",
        valign="middle",
        size_hint_y=None,
        height=64,
        color=(0.85, 0.15, 0.15, 1),
    )
    heading.bind(size=lambda widget, value: setattr(
        widget, "text_size", (value[0], None)))

    body = Label(
        text=message,
        font_size=15,
        halign="center",
        valign="top",
        color=(0.2, 0.2, 0.2, 1),
    )
    body.bind(size=lambda widget, value: setattr(
        widget, "text_size", value))

    root.add_widget(heading)
    root.add_widget(body)
    return root


def present_startup_failure(app, title, message, *, schedule=None):
    """Fail-closed açılış yüzeyini kurar ve root'u DÖNDÜRÜR.

    İSTİSNA FIRLATMAZ — fırlatmak, olay döngüsünün hiç başlamaması demekti.

    `message` DAİMA ilgili modülün sabit kullanıcı metni olmalıdır; exception
    metni, traceback, dosya yolu, tablo adı, rowid, anahtar, parola ya da
    finansal değer buraya GEÇİRİLMEMELİ. Teknik ayrıntı çağıranın log
    satırında kalır.

    `schedule` testler için enjekte edilebilir; verilmezse diyalog Kivy'nin
    `Clock`'u ile İLK KAREDE, yani pencere ve olay döngüsü hazır olduktan
    sonra açılır.
    """
    app._startup_recovery_failure = message
    app._startup_failure_title = title
    root = build_startup_failure_root(title, message)

    def _open_dialog(*_args):
        from kivymd.uix.dialog import MDDialog

        dialog = MDDialog(title=title, text=message, auto_dismiss=False)
        app._startup_failure_dialog = dialog
        dialog.open()
        return dialog

    if schedule is None:
        from kivy.clock import Clock

        Clock.schedule_once(_open_dialog, 0)
    else:
        schedule(_open_dialog)
    return root


def present_startup_recovery_failure(app, message):
    """Kurtarma hatası — ortak yüzeyin ince sarmalayıcısı."""
    return present_startup_failure(app, RECOVERY_FAILURE_TITLE, message)


def present_schema_too_new_failure(app, message):
    """Şema kuşağı hatası (A-5) — ortak yüzeyin ince sarmalayıcısı."""
    return present_startup_failure(app, SCHEMA_TOO_NEW_TITLE, message)


def present_data_integrity_failure(app, message):
    """Veri bütünlüğü hatası — ortak yüzeyin ince sarmalayıcısı."""
    return present_startup_failure(app, DATA_INTEGRITY_TITLE, message)


def run_startup_recovery(db_path=None, *, config_path=None):
    """Yarım restore varsa geri alır; yoksa hiçbir şey yapmaz.

    Döner: `(RecoveryOutcome, detay_sözlüğü)`.

    FAIL-CLOSED: journal bozuksa, tanınmayan bir state taşıyorsa ya da geri
    alma sırasında hata olursa `StartupRecoveryError` fırlatır. Çağıran bunu
    yakalayıp açılışı DURDURMALIDIR — bozuk bir journal'a bakıp "her şey
    yolunda" varsaymak, karma bir profille açılmaktan daha kötüdür.
    """
    from database.db import DB_NAME
    from services.backup_service import recover_interrupted_restore

    target_db = db_path or DB_NAME
    try:
        result = recover_interrupted_restore(
            db_path=target_db, config_path=config_path
        )
    except DataMigrationError as exc:
        raise StartupRecoveryError(
            USER_MESSAGE,
            outcome=RecoveryOutcome.MANUAL_INTERVENTION_REQUIRED,
        ) from exc
    except OSError as exc:

        raise StartupRecoveryError(
            USER_MESSAGE,
            outcome=RecoveryOutcome.MANUAL_INTERVENTION_REQUIRED,
        ) from exc

    if not result.get("recovered"):
        return RecoveryOutcome.NOT_REQUIRED, result

    from utils.logging_config import get_logger

    get_logger().warning(
        "Yarım kalmış geri yükleme açılışta onarıldı (state=%s).",
        result.get("state"),
    )
    return RecoveryOutcome.COMPLETED, result
