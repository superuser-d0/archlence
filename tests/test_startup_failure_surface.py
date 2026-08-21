"""Açılış hatası ekranı GERÇEKTEN gösterilebilir olmalı.

ÖLÇÜLEN KUSUR: üç açılış hatası yolu da (`StartupRecoveryError`,
`SchemaTooNewError`, `FinancialDataIntegrityError`) `MDDialog.open()` çağırıp
ardından istisnayı YENİDEN FIRLATIYORDU. Kivy'nin `App.run()` sırası şu:

    _run_prepare()   ->  self.build() çağrılır, root Window'a eklenir
    runTouchApp()    ->  OLAY DÖNGÜSÜ burada başlar

`build()` fırlatınca `_run_prepare` yarıda kalıyor ve `runTouchApp()`'e HİÇ
ulaşılmıyor. Gerçek Kivy penceresiyle ölçüldü:

    build() istisna firlatti mi : FinancialDataIntegrityError
    runTouchApp CAGRILDI MI     : False
    app.root                    : None
    MDDialog.open() cagrildi mi : ['Veritabanı doğrulanamadı']

Yani diyalog nesnesi kuruluyor ve `open()` çağrılıyor — bir MOCK-CALL TESTİ
bunu YEŞİL görürdü — ama olay döngüsü hiç başlamadığı için ekrana tek piksel
çizilmiyor. Kullanıcının gördüğü şey traceback.

BU DOSYA MOCK-CALL İLE YETİNMİYOR. Doğruladıkları:
  * `build()` üç hatada da BAŞARIYLA DÖNÜYOR (istisna yok),
  * dönen root `None` değil ve mesajı KENDİ İÇİNDE taşıyor,
  * mesaj gösterimi olay döngüsüne ERTELENİYOR, inline açılmıyor,
  * sonraki veri yükleme yolları (`_run_savings_migration_at_startup`,
    `load_savings_goals`) ÇALIŞMIYOR,
  * `on_start` erken çıkıyor, yani uygulama normal kullanıma devam edemiyor.

YAPRAK WIDGET SINIFLARI NEDEN DEĞİŞTİRİLİYOR: `kivy.uix.widget.Widget.__init__`
`EventLoop.ensure_window()` çağırıyor ve pencere sağlayıcısı olmayan başsız
test ortamında bu `sys.exit(1)` yapıyor. Yani bu ortamda HİÇBİR Kivy widget'ı
kurulamıyor. Test edilen fonksiyon (`build_startup_failure_root`) GERÇEK
olarak koşuyor; yalnız `BoxLayout`/`Label` taban sınıfları hafif birer
karşılıkla değiştiriliyor ki kurduğu ağaç okunabilsin. Widget'ların gerçekten
ÇİZİLDİĞİ `scripts/dev/verify_startup_failure_surface.py` içinde, gerçek
pencerede ölçülüyor.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest import mock

from database.init_db import DATA_INTEGRITY_MESSAGE, SCHEMA_TOO_NEW_MESSAGE
from services.startup_recovery import (
    DATA_INTEGRITY_TITLE,
    RECOVERY_FAILURE_TITLE,
    SCHEMA_TOO_NEW_TITLE,
    USER_MESSAGE as RECOVERY_USER_MESSAGE,
    RecoveryOutcome,
    StartupRecoveryError,
    build_startup_failure_root,
    present_startup_failure,
)

_TX_INSERT = (
    "INSERT INTO transactions "
    "(account_id, amount, type, category, description, transaction_date) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

#: Üç hatanın ortak yüzeyi — hepsi aynı sözleşmeyi taşımalı.
SURFACES = (
    ("kurtarma", RECOVERY_FAILURE_TITLE, RECOVERY_USER_MESSAGE),
    ("şema kuşağı", SCHEMA_TOO_NEW_TITLE, SCHEMA_TOO_NEW_MESSAGE),
    ("veri bütünlüğü", DATA_INTEGRITY_TITLE, DATA_INTEGRITY_MESSAGE),
)


class _StandInWidget:
    """Pencere gerektirmeyen, Kivy widget yüzeyinin gerekli kısmı."""

    def __init__(self, **kwargs):
        self.children = []
        self.bindings = {}
        for name, value in kwargs.items():
            setattr(self, name, value)

    def add_widget(self, widget):
        self.children.append(widget)

    def bind(self, **kwargs):
        self.bindings.update(kwargs)


@contextmanager
def _headless_widgets():
    with mock.patch("kivy.uix.boxlayout.BoxLayout", _StandInWidget), \
            mock.patch("kivy.uix.label.Label", _StandInWidget):
        yield


def _walk(widget):
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _walk(child)


def _rendered_text(root):
    return " ".join(
        str(widget.text) for widget in _walk(root)
        if getattr(widget, "text", None)
    )


class SafeRootContractTest(unittest.TestCase):
    def test_the_root_is_built_and_is_not_none(self):
        for label, title, message in SURFACES:
            with self.subTest(surface=label), _headless_widgets():
                self.assertIsNotNone(build_startup_failure_root(title, message))

    def test_the_message_is_inside_the_root_not_only_in_a_dialog(self):
        """Diyalog hiç açılamasa bile kullanıcı ne olduğunu görmeli."""
        for label, title, message in SURFACES:
            with self.subTest(surface=label), _headless_widgets():
                rendered = _rendered_text(
                    build_startup_failure_root(title, message)
                )
                self.assertIn(title, rendered)
                self.assertIn(message, rendered)

    def test_the_root_needs_no_window_metrics(self):
        """`dp()`/`sp()` pencere yoksa `TypeError` fırlatıyor — kullanılmamalı.

        Hata yüzeyi, bozulduğunu bildirdiği makineye bağımlı olmamalı.
        """
        import kivy.metrics

        def exploding(*_args, **_kwargs):
            raise AssertionError("hata yüzeyi metrik başlatmasına bağımlı")

        with _headless_widgets(), \
                mock.patch.object(kivy.metrics, "dp", exploding), \
                mock.patch.object(kivy.metrics, "sp", exploding):
            self.assertIsNotNone(
                build_startup_failure_root(*SURFACES[0][1:])
            )

    def test_the_root_carries_no_dashboard_surface(self):
        with _headless_widgets():
            root = build_startup_failure_root(*SURFACES[0][1:])
        ids = getattr(root, "ids", {})
        for forbidden in ("screen_manager", "bottom_nav", "password_input"):
            self.assertNotIn(forbidden, ids)

    def test_the_dialog_is_scheduled_not_opened_inline(self):
        """Diyalog `build()` içinde DEĞİL, ilk karede açılmalı."""
        scheduled = []
        app = mock.Mock()
        with _headless_widgets():
            root = present_startup_failure(
                app, DATA_INTEGRITY_TITLE, DATA_INTEGRITY_MESSAGE,
                schedule=scheduled.append,
            )
        self.assertIsNotNone(root)
        self.assertEqual(
            len(scheduled), 1,
            "mesaj gösterimi olay döngüsüne ERTELENMEDİ",
        )
        self.assertTrue(callable(scheduled[0]))
        self.assertEqual(app._startup_recovery_failure, DATA_INTEGRITY_MESSAGE)
        self.assertEqual(app._startup_failure_title, DATA_INTEGRITY_TITLE)

    def test_no_surface_leaks_technical_metadata(self):
        for label, title, message in SURFACES:
            for forbidden in (
                "traceback", "sqlite", "rowid", "finance.db", "account_id",
                "transactions", ".db", "journal",
            ):
                with self.subTest(surface=label, forbidden=forbidden):
                    self.assertNotIn(forbidden, f"{title} {message}".lower())


class BuildReturnsSafeRootTest(unittest.TestCase):
    """`build()` üç hatada da FIRLATMAMALI, güvenli root DÖNDÜRMELİ."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "finance.db"
        self.key = os.urandom(32)
        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database

        initialize_database()

    def _inject_orphan(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                _TX_INSERT,
                (424242, "x", "expense", "Eski", "öksüz",
                 "2026-01-01 00:00:00"),
            )
            conn.commit()

    def _build(self, *, recovery_error=None, init_error=None):
        """GERÇEK `ArchlenceApp.build`'i hata yüzeyine kadar çalıştırır."""
        import main

        app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        app.background_tasks = None
        loaded = []
        scheduled = []

        def recovery(*_args, **_kwargs):
            if recovery_error is not None:
                raise recovery_error

        def initialise(*_args, **_kwargs):
            if init_error is not None:
                raise init_error
            from database.init_db import initialize_database

            initialize_database()

        patches = [
            mock.patch("main.setup_appimage_desktop_integration", lambda: None),
            mock.patch("main.migrate_legacy_database_location", lambda: False),
            mock.patch("main.initialize_database", initialise),
            mock.patch("services.startup_recovery.run_startup_recovery",
                       recovery),
            mock.patch.object(
                main.ArchlenceApp, "_warm_crypto_key_in_background",
                lambda self: None),
            mock.patch.object(
                main.ArchlenceApp, "_run_savings_migration_at_startup",
                lambda self: loaded.append("savings_migration")),
            mock.patch.object(
                main.ArchlenceApp, "load_savings_goals",
                lambda self: loaded.append("load_savings_goals")),
            mock.patch("main.Clock", mock.MagicMock()),
            mock.patch("kivy.clock.Clock.schedule_once",
                       lambda callback, *a, **k: scheduled.append(callback)),
            mock.patch("services.background_task_manager.BackgroundTaskManager",
                       mock.MagicMock()),
        ]
        for patch in patches:
            patch.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        with _headless_widgets():
            try:
                root = main.ArchlenceApp.build(app)
            except AttributeError:
                # SAĞLIKLI YOL bu iskelet nesnede `theme_cls`e kadar
                # ilerliyor ve orada duruyor; hata yolları çok daha önce
                # dönüyor. Kontrollü duruş, "hata yüzeyine hiç girilmedi"
                # kanıtının kendisi.
                root = None
        return app, root, loaded, scheduled

    def _assert_safe_surface(self, app, root, loaded, scheduled, message, title):
        self.assertIsNotNone(root, "güvenli root dönmedi")
        self.assertEqual(app._startup_recovery_failure, message)
        rendered = _rendered_text(root)
        self.assertIn(title, rendered)
        self.assertIn(message, rendered)
        self.assertEqual(
            loaded, [],
            f"açılış hatasından sonra veri yükleme yolu çalıştı: {loaded}",
        )
        self.assertEqual(
            len(scheduled), 1,
            "mesaj gösterimi olay döngüsüne ertelenmedi",
        )

    def test_recovery_failure_returns_the_safe_root(self):
        app, root, loaded, scheduled = self._build(
            recovery_error=StartupRecoveryError(
                "ic ayrinti: /gizli/yol/finance.db",
                outcome=RecoveryOutcome.MANUAL_INTERVENTION_REQUIRED,
            )
        )
        self._assert_safe_surface(
            app, root, loaded, scheduled,
            RECOVERY_USER_MESSAGE, RECOVERY_FAILURE_TITLE,
        )
        self.assertNotIn("/gizli/yol", _rendered_text(root))

    def test_schema_too_new_returns_the_safe_root(self):
        from utils.errors import SchemaTooNewError

        app, root, loaded, scheduled = self._build(
            init_error=SchemaTooNewError(99, 2)
        )
        self._assert_safe_surface(
            app, root, loaded, scheduled,
            SCHEMA_TOO_NEW_MESSAGE, SCHEMA_TOO_NEW_TITLE,
        )
        self.assertNotIn("99", _rendered_text(root))

    def test_data_integrity_failure_returns_the_safe_root(self):
        self._inject_orphan()
        app, root, loaded, scheduled = self._build()
        self._assert_safe_surface(
            app, root, loaded, scheduled,
            DATA_INTEGRITY_MESSAGE, DATA_INTEGRITY_TITLE,
        )
        self.assertNotIn("424242", _rendered_text(root))

    def test_a_healthy_startup_is_unaffected_by_the_failure_path(self):
        """Kapı yalnız hata durumunda devreye girmeli."""
        import main

        app, root, loaded, scheduled = self._build()
        # Sağlıklı profilde hata yüzeyine hiç girilmemeli: bayrak kurulmaz,
        # root döndürülmez, mesaj ertelenmez — ve savings migration ile hedef
        # yüklemesi NORMAL biçimde çalışır.
        self.assertIsNone(getattr(app, "_startup_recovery_failure", None))
        self.assertIsNone(root, "sağlıklı açılışta hata root'u döndürüldü")
        self.assertEqual(scheduled, [])
        self.assertEqual(loaded, ["savings_migration", "load_savings_goals"])
        del main


class OnStartIsInertAfterFailureTest(unittest.TestCase):
    """Kivy `_run_prepare` `build()`'den HEMEN SONRA `on_start` dispatch ediyor."""

    #: `on_start`'ın hata yüzeyi etkinken ÇAĞIRMAMASI gereken adımlar.
    FORBIDDEN_STEPS = (
        "_normalize_card_shadows", "purge_logs", "vacuum_database",
        "write_daily_balance_snapshot", "setup_dynamic_months",
        "safe_refresh_charts", "load_recent_transactions",
        "generate_financial_advice", "load_active_debts",
        "load_active_assets", "load_asset_history",
    )

    def test_on_start_returns_immediately_when_the_surface_is_active(self):
        import main

        app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        app._startup_recovery_failure = DATA_INTEGRITY_MESSAGE

        touched = []
        for name in self.FORBIDDEN_STEPS:
            setattr(
                app, name,
                (lambda captured: lambda *a, **k: touched.append(captured))(name),
            )

        with mock.patch("main.Clock", mock.MagicMock()):
            main.ArchlenceApp.on_start(app)

        self.assertEqual(
            touched, [],
            f"hata yüzeyi etkinken şu adımlar çalıştı: {touched}",
        )

    def test_on_start_does_not_stop_a_healthy_startup(self):
        import main

        app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        app._startup_recovery_failure = None
        reached = []
        app._normalize_card_shadows = lambda: reached.append("normalize")
        sentinel = RuntimeError("kontrollü durdurma")

        with mock.patch("main.Clock", mock.MagicMock(
                schedule_once=mock.Mock(side_effect=sentinel))):
            with self.assertRaises(RuntimeError):
                main.ArchlenceApp.on_start(app)

        self.assertEqual(
            reached, ["normalize"],
            "sağlıklı açılışta on_start erken çıktı",
        )


if __name__ == "__main__":
    unittest.main()
