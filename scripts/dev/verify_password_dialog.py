"""Measure the password-change dialog in a real Kivy window.

This verifier uses the real ``ArchlenceApp``, KV tree, and a disposable local
profile. It confirms that:

  1. the dialog renders current, new, and confirmation password fields,
  2. every password field is masked,
  3. helper text comes from the password-policy source,
  4. the public labels are rendered in English,
  5. a wrong current password cannot change the stored hash,
  6. a valid change with the correct current password succeeds, and
  7. sensitive widget references are released when the dialog closes.

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

CURRENT_PASSWORD = "Current-Password-2026!"
NEW_PASSWORD = "New-Strong-Password-2026!"
WRONG_PASSWORD = "Completely-Wrong-2026!"


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
        """Read the effective limits of the three password fields from KV."""
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
            self._fail("dialog", "the dialog did not open")
            self._finish()
            return

        fields = [
            widget for widget in _walk(dialog.content_cls)
            if isinstance(widget, MDTextField)
        ]
        hints = [field.hint_text for field in fields]
        self.observations["field_hints_en"] = hints
        self.observations["field_count"] = len(fields)

        if len(fields) != 3:
            self._fail("fields", f"expected three password fields, rendered {len(fields)}",
                       shown=hints)

        for expected in ("Current Password", "New Password", "Confirm New Password"):
            if expected not in hints:
                self._fail("fields", f"'{expected}' is missing", shown=hints)

        for field in fields:
            if not field.password:
                self._fail("masking", "a password field renders plain text",
                           shown=field.hint_text)


        limits = [field.max_text_length for field in fields]
        self.observations["dialog_max_lengths"] = limits
        for limit in limits:
            if limit != PasswordPolicy.MAX_LENGTH:
                self._fail("length-limit",
                           "a dialog field does not use the policy limit",
                           shown=limit, expected=PasswordPolicy.MAX_LENGTH)

        setup_limits = self._setup_screen_limits()
        self.observations["setup_max_lengths"] = setup_limits
        for limit in setup_limits:
            if limit != PasswordPolicy.MAX_LENGTH:
                self._fail("length-limit",
                           "a setup/login field does not use the policy limit",
                           shown=limit, expected=PasswordPolicy.MAX_LENGTH)

        helper = [f.helper_text for f in fields if f.helper_text]
        self.observations["helper_text"] = helper
        expected_helper = tr(PasswordPolicy.REQUIREMENTS, "en")
        if expected_helper not in helper:
            self._fail("helper-text",
                       "helper text does not match the translated policy source",
                       shown=helper, expected=expected_helper)


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
                self._fail("translation", "the English mapping is missing", shown=source)

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
            self._fail("wrong-current",
                       "the hash changed after a wrong current password")
        if getattr(self, "_change_pin_dialog", None) is None:
            self._fail("wrong-current",
                       "the dialog closed after a failed attempt")
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
            self._fail("valid-change",
                       "the change failed with the correct current password")
        if SecurityService.verify_password(
            CURRENT_PASSWORD, security["salt"], security["pin_hash"]
        ):
            self._fail("valid-change", "the old password is still valid")

        missing = object()
        leftovers = {
            name: getattr(self, name, missing)
            for name in ("_current_pin_input", "_new_pin_input",
                         "_new_pin_confirm", "_change_pin_dialog")
        }
        self.observations["references_cleared"] = {
            name: value is None for name, value in leftovers.items()
        }
        for name, value in leftovers.items():
            if value is not None:
                self._fail("cleanup",
                           f"{name} is missing or retained after the dialog closed")

        screen = self.root.ids.screen_manager.current
        self.observations["screen_after_change"] = screen
        if screen != "login":
            self._fail("reauthentication",
                       "login was not required after the password change",
                       shown=screen)
        self._finish()

    def _finish(self):
        report = {"observations": self.observations, "findings": self.findings}
        (self.output / "password-dialog.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Field hints: {self.observations.get('field_hints_en')}", flush=True)
        if self.findings:
            for item in self.findings:
                print(f"[FINDING] {item['step']}: {item['reason']}", flush=True)
            print(f"::error::{len(self.findings)} password-dialog findings", flush=True)
            self.exit_code = 1
        else:
            print("The dialog renders three masked fields and changes nothing "
                  "until the current password is verified.", flush=True)
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
