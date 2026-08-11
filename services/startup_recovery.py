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


# Kullanıcıya gösterilecek metin. Journal içeriği, dosya yolu, anahtar veya
# finansal veri İÇERMEZ — kurtarma hatası mesajı bir sızıntı yüzeyi olmamalı.
USER_MESSAGE = (
    "Önceki bir geri yükleme işlemi yarıda kalmış ve otomatik olarak "
    "onarılamadı. Verileriniz olduğu gibi korundu; hiçbir dosyanın üzerine "
    "yazılmadı. Devam etmeden önce yedekleme/kurtarma belgelerine bakın."
)


def present_startup_recovery_failure(app, message):
    """Kurtarma hatasını kullanıcıya güvenli biçimde gösterir.

    Ayrı fonksiyon olmasının sebebi test edilebilirlik: gerçek Kivy pencere
    sağlayıcısı olmadan da çağrıldığı ve DOĞRU metni aldığı doğrulanabilsin.

    `message` DAİMA `USER_MESSAGE` olmalıdır — çağıran, exception'ın kendi
    metnini veya traceback'ini buraya geçirmemelidir. Anahtar, parola,
    journal içeriği veya dosya yolu kullanıcı metnine girmemeli.
    """
    from kivymd.uix.dialog import MDDialog

    dialog = MDDialog(title="Geri yükleme tamamlanamadı", text=message)
    dialog.open()
    return dialog


def present_schema_too_new_failure(app, message):
    """Şema kuşağı hatasını kullanıcıya güvenli biçimde gösterir (A-5).

    Kardeşiyle aynı sözleşme: `message` DAİMA
    `database.init_db.SCHEMA_TOO_NEW_MESSAGE` olmalı, exception metni veya
    bulunan/desteklenen sürüm numaraları buraya GEÇİRİLMEMELİ. Numaralar
    geliştirici log'una gider, kullanıcı metnine değil.
    """
    from kivymd.uix.dialog import MDDialog

    dialog = MDDialog(title="Veritabanı bu sürümden yeni", text=message)
    dialog.open()
    return dialog


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
        # Geri alma sırasındaki dosya sistemi hatası da fail-closed.
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
