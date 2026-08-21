"""Verify in a real Kivy surface that user-owned text is never translated.

The harness uses the real application, KV files, and a generated SQLite
profile. It verifies account, subscription, savings-goal, and debt names;
checks that controlled enum labels are fully English; and confirms that a
retired locale code still resolves to the English-only public UI.

    xvfb-run -a python scripts/dev/verify_i18n_user_data.py --output visual/i18n
"""

import argparse
import json
import os
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


_SANDBOX = tempfile.mkdtemp(prefix="archlence-i18n-verify-")
os.environ["ARCHLENCE_HOME"] = _SANDBOX
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "xdg-data")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "xdg-cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_SANDBOX, "xdg-state")
os.environ["ARCHLENCE_CONFIG_PATH"] = os.path.join(_SANDBOX, "config.json")

from kivy.clock import Clock                                    # noqa: E402
from kivy.uix.screenmanager import NoTransition                 # noqa: E402

from main import ArchlenceApp                                   # noqa: E402
from ui.components import BentoAccountWidget                    # noqa: E402


ACCOUNT_NAMES = ["Nakit", "Ayarlar", "Gelir"]
GOAL_NAME = "Nakit"
SUBSCRIPTION_NAME = "Ayarlar"


ENUM_EXPECTATIONS = {
    "Hisse": "Stock",
    "Hisse Senedi": "Stock",
    "Nakit / Vadesiz": "Cash / Checking",
}


def seed_profile():
    from database.init_db import initialize_database
    from services.account_service import AccountService
    from services.savings_service import SavingsService

    initialize_database()
    for name in ACCOUNT_NAMES:
        AccountService.create_account(name, "checking", initial_balance=1000.0)
    SavingsService.create_goal(GOAL_NAME, 5000.0)


def _walk(widget):
    yield widget
    for child in widget.children:
        yield from _walk(child)


class I18nVerifier(ArchlenceApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.findings = []
        self.observations = {}
        self.exit_code = 1

    def on_start(self):
        super().on_start()
        Clock.schedule_once(self._enter, 1.5)

    def _enter(self, _dt):
        self.root.ids.screen_manager.transition = NoTransition()
        self.root.ids.screen_manager.current = "home"
        nav = self.root.ids.bottom_nav
        nav.ids.tab_manager.transition = NoTransition()
        nav.switch_tab("accounts_tab")
        self.set_language("en", persist=False)
        self.render_accounts()
        Clock.schedule_once(self._check_english, 1.5)


    def _account_widget_names(self):
        return [
            widget.account_name
            for widget in _walk(self.root)
            if isinstance(widget, BentoAccountWidget) and widget.account_name
        ]

    def _check_english(self, _dt):
        shown = self._account_widget_names()
        self.observations["language"] = self.language
        self.observations["account_names_en"] = shown

        if not shown:
            self.findings.append({
                "step": "ingilizce-hesaplar",
                "reason": "hiç hesap kartı çizilmedi — ölçüm yapılamadı",
            })
            self._finish()
            return

        for name in ACCOUNT_NAMES:
            if name not in shown:
                self.findings.append({
                    "step": "ingilizce-hesaplar",
                    "expected": name,
                    "shown": shown,
                    "reason": "kullanıcının hesap adı İngilizce arayüzde "
                              "değişmiş",
                })

        Clock.schedule_once(self._check_messages, 0.5)

    def _check_messages(self, _dt):
        from ui.i18n import tr, trf

        checks = [
            ("abonelik", trf("{name} aboneliği durduruldu.", language="en",
                             name=SUBSCRIPTION_NAME), SUBSCRIPTION_NAME,
             "Settings"),
            ("hedef", trf("Hedefi Sil: {name}", language="en",
                          name=GOAL_NAME), GOAL_NAME, "Cash"),
            ("borç", trf("{name} Borç Ödeme", language="en",
                         name="Gelir"), "Gelir", "Income"),
        ]
        rendered = {}
        for label, text, must_contain, must_not_contain in checks:
            rendered[label] = text
            if must_contain not in text:
                self.findings.append({
                    "step": f"mesaj-{label}",
                    "shown": text,
                    "reason": "kullanıcı adı mesajdan kayboldu",
                })
            if must_not_contain in text:
                self.findings.append({
                    "step": f"mesaj-{label}",
                    "shown": text,
                    "reason": "kullanıcı adı çevrildi",
                })
        self.observations["messages_en"] = rendered

        enums = {}
        for source, expected in ENUM_EXPECTATIONS.items():
            actual = tr(source, "en")
            enums[source] = actual
            if actual != expected:
                self.findings.append({
                    "step": "enum",
                    "source": source,
                    "shown": actual,
                    "expected": expected,
                    "reason": "etiket tam ve doğru çevrilmedi",
                })
        select = trf("Tür Seç: {type}", language="en", type=tr("Hisse Senedi", "en"))
        enums["Tür Seç"] = select
        if "Senedi" in select:
            self.findings.append({
                "step": "enum",
                "shown": select,
                "reason": "yarı çevrilmiş melez üretildi",
            })
        self.observations["enums_en"] = enums

        Clock.schedule_once(self._check_retired_locale, 0.5)

    def _check_retired_locale(self, _dt):
        self.set_language("tr", persist=False)
        self.render_accounts()
        Clock.schedule_once(self._check_english_fallback, 1.2)

    def _check_english_fallback(self, _dt):
        from ui.i18n import trf

        shown = self._account_widget_names()
        self.observations["account_names_after_retired_locale"] = shown
        self.observations["language_after_retired_locale"] = self.language

        if self.language != "en":
            self.findings.append({
                "step": "retired-locale",
                "reason": "unsupported locale did not fall back to English",
            })
        for name in ACCOUNT_NAMES:
            if name not in shown:
                self.findings.append({
                    "step": "english-fallback-accounts",
                    "expected": name,
                    "shown": shown,
                    "reason": "user-owned account name changed after fallback",
                })

        rendered = trf("{name} aboneliği durduruldu.", language=None,
                       name=SUBSCRIPTION_NAME)
        self.observations["message_after_retired_locale"] = rendered
        if rendered != "Ayarlar subscription stopped.":
            self.findings.append({
                "step": "retired-locale",
                "shown": rendered,
                "reason": "template did not render in English after fallback",
            })
        self._finish()

    def _finish(self):
        report = {"observations": self.observations, "findings": self.findings}
        (self.output / "i18n-user-data.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"İngilizce hesap adları: {self.observations.get('account_names_en')}",
              flush=True)
        if self.findings:
            for item in self.findings:
                print(f"[BULGU] {item['step']}: {item['reason']}", flush=True)
            print(f"::error::{len(self.findings)} i18n bulgusu", flush=True)
            self.exit_code = 1
        else:
            print("Kullanıcı verisi iki dilde de değişmiyor; etiketler çevriliyor.",
                  flush=True)
            self.exit_code = 0
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    seed_profile()
    app = I18nVerifier(args.output)
    app.run()
    raise SystemExit(app.exit_code)
