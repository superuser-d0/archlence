"""Açılış hatası yüzeyi GERÇEK pencerede çiziliyor mu — ölçer.

NEDEN VAR: üç açılış hatası yolu da `MDDialog.open()` çağırıp ardından
istisnayı yeniden fırlatıyordu. Kivy'nin sırası şu:

    App.run()
      _run_prepare()   ->  build() çağrılır, root Window'a eklenir
      runTouchApp()    ->  OLAY DÖNGÜSÜ burada başlar

`build()` fırlatınca `_run_prepare` yarıda kalıyor ve `runTouchApp()`'e HİÇ
ulaşılmıyor. Bu betikle ölçülen eski davranış:

    build() istisna firlatti mi : FinancialDataIntegrityError
    runTouchApp CAGRILDI MI     : False
    app.root                    : None
    MDDialog.open() cagrildi mi : ['Veritabanı doğrulanamadı']

Diyalog nesnesi kuruluyor ve `open()` çağrılıyor — bir MOCK-CALL TESTİ bunu
YEŞİL görürdü — ama tek piksel çizilmiyor. Birim testi bu farkı göremez;
bu betik görür, çünkü gerçek pencerede gerçek olay döngüsünü çalıştırıyor.

Ölçtüğü şeyler:
  1. `build()` istisna FIRLATMIYOR,
  2. `runTouchApp()` gerçekten çağrılıyor (olay döngüsü başlıyor),
  3. `app.root` bir Kivy `Widget` ve pencereye eklenmiş,
  4. başlık ve mesaj metni ekrandaki widget ağacında GERÇEKTEN var,
  5. hata diyaloğu olay döngüsü başladıktan SONRA açılıyor,
  6. root'ta finansal ekranın hiçbir parçası yok,
  7. `on_start` veri yükleme adımlarını çalıştırmıyor,
  8. kullanıcı metni teknik ayrıntı sızdırmıyor.

    xvfb-run -a python scripts/dev/verify_startup_failure_surface.py \
        --output visual/startup-failure
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("KIVY_NO_ARGS", "1")


_SANDBOX = tempfile.mkdtemp(prefix="archlence-startup-verify-")
os.environ["ARCHLENCE_HOME"] = _SANDBOX
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "xdg-data")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "xdg-cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_SANDBOX, "xdg-state")
os.environ["ARCHLENCE_CONFIG_PATH"] = os.path.join(_SANDBOX, "config.json")

import kivy.app                                               # noqa: E402
import kivy.base                                              # noqa: E402
from kivy.clock import Clock                                  # noqa: E402
from kivy.uix.widget import Widget                            # noqa: E402
from kivymd.uix.dialog import MDDialog                        # noqa: E402

from database.db import DB_NAME                               # noqa: E402
from database.init_db import (                                # noqa: E402
    DATA_INTEGRITY_MESSAGE,
    initialize_database,
)
from main import ArchlenceApp                                 # noqa: E402
from services.startup_recovery import DATA_INTEGRITY_TITLE    # noqa: E402
from utils.errors import ArchlenceError                       # noqa: E402


FORBIDDEN_IN_USER_TEXT = (
    "traceback", "sqlite", "rowid", "finance.db", "account_id",
    "transactions", "journal", _SANDBOX.lower(),
)


FORBIDDEN_STARTUP_STEPS = (
    "purge_logs", "vacuum_database", "write_daily_balance_snapshot",
    "setup_dynamic_months", "safe_refresh_charts",
    "load_recent_transactions", "generate_financial_advice",
    "load_active_debts", "load_active_assets", "load_asset_history",
)

ORPHAN_ACCOUNT = 424242


def seed_broken_profile():
    """Sağlıklı profil kurar, sonra eski sürümün bırakacağı öksüz satırı yazar."""
    initialize_database()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO transactions (account_id, amount, type, category,"
            " description, transaction_date) VALUES (?,?,?,?,?,?)",
            (ORPHAN_ACCOUNT, "x", "expense", "Eski", "öksüz",
             "2026-01-01 00:00:00"),
        )
        conn.commit()


def _walk(widget):
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _walk(child)


def _rendered_text(root):
    return " ".join(
        str(widget.text) for widget in _walk(root)
        if getattr(widget, "text", None)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    seed_broken_profile()

    observed = {
        "build_raised": None,
        "run_touch_app_called": False,
        "root_type": None,
        "root_is_widget": False,
        "root_attached_to_window": False,
        "dialogs_opened": [],
        "dialog_opened_after_loop_started": False,
        "rendered_text": "",
        "startup_steps_run": [],
    }
    findings = []


    real_run_touch_app = kivy.base.runTouchApp

    def spy_run_touch_app(*call_args, **call_kwargs):
        observed["run_touch_app_called"] = True

        Clock.schedule_once(lambda _dt: _measure_and_stop(), 1.5)
        return real_run_touch_app(*call_args, **call_kwargs)

    kivy.base.runTouchApp = spy_run_touch_app
    kivy.app.runTouchApp = spy_run_touch_app


    real_open = MDDialog.open

    def spy_open(self, *call_args, **call_kwargs):
        observed["dialogs_opened"].append(str(getattr(self, "title", "?")))
        if observed["run_touch_app_called"]:
            observed["dialog_opened_after_loop_started"] = True
        return real_open(self, *call_args, **call_kwargs)

    MDDialog.open = spy_open


    for name in FORBIDDEN_STARTUP_STEPS:
        if hasattr(ArchlenceApp, name):
            setattr(
                ArchlenceApp, name,
                (lambda captured: lambda self, *a, **k:
                    observed["startup_steps_run"].append(captured))(name),
            )

    app = ArchlenceApp()

    def _measure_and_stop():
        root = app.root
        observed["root_type"] = type(root).__name__ if root else None
        observed["root_is_widget"] = isinstance(root, Widget)
        if root is not None:
            observed["rendered_text"] = _rendered_text(root)
            from kivy.core.window import Window

            observed["root_attached_to_window"] = root in Window.children
        app.stop()

    try:
        app.run()
    except ArchlenceError as exc:


        observed["build_raised"] = type(exc).__name__
    finally:
        kivy.base.runTouchApp = real_run_touch_app
        kivy.app.runTouchApp = real_run_touch_app
        MDDialog.open = real_open

    # ── bulgular ─────────────────────────────────────────────────────────
    def fail(step, reason, **extra):
        findings.append(dict(step=step, reason=reason, **extra))

    if observed["build_raised"] is not None:
        fail("build", "build() istisna fırlattı — olay döngüsü hiç başlamaz",
             shown=observed["build_raised"])
    if not observed["run_touch_app_called"]:
        fail("olay-dongusu", "runTouchApp() hiç çağrılmadı; ekran çizilmedi")
    if not observed["root_is_widget"]:
        fail("root", "güvenli root bir Kivy Widget değil",
             shown=observed["root_type"])
    if not observed["root_attached_to_window"]:
        fail("root", "güvenli root pencereye eklenmedi")

    rendered = observed["rendered_text"]
    if DATA_INTEGRITY_TITLE not in rendered:
        fail("metin", "başlık ekrandaki widget ağacında yok")
    if DATA_INTEGRITY_MESSAGE not in rendered:
        fail("metin", "hata mesajı ekrandaki widget ağacında yok")

    if not observed["dialogs_opened"]:
        fail("diyalog", "hata diyaloğu hiç açılmadı")
    elif not observed["dialog_opened_after_loop_started"]:
        fail("diyalog", "diyalog olay döngüsü başlamadan ÖNCE açıldı")

    for forbidden in FORBIDDEN_IN_USER_TEXT:
        if forbidden and forbidden in rendered.lower():
            fail("sizinti", "kullanıcı metni teknik ayrıntı taşıyor",
                 shown=forbidden)
    if str(ORPHAN_ACCOUNT) in rendered:
        fail("sizinti", "kullanıcı metni kayıt kimliği taşıyor")

    if observed["startup_steps_run"]:
        fail("fail-closed", "hata yüzeyi etkinken veri yükleme adımı çalıştı",
             shown=observed["startup_steps_run"])

    report = {"observations": observed, "findings": findings}
    (output / "startup-failure-surface.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"build() fırlattı mı        : {observed['build_raised'] or 'hayır'}",
          flush=True)
    print(f"runTouchApp çağrıldı mı    : {observed['run_touch_app_called']}",
          flush=True)
    print(f"app.root                   : {observed['root_type']}", flush=True)
    print(f"pencereye eklendi mi       : {observed['root_attached_to_window']}",
          flush=True)
    print(f"diyalog (döngüden sonra)   : "
          f"{observed['dialog_opened_after_loop_started']}", flush=True)
    print(f"on_start veri adımları     : "
          f"{observed['startup_steps_run'] or 'çalışmadı'}", flush=True)

    if findings:
        for item in findings:
            print(f"[BULGU] {item['step']}: {item['reason']}", flush=True)
        print(f"::error::{len(findings)} açılış yüzeyi bulgusu", flush=True)
        return 1
    print("Açılış hatası ekranı gerçek pencerede çiziliyor; uygulama "
          "normal kullanıma devam etmiyor.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
