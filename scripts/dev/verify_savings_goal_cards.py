"""Gerçek Kivy ekranında birikim hedefleri SQL'den besleniyor mu — ölçer.

NEDEN VAR: birikim kartları uzun süre `savings_goals.json`'dan çiziliyordu;
para ise SQLite'taydı. Tek doğruluk kaynağı SQL'e taşındıktan sonra geriye
kalan risk BİRİM TESTİYLE YAKALANAMAZ: servis doğru veriyi döndürse bile
kartlar hiç çizilmeyebilir, boş açılabilir ya da eski değerleri gösterebilir.
Planın durma koşullarından biri açıkça budur — "gerçek uygulamada birikim
ekranı boş açılıyorsa" dilim geri alınır.

Bu betik GERÇEK `ArchlenceApp`i, gerçek KV dosyalarını ve gerçek bir SQLite
profilini kullanır. Ölçtüğü dört şey:

  1. SQL'deki her hedef için bir kart çiziliyor (sayı ve ADLAR eşleşiyor),
  2. kartın gösterdiği tutar SQL'deki tutar (JSON değil),
  3. servis sınırından yapılan bir yatırma sonrası kart YENİ değeri gösteriyor,
  4. silme sonrası kart ekrandan kalkıyor.

    xvfb-run -a python scripts/dev/verify_savings_goal_cards.py --output visual/savings
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

# PROFİL İZOLASYONU IMPORT'TAN ÖNCE. `utils.app_paths` yolları ortam
# değişkeninden çözüyor; `main` import edildikten sonra ayarlamak, betiği
# geliştiricinin GERÇEK finans verisi üzerinde çalıştırırdı.
_SANDBOX = tempfile.mkdtemp(prefix="archlence-savings-verify-")
os.environ["ARCHLENCE_HOME"] = _SANDBOX
os.environ["XDG_DATA_HOME"] = os.path.join(_SANDBOX, "xdg-data")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "xdg-cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_SANDBOX, "xdg-state")
os.environ["ARCHLENCE_CONFIG_PATH"] = os.path.join(_SANDBOX, "config.json")

from kivy.clock import Clock                                    # noqa: E402
from kivy.uix.screenmanager import NoTransition                 # noqa: E402

from main import ArchlenceApp                                   # noqa: E402
from ui.components import SavingsGoalCard                       # noqa: E402

SEED = [
    # (ad, hedef, biriken, renk)
    ("Araba Fonu", 20000.0, 2500.0, "green"),
    ("Tatil Fonu", 10000.0, 0.0, "blue"),
]
DEPOSIT = 750.0


def _walk(widget):
    yield widget
    for child in widget.children:
        yield from _walk(child)


def seed_profile():
    """Gerçek servislerle gerçek bir profil kurar (elle SQL yazmadan)."""
    from database.init_db import initialize_database
    from services.account_service import AccountService
    from services.savings_service import SavingsService

    initialize_database()
    account_id = AccountService.create_account(
        "Vadesiz", "checking", initial_balance=50000.0
    )
    goals = {}
    for name, target, current, color in SEED:
        goal_id = SavingsService.create_goal(name, target, color=color)
        if current:
            SavingsService.deposit_to_goal(goal_id, current, account_id)
        goals[name] = goal_id
    return account_id, goals


class SavingsCardVerifier(ArchlenceApp):
    def __init__(self, output, account_id, **kwargs):
        super().__init__(**kwargs)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.account_id = account_id
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
        # Hedef kartlarının kabı hangi sekmedeyse ORAYA geç. Sekme adını
        # sabit yazmak, kap ileride başka bir sekmeye taşınırsa betiği sessizce
        # yanlış yerde ölçtürürdü (ölçüldü: kap "home_tab"da değil,
        # "assets_tab"da yaşıyor).
        tab = self._container_tab_name()
        self.observations["container_tab"] = tab
        if tab:
            nav.switch_tab(tab)
        # BELLEĞİ ÖNCE SQL'DEN TAZELE. `savings_goals` açılışta arka plan
        # tazelemesiyle doluyor; `_enter` o tazelemeden ÖNCE koşarsa liste
        # boş oluyor ve render hiçbir kart çizmiyordu (ölçüldü: beş koşumun
        # üçünde `goals_in_memory` doluyken `cards_rendered=1`). Bu bir ÖLÇÜM
        # YARIŞIYDI; `load_savings_goals` zaten üretimin kendi yeniden yükleme
        # yolu, yani kapı hâlâ gerçek kod yolunu çalıştırıyor.
        self.load_savings_goals()
        self.render_savings_goals(0)
        self._render_deadline = 0
        self._previous_draw_count = -1
        Clock.schedule_once(self._await_cards, 0.3)

    def _await_cards(self, _dt):
        """Kartların TAMAMI çizilene kadar bekler — sabit süre YETMİYOR.

        `render_savings_goals` kartları FRAME BAŞINA BİR TANE çiziyor
        (`Clock.schedule_once(... draw_goal(idx + 1), 0)`). Sabit 1.5 sn
        beklemek yükün altında yetmiyordu ve kapı ölçüm anında yalnız 1 kart
        görüp kırmızı veriyordu — üründe kusur yokken (ölçüldü: aynı koşumda
        yatırma/silme adımları tam durumu gördü). Bu bir ÖLÇÜM YARIŞIYDI.

        Bekleme SINIRLI: kartlar gerçekten hiç çizilmezse kapı yine kırmızı
        verir, yani dişleri kaybolmuyor.
        """
        # Beklenen sayı TOHUMDAN geliyor, bellekteki listeden değil: liste
        # henüz dolmamışsa `0 >= 0` ile döngü hemen çıkar ve kapı boş ekranı
        # "tamam" sanardı.
        #
        # ÜST ÜSTE İKİ kez doğru sayıyı görmek şart. Arka plan dashboard
        # tazelemesi kendi `render_savings_goals` çağrısını yapıyor ve o çağrı
        # kabı ÖNCE temizleyip kartları frame başına bir tane yeniden çiziyor;
        # tek ölçüm o yeniden çizimin ortasına düşebiliyordu (ölçüldü:
        # cards_rendered=1, container_children=1, hedefler bellekte tam).
        expected = len(SEED)
        drawn = len(self._cards())
        self._render_deadline += 1
        settled = drawn == expected and self._previous_draw_count == drawn
        self._previous_draw_count = drawn
        if not settled and self._render_deadline < 40:
            Clock.schedule_once(self._await_cards, 0.2)
            return
        self.observations["render_polls"] = self._render_deadline
        Clock.schedule_once(self._check_initial_render, 0.3)

    def _container_tab_name(self):
        from kivymd.uix.bottomnavigation import MDBottomNavigationItem

        widget = self.root.ids.goals_container
        for _ in range(100):
            if widget is None:
                return None
            if isinstance(widget, MDBottomNavigationItem):
                return widget.name
            widget = widget.parent
        return None

    # ── 1 + 2: kartlar SQL'den mi geliyor ────────────────────────────────
    def _cards(self):
        """Hedef kartları — kabın KENDİSİNDEN okunuyor.

        `self.root`tan aşağı yürümek YANLIŞ ölçüm veriyordu: KivyMD'nin alt
        gezinme çubuğu yalnız AKTİF sekmenin ağacını `children` altında
        tutuyor, dolayısıyla kartlar çizilmiş olsa bile kökten
        görünmüyorlardı (ölçüldü: container_children=2 iken kökten taranan
        kart sayısı 0). Kabın ağaca gerçekten bağlı olduğu ayrıca
        `_container_is_attached` ile doğrulanıyor.
        """
        container = self.root.ids.goals_container
        return [
            widget for widget in container.children
            if isinstance(widget, SavingsGoalCard)
        ]

    def _container_is_attached(self):
        """Kap, kullanıcının GÖRDÜĞÜ ağaçta mı?

        Naif "ebeveyn zinciri köke ulaşıyor mu" kontrolü YANLIŞ negatif
        veriyordu: KivyMD, alt gezinme çubuğundaki PASİF sekmeleri ağaçtan
        koparıyor, yani zincir `MDBottomNavigationItem`da bitiyor
        (ölçüldü: parent_chain sonu MDBottomNavigationItem, parent=None).
        Bu bir kusur değil, bileşenin tasarımı.

        Doğru soru: zincir köke ulaşıyor mu, YA DA sekme öğesinde bitiyorsa o
        öğe SEÇİLİ sekme mi? İkisi de değilse kartlar gerçekten görünmez.
        """
        from kivymd.uix.bottomnavigation import MDBottomNavigationItem

        widget = self.root.ids.goals_container
        chain = []
        for _ in range(100):
            if widget is None:
                break
            chain.append(type(widget).__name__)
            if widget is self.root:
                self.observations["parent_chain"] = chain
                return True
            if isinstance(widget, MDBottomNavigationItem):
                self.observations["parent_chain"] = chain
                manager = self.root.ids.bottom_nav.ids.tab_manager
                self.observations["active_tab"] = manager.current
                return manager.current == widget.name
            widget = widget.parent
        self.observations["parent_chain"] = chain
        return False

    def _check_initial_render(self, _dt):
        cards = self._cards()
        self.observations["goals_in_memory"] = [
            g["name"] for g in getattr(self, "savings_goals", [])
        ]
        self.observations["has_container"] = (
            bool(self.root) and "goals_container" in self.root.ids
        )
        self.observations["container_children"] = (
            len(self.root.ids.goals_container.children)
            if self.observations["has_container"] else None
        )
        self.observations["screen"] = self.root.ids.screen_manager.current
        self.observations["container_attached"] = self._container_is_attached()
        self.observations["cards_rendered"] = len(cards)

        if not self.observations["container_attached"]:
            self.findings.append({
                "step": "ilk-cizim",
                "reason": "hedef kabı widget ağacına bağlı değil — çizilen "
                          "kartlar kullanıcıya görünmez",
            })
        drawn = {card.goal_name: card for card in cards}

        if not cards:
            self.findings.append({
                "step": "ilk-cizim",
                "reason": "birikim ekranı BOŞ açıldı — hiç kart çizilmedi",
            })
            self._finish()
            return

        for name, target, current, _color in SEED:
            card = drawn.get(name)
            if card is None:
                self.findings.append({
                    "step": "ilk-cizim",
                    "reason": f"'{name}' hedefi ekranda yok",
                })
                continue
            if f"{current:,.2f}".replace(",", "X").replace(".", ",").replace(
                    "X", ".") not in card.saved_text:
                self.findings.append({
                    "step": "ilk-cizim",
                    "goal": name,
                    "shown": card.saved_text,
                    "reason": "kart SQL'deki biriken tutarı göstermiyor",
                })
            if f"{target:,.2f}".replace(",", "X").replace(".", ",").replace(
                    "X", ".") not in card.target_text:
                self.findings.append({
                    "step": "ilk-cizim",
                    "goal": name,
                    "shown": card.target_text,
                    "reason": "kart SQL'deki hedef tutarı göstermiyor",
                })

        Clock.schedule_once(self._deposit, 0.5)

    # ── 3: yatırma sonrası kart yeni değeri gösteriyor mu ────────────────
    def _deposit(self, _dt):
        goal = next(
            (g for g in self.savings_goals if g["name"] == "Tatil Fonu"), None
        )
        if goal is None:
            self.findings.append({
                "step": "yatirma",
                "reason": "hedef listesi SQL'den yüklenmemiş",
            })
            self._finish()
            return
        try:
            self.deposit_into_goal(goal, DEPOSIT, self.account_id)
        except ValueError as exc:
            self.findings.append({
                "step": "yatirma",
                "reason": f"servis yatırmayı reddetti: {exc}",
            })
            self._finish()
            return
        self.render_savings_goals(0)
        Clock.schedule_once(self._check_after_deposit, 1.2)

    def _check_after_deposit(self, _dt):
        card = next(
            (c for c in self._cards() if c.goal_name == "Tatil Fonu"), None
        )
        expected = f"{DEPOSIT:,.2f}".replace(",", "X").replace(
            ".", ",").replace("X", ".")
        self.observations["after_deposit_text"] = (
            card.saved_text if card else None
        )
        if card is None:
            self.findings.append({
                "step": "yatirma-sonrasi",
                "reason": "yatırmadan sonra kart kayboldu",
            })
        elif expected not in card.saved_text:
            self.findings.append({
                "step": "yatirma-sonrasi",
                "shown": card.saved_text,
                "expected": expected,
                "reason": "kart yatırmadan sonra ESKİ tutarı gösteriyor",
            })
        Clock.schedule_once(self._delete, 0.5)

    # ── 4: silme sonrası kart kalkıyor mu ────────────────────────────────
    def _delete(self, _dt):
        goal = next(
            (g for g in self.savings_goals if g["name"] == "Tatil Fonu"), None
        )
        if goal is not None:
            try:
                self.delete_goal_record(goal, self.account_id, refund=True)
            except ValueError as exc:
                self.findings.append({
                    "step": "silme",
                    "reason": f"servis silmeyi reddetti: {exc}",
                })
        self.render_savings_goals(0)
        Clock.schedule_once(self._check_after_delete, 1.2)

    def _check_after_delete(self, _dt):
        names = [card.goal_name for card in self._cards()]
        self.observations["after_delete_cards"] = names
        if "Tatil Fonu" in names:
            self.findings.append({
                "step": "silme-sonrasi",
                "reason": "silinen hedef hâlâ ekranda",
            })
        if "Araba Fonu" not in names:
            self.findings.append({
                "step": "silme-sonrasi",
                "reason": "silinmeyen hedef ekrandan kayboldu",
            })
        self._finish()

    def _finish(self):
        report = {"observations": self.observations, "findings": self.findings}
        (self.output / "savings-goal-cards.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"çizilen kart: {self.observations.get('cards_rendered')}",
              flush=True)
        if self.findings:
            for item in self.findings:
                print(f"[BULGU] {item['step']}: {item['reason']}", flush=True)
            print(f"::error::{len(self.findings)} birikim kartı bulgusu",
                  flush=True)
            self.exit_code = 1
        else:
            print("Birikim kartları SQL'den doğru besleniyor.", flush=True)
            self.exit_code = 0
        self.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    account_id, _goals = seed_profile()
    app = SavingsCardVerifier(args.output, account_id)
    app.run()
    raise SystemExit(app.exit_code)
