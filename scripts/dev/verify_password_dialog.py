"""Parola değiştirme diyaloğunu GERÇEK Kivy penceresinde ölçer.

NEDEN VAR: `_apply_new_pin` eskiden mevcut parolayı hiç sormuyordu — açık
bırakılmış bir uygulamanın başına oturan herkes parolayı değiştirip sahibini
kilitleyebiliyordu. Düzeltme üç alanlı bir diyalog ve doğrulama zinciri
getirdi; ama bir diyaloğun GERÇEKTEN çizildiğini, alanların maskeli olduğunu
ve metinlerin iki dilde de çevrildiğini birim testi kanıtlayamaz. Bu betik
gerçek `ArchlenceApp`i, gerçek KV'yi ve gerçek bir profili kullanır.

Ölçtüğü şeyler:

  1. Diyalog üç parola alanıyla çiziliyor (Mevcut / Yeni / Yeni Tekrar),
  2. üçü de `password=True` — düz metin ekranda görünmüyor,
  3. yardım metni politikanın kendi metniyle aynı kaynaktan geliyor,
  4. hint ve başlık metinleri Türkçe ve İngilizce'de çevriliyor,
  5. YANLIŞ mevcut parola ile kaydetmek saklanan hash'i DEĞİŞTİRMİYOR,
  6. doğru mevcut parola + geçerli yeni parola değişikliği tamamlıyor,
  7. diyalog kapandığında hassas alan referansları bırakılıyor.

    xvfb-run -a python scripts/dev/verify_password_dialog.py --output visual/pwd
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


_SANDBOX = tempfile.mkdtemp(prefix="archlence-pwd-verify-")
os.environ["ARCHLENCE_HOME"] = _SANDBOX
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "xdg-data")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "xdg-cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_SANDBOX, "xdg-state")
os.environ["ARCHLENCE_CONFIG_PATH"] = os.path.join(_SANDBOX, "config.json")

from kivy.clock import Clock                                    # noqa: E402
from kivymd.uix.textfield import MDTextField                    # noqa: E402

from main import ArchlenceApp                                   # noqa: E402
from security.security_service import (                         # noqa: E402
    PasswordPolicy,
    SecurityService,
)
from ui.i18n import tr                                          # noqa: E402

CURRENT_PASSWORD = "Mevcut-Parola-2026!"
NEW_PASSWORD = "Yeni-Guclu-Parola-2026!"
WRONG_PASSWORD = "Tamamen-Yanlis-2026!"


def _walk(widget):
    yield widget
    for child in widget.children:
        yield from _walk(child)


class PasswordDialogVerifier(ArchlenceApp):
    def __init__(self, output, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.findings = []
        self.observations = {}
        self.exit_code = 1

    def _fail(self, step, reason, **extra):
        self.findings.append(dict(step=step, reason=reason, **extra))

    def _setup_screen_limits(self):
        """`.kv`'den gelen üç parola alanının GERÇEK sınırını okur.

        Kaynak metni değil, çizilmiş widget'ı ölçüyor: KV'deki sayı ile ekrana
        gelen değer arasında bir fark kalırsa burada görünür.
        """
        return [
            self.root.ids[name].max_text_length
            for name in ("pin_setup_input", "pin_confirm_input",
                         "password_input")
        ]

    def on_start(self):
        super().on_start()
        Clock.schedule_once(self._install_credential, 1.5)

    def _install_credential(self, _dt):
        salt = SecurityService.generate_salt()
        self.config_store.put(
            "security",
            pin_hash=SecurityService.hash_password(CURRENT_PASSWORD, salt),
            salt=salt,
            is_set=True,
        )
        self._stored_before = self.config_store.get("security")["pin_hash"]
        self.open_change_pin_dialog()
        Clock.schedule_once(self._check_surface, 1.0)


    def _check_surface(self, _dt):
        dialog = getattr(self, "_change_pin_dialog", None)
        if dialog is None:
            self._fail("diyalog", "diyalog hiç açılmadı")
            self._finish()
            return

        fields = [
            widget for widget in _walk(dialog.content_cls)
            if isinstance(widget, MDTextField)
        ]
        hints = [field.hint_text for field in fields]
        self.observations["field_hints_tr"] = hints
        self.observations["field_count"] = len(fields)

        if len(fields) != 3:
            self._fail("alanlar", f"üç parola alanı beklendi, {len(fields)} çizildi",
                       shown=hints)

        for expected in ("Mevcut Şifre", "Yeni Şifre", "Yeni Şifre Tekrar"):
            if expected not in hints:
                self._fail("alanlar", f"'{expected}' alanı ekranda yok", shown=hints)

        for field in fields:
            if not field.password:
                self._fail("maskeleme", "parola alanı düz metin gösteriyor",
                           shown=field.hint_text)


        limits = [field.max_text_length for field in fields]
        self.observations["dialog_max_lengths"] = limits
        for limit in limits:
            if limit != PasswordPolicy.MAX_LENGTH:
                self._fail("uzunluk-siniri",
                           "diyalog alanı politika sınırını taşımıyor",
                           shown=limit, expected=PasswordPolicy.MAX_LENGTH)

        setup_limits = self._setup_screen_limits()
        self.observations["setup_max_lengths"] = setup_limits
        for limit in setup_limits:
            if limit != PasswordPolicy.MAX_LENGTH:
                self._fail("uzunluk-siniri",
                           "kurulum/giriş alanı politika sınırını taşımıyor",
                           shown=limit, expected=PasswordPolicy.MAX_LENGTH)

        helper = [f.helper_text for f in fields if f.helper_text]
        self.observations["helper_text"] = helper
        if PasswordPolicy.REQUIREMENTS not in helper:
            self._fail("yardim-metni",
                       "yardım metni politika kaynağıyla aynı değil",
                       shown=helper, expected=PasswordPolicy.REQUIREMENTS)


        english = {source: tr(source, "en") for source in (
            "Mevcut Şifre", "Yeni Şifre", "Yeni Şifre Tekrar",
            "Şifre Değiştir", PasswordPolicy.REQUIREMENTS,
            "Yeni şifre mevcut şifreyle aynı olamaz.",
            "Şifreniz güncel güvenlik politikasını karşılamıyor. "
            "Devam etmek için yeni bir şifre belirleyin.",
        )}
        english.update({m: tr(m, "en") for m in PasswordPolicy.MESSAGES})
        self.observations["english"] = english
        for source, translated in english.items():
            if translated == source:
                self._fail("ceviri", "İngilizce karşılığı yok", shown=source)

        Clock.schedule_once(self._check_wrong_current, 0.5)


    def _check_wrong_current(self, _dt):
        self._current_pin_input.text = WRONG_PASSWORD
        self._new_pin_input.text = NEW_PASSWORD
        self._new_pin_confirm.text = NEW_PASSWORD
        self._apply_new_pin(None)

        after = self.config_store.get("security")["pin_hash"]
        self.observations["hash_unchanged_after_wrong_current"] = (
            after == self._stored_before
        )
        if after != self._stored_before:
            self._fail("yanlis-mevcut",
                       "yanlış mevcut parolayla hash DEĞİŞTİ")
        if getattr(self, "_change_pin_dialog", None) is None:
            self._fail("yanlis-mevcut",
                       "başarısız denemede diyalog kapandı")
            self._finish()
            return


        from security.security_service import LoginThrottle
        self.config_store.put(
            "security_throttle", **LoginThrottle.record_success()
        )
        Clock.schedule_once(self._check_correct_change, 0.5)


    def _check_correct_change(self, _dt):
        self._current_pin_input.text = CURRENT_PASSWORD
        self._new_pin_input.text = NEW_PASSWORD
        self._new_pin_confirm.text = NEW_PASSWORD
        self._apply_new_pin(None)

        security = self.config_store.get("security")
        changed = SecurityService.verify_password(
            NEW_PASSWORD, security["salt"], security["pin_hash"]
        )
        self.observations["password_changed"] = changed
        if not changed:
            self._fail("dogru-degisiklik",
                       "doğru mevcut parolayla değişiklik tamamlanmadı")
        if SecurityService.verify_password(
            CURRENT_PASSWORD, security["salt"], security["pin_hash"]
        ):
            self._fail("dogru-degisiklik", "eski parola hâlâ geçerli")

        leftovers = {
            name: getattr(self, name, "yok")
            for name in ("_current_pin_input", "_new_pin_input",
                         "_new_pin_confirm", "_change_pin_dialog")
        }
        self.observations["references_cleared"] = {
            name: value is None for name, value in leftovers.items()
        }
        for name, value in leftovers.items():
            if value is not None:
                self._fail("temizlik",
                           f"{name} diyalog kapandıktan sonra hâlâ tutuluyor")

        screen = self.root.ids.screen_manager.current
        self.observations["screen_after_change"] = screen
        if screen != "login":
            self._fail("yeniden-giris",
                       "parola değiştikten sonra yeniden giriş istenmedi",
                       shown=screen)
        self._finish()

    def _finish(self):
        report = {"observations": self.observations, "findings": self.findings}
        (self.output / "password-dialog.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Alan ipuçları: {self.observations.get('field_hints_tr')}", flush=True)
        if self.findings:
            for item in self.findings:
                print(f"[BULGU] {item['step']}: {item['reason']}", flush=True)
            print(f"::error::{len(self.findings)} parola diyaloğu bulgusu", flush=True)
            self.exit_code = 1
        else:
            print("Diyalog üç maskeli alanla çiziliyor; mevcut parola "
                  "doğrulanmadan hiçbir şey değişmiyor.", flush=True)
            self.exit_code = 0
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from database.init_db import initialize_database

    initialize_database()
    app = PasswordDialogVerifier(args.output)
    app.run()
    raise SystemExit(app.exit_code)
