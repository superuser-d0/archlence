"""Birikim hedefleri (savings goals) mixin'i.

Hedef ekleme/hesaplama diyalogları, hedef kartlarının dashboard'da çizimi,
renk döngüsü ve hedefe para ekleme akışı.

TEK DOĞRULUK KAYNAĞI SQL'dir (sözleşme: docs/ARCHITECTURE.md).
`self.savings_goals` artık kalıcı bir depo DEĞİL, `SavingsService.get_goals()`
sonucunun ekrana uygun bir GÖRÜNÜMÜ; her başarılı servis çağrısından sonra
SQL'den yeniden okunur. `savings_goals.json`'a yazan kod yolu kalmadı.

Eskiden görüntü JSON'dan, para SQL'den geliyordu ve ikisi ayrışabiliyordu:
JSON hedefi yalnız SAYISAL id ile işaretliyordu, restore `sqlite_sequence`i
geri sarıyordu ve bayat bir kart başka bir hedefi fonluyordu
(tests/test_savings_identity_reuse_regression.py). Bu yüzden her kart işlemi
artık `goal_uid` ile doğrulanıyor.
"""
import datetime
import math

from kivy.metrics import dp
from kivy.clock import Clock
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from ui.i18n import tr as _t, trf as _tf
from utils.formatters import attach_amount_mask, read_amount
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu

from typing import Any
import ui.theme as ftheme
from services.account_service import AccountService, CHECKING
from services.savings_service import SavingsService


GOAL_IDENTITY_MISSING_MESSAGE = (
    "Bu hedef kartı güncel değil; işlem güvenlik için durduruldu ve "
    "hiçbir para hareket etmedi. Lütfen ekranı yenileyip tekrar deneyin."
)


class SavingsMixin:
    savings_goals: list[dict[str, Any]]


    GOAL_IDENTITY_MISSING_MESSAGE = GOAL_IDENTITY_MISSING_MESSAGE

    @staticmethod
    def _goal_view(row):
        """Servis sözlüğünü kartların beklediği görünüme çevirir.

        Kimlik alanları (`id`, `goal_uid`) BİLEREK taşınıyor: kart üzerinden
        yapılan her işlem bunlarla doğrulanıyor.
        """
        return {
            "id": row["id"],
            "goal_uid": row["goal_uid"],
            "name": row["goal_name"],
            "target": float(row["target_amount"] or 0.0),
            "current": float(row["current_amount"] or 0.0),
            "color": row["color"] or "green",
            "auto_deposit": bool(row["auto_deposit"]),
            "created_at": row["created_at"],
            "status": row["status"],
            "target_date": row["target_date"],
        }

    def load_savings_goals(self):
        """Hedefleri TEK KAYNAKTAN (SQL) okuyup belleği tazeler.

        Her başarılı servis çağrısından ve restore'dan sonra çağrılır: arayüz
        kendi bellek durumunu güncellemek yerine SQL'in söylediğini gösterir.
        """
        from utils.errors import KeyUnavailableError

        try:
            rows = SavingsService.get_goals()
        except KeyUnavailableError:


            from utils.logging_config import get_logger
            get_logger().exception("Birikim hedefleri okunamadı: anahtar yok")
            self._savings_unavailable = True
            self.savings_goals = []
            return self.savings_goals

        self._savings_unavailable = False
        self.savings_goals = [self._goal_view(row) for row in rows]
        return self.savings_goals

    def deposit_into_goal(self, goal, amount, account_id):
        """Bir hedef KARTINDAN yatırma — tek servis/transaction sınırı.

        Kimlik doğrulanamıyorsa servise hiç gidilmez; servis de kendi
        tarafında `goal_uid`i yeniden doğrular (fail-closed, iki katman).
        Başarıdan sonra bellek SQL'den tazelenir; çağıran kendi sözlüğünü
        elle güncellemez.
        """
        goal_uid = (goal or {}).get("goal_uid")
        goal_id = (goal or {}).get("id")
        if not goal_uid or goal_id is None:
            from utils.logging_config import get_logger
            get_logger().warning(
                "[KİMLİK] kalıcı kimliği olmayan hedef kartından yatırma "
                "denendi; işlem reddedildi")
            raise ValueError(GOAL_IDENTITY_MISSING_MESSAGE)
        updated = SavingsService.deposit_to_goal(
            int(goal_id), amount, account_id, goal_uid=goal_uid
        )
        self.load_savings_goals()
        return updated

    def delete_goal_record(self, goal, account_id=None, refund=False):
        """Bir hedef KARTINDAN silme — `deposit_into_goal` ile aynı sözleşme."""
        goal_uid = (goal or {}).get("goal_uid")
        goal_id = (goal or {}).get("id")
        if not goal_uid or goal_id is None:
            from utils.logging_config import get_logger
            get_logger().warning(
                "[KİMLİK] kalıcı kimliği olmayan hedef kartı silinmeye "
                "çalışıldı; işlem reddedildi")
            raise ValueError(GOAL_IDENTITY_MISSING_MESSAGE)
        deleted = SavingsService.delete_goal(
            int(goal_id), account_id, refund=refund, goal_uid=goal_uid
        )
        self.load_savings_goals()
        return deleted

    def calculate_savings_goal(self, *args):
        """Birikim hedefi için girilen verilere göre hedefe ulaşma süresini hesaplar
        ve sonucu dialog üzerinde gösterir."""
        try:
            target = float(self.sg_target_input.text)
            deposit = float(self.sg_deposit_input.text)
            name = self.sg_name_input.text if self.sg_name_input.text else _t("Hedef")

            if target <= 0 or deposit <= 0:
                toast(_t("Lütfen 0'dan büyük tutarlar girin!"))
                return

            periods = math.ceil(target / deposit)


            if self.sg_period == _t("Günlük"):
                months = periods // 30
                days = periods % 30
                time_str = (
                    _tf("{months} Ay, {days} Gün", months=months, days=days)
                    if months > 0 else _tf("{days} Gün", days=days)
                )
                self.sg_result_label.text = _tf(
                    "'{name}' için gereken süre:\n{periods} Gün\n(~{approx})",
                    name=name, periods=periods, approx=time_str,
                )
            else:
                years = periods // 12
                months = periods % 12
                time_str = (
                    _tf("{years} Yıl, {months} Ay", years=years, months=months)
                    if years > 0 else _tf("{months} Ay", months=months)
                )
                self.sg_result_label.text = _tf(
                    "'{name}' için gereken süre:\n{periods} Ay\n(~{approx})",
                    name=name, periods=periods, approx=time_str,
                )

            self.sg_result_label.theme_text_color = "Custom"
            self.sg_result_label.text_color = ftheme.accent(self.theme_cls, "blue")

        except ValueError:
            toast(_t("L\u00fctfen ge\u00e7erli say\u0131lar girin!"))

    def commit_savings_goal(self, *args):
        """Yeni birikim hedefini listeye (maksimum 3 adet) ekler ve ana ekranı (dashboard) günceller."""
        try:
            target = float(self.sg_target_input.text)
            name   = self.sg_name_input.text.strip() or "Birikim Hedefim"
            if target <= 0:
                toast(_t("Hedef tutar 0'dan b\u00fcy\u00fck olmal\u0131d\u0131r!"))
                return
            if len(self.savings_goals) >= 3:
                toast(_t("\u26a0\ufe0f En fazla 3 aktif hedef ekleyebilirsin!"))
                return


            SavingsService.create_goal(
                name, target,
                color="green",
                auto_deposit=bool(getattr(self, "sg_auto_deposit", False)),
                created_at=datetime.date.today().isoformat(),
            )
            self.load_savings_goals()
            toast(_tf("\u2714 '{name}' hedefi eklendi!", name=name))
            self.sg_dialog.dismiss()


            try:
                if self.root and 'goals_container' in self.root.ids:
                    self.render_savings_goals(0)  # balance=0 placeholder; real fetch below
            except (AttributeError, KeyError):
                from utils.logging_config import get_logger
                get_logger().exception("Hedef kartları çizilemedi")
            self.safe_refresh_charts()
        except ValueError:
            toast(_t("L\u00fctfen ge\u00e7erli bir hedef tutar girin!"))

    def _estimate_goal_eta(self, goal):
        """Mevcut birikim hızına göre kalan ay tahminini metin olarak döndürür.
        created_at eksikse (eski hedef) veya hız hesaplanamıyorsa 'yeterli veri
        yok' döner."""
        target = float(goal.get("target", 0))
        current = float(goal.get("current", 0.0))
        created_at = goal.get("created_at")

        if target > 0 and current >= target:
            return _t("Tebrikler, hedefe ulaştın! 🎉")
        if not created_at or current <= 0:
            return _t("Henüz tahmin için yeterli veri yok")

        try:
            created = datetime.date.fromisoformat(created_at)
        except ValueError:
            return _t("Henüz tahmin için yeterli veri yok")

        days_elapsed = max(1, (datetime.date.today() - created).days)
        months_elapsed = max(1.0, days_elapsed / 30.0)
        avg_monthly_pace = current / months_elapsed

        if avg_monthly_pace <= 0:
            return _t("Henüz tahmin için yeterli veri yok")

        remaining_months = math.ceil((target - current) / avg_monthly_pace)
        return _tf("Şu anki hızla ~{months} ay kaldı", months=remaining_months)


    def add_funds_to_goal(self, goal_idx, *args):
        """Belirtilen hedefe tek seferlik fon/para eklemek için bir diyalog penceresi açar.

        Kart üzerindeki tek 'Biriktir' butonundan `app.add_funds_to_goal(idx)`
        olarak çağrılır; ekleme sonrası tüm kartlar yeniden çizilir (bar/tutarlar
        kendiliğinden güncellenir), o yüzden ekstra widget referansı gerekmez.
        """
        if goal_idx >= len(self.savings_goals):
            return
        g = self.savings_goals[goal_idx]
        checking_accounts = [
            account for account in AccountService.get_accounts()
            if account["account_type"] == CHECKING
        ]
        if not checking_accounts:
            toast(_t("Para yatırabileceğiniz vadesiz/nakit hesabı bulunamadı."))
            return

        selected_account_id = checking_accounts[0]["id"]


        amount_field = attach_amount_mask(ftheme.make_text_field(
            _t("Yatırılacak Tutar (\u20ba)"), self.theme_cls
        ))
        account_btn = MDRaisedButton(
            size_hint_x=1,
            elevation=0 if self.theme_cls.theme_style == "Light" else 1,
            md_bg_color=ftheme.elevated_bg(self.theme_cls),
            theme_text_color="Custom",
            text_color=self.theme_cls.text_color,
        )


        desired_elevation = 0 if self.theme_cls.theme_style == "Light" else 1
        Clock.schedule_once(
            lambda dt: setattr(account_btn, "elevation", desired_elevation), 0
        )

        inner = MDBoxLayout(
            orientation="vertical", spacing=dp(14),
            size_hint_y=None, height=dp(140),
        )
        inner.add_widget(amount_field)
        inner.add_widget(account_btn)

        def _account_text(account):
            return (
                f"{account['name']} "
                f"(Bakiye: {account['balance']:,.2f} \u20ba)"
            )

        def _select_account(account):
            nonlocal selected_account_id
            selected_account_id = account["id"]
            account_btn.text = _account_text(account)
            self.savings_account_menu.dismiss()

        def _fresh_accounts():
            """Her çağrıda DB'den güncel bakiye ve hesap listesini döndürür."""
            return [
                account for account in AccountService.get_accounts()
                if account["account_type"] == CHECKING
            ]

        def _sync_account_button(accounts):
            nonlocal selected_account_id
            selected = next(
                (a for a in accounts if a["id"] == selected_account_id),
                accounts[0] if accounts else None,
            )
            if selected is None:
                account_btn.text = _t("Kullanılabilir hesap yok")
                account_btn.disabled = True
                return
            selected_account_id = selected["id"]
            account_btn.disabled = False
            account_btn.text = _account_text(selected)

        def _open_account_menu(*args):


            accounts_now = _fresh_accounts()
            _sync_account_button(accounts_now)
            self.savings_account_menu.items = [
                {
                    "text": _account_text(account),
                    "viewclass": "OneLineListItem",
                    "on_release": lambda account=account: _select_account(account),
                }
                for account in accounts_now
            ]
            if accounts_now:
                self.savings_account_menu.open()

        self.savings_account_menu = MDDropdownMenu(
            caller=account_btn,
            width_mult=4,
        )
        self.savings_account_button = account_btn
        account_btn.on_release = _open_account_menu
        _sync_account_button(checking_accounts)

        def _do_add(instance):


            try:
                amount = read_amount(amount_field)
            except ValueError:
                toast(_t("Geçerli bir sayı girin!"))
                return
            if amount <= 0:
                toast(_t("0'dan büyük bir tutar girin!"))
                return

            target = float(g.get("target", 1)) or 1.0
            old_pct = max(0.0, min(100.0, (g.get("current", 0.0) / target) * 100))
            try:
                updated = self.deposit_into_goal(g, amount, selected_account_id)
            except ValueError as exc:

                from utils.logging_config import get_logger
                get_logger().warning("Hedefe yatırma reddedildi", exc_info=True)


                toast(_t(str(exc)))
                return


            current = float((updated or {}).get("current_amount", 0.0))
            new_pct = max(0.0, min(100.0, (current / target) * 100))
            toast(_tf("₺{amount} eklendi!", amount=f"{amount:,.2f}"))
            fund_dlg.dismiss()
            self.render_savings_goals(0)
            self.safe_refresh_charts()

            crossed = [m for m in (25, 50, 75, 100) if old_pct < m <= new_pct]
            if crossed:
                top = max(crossed)
                try:
                    if self.root and 'confetti_overlay' in self.root.ids:
                        self.root.ids.confetti_overlay.burst()
                except Exception:
                    from utils.logging_config import get_logger
                    get_logger().exception("Hedef kutlama animasyonu oynatılamadı")
                msg = (_t("🎉🎉🎉 Hedefe ulaştın!") if top == 100
                       else _tf("🎉 %{percent} tamamlandı!", percent=top))
                toast(msg)

        fund_dlg = MDDialog(

            title=_tf("{name} — Para Yatır", name=g["name"]),
            type="custom",
            content_cls=inner,
            buttons=[
                ftheme.secondary_button(_t("İPTAL"), self.theme_cls, on_release=lambda x: fund_dlg.dismiss()),
                ftheme.primary_button(_t("YATIR"), self.theme_cls, on_release=_do_add),
            ]
        )
        fund_dlg.open()

    def open_delete_savings_goal_dialog(self, goal_idx, card=None, *args):
        """Hedef bakiyesini yok sayma veya hesaba iade etme kararını sorar."""
        if goal_idx < 0 or goal_idx >= len(self.savings_goals):
            return
        goal = self.savings_goals[goal_idx]
        name = str(goal.get("name", "Birikim Hedefim"))
        current = float(goal.get("current", 0) or 0)
        formatted = f"{current:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        message = (_tf("Bu hedef için şu ana kadar biriktirdiğiniz {amount} ₺ "
                       "ne yapılsın?", amount=formatted)
                   if current > 0 else
                   _t("Bu hedefte birikmiş bakiye yok. Hedef kalıcı olarak silinsin mi?"))
        content = MDLabel(text=message, theme_text_color="Secondary",
                          size_hint_y=None, height=dp(64), valign="middle")
        content.bind(size=content.setter("text_size"))

        def _finish(refund=False, account_id=None):
            try:


                if not self.delete_goal_record(goal, account_id, refund=refund):
                    raise ValueError(
                        "Hedef bulunamadı; ekranı yenileyip tekrar deneyin."
                    )
            except (ValueError, TypeError) as exc:
                from utils.logging_config import get_logger
                get_logger().warning("Hedef silme reddedildi", exc_info=True)
                toast(_t(str(exc)))
                return False
            if card is not None and card.parent is not None:
                card.parent.remove_widget(card)
            Clock.schedule_once(lambda dt: self.render_savings_goals(0), 0)
            try:
                self.safe_refresh_charts()
                self.render_accounts()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Hedef silindikten sonra grafik/kartlar tazelenemedi")
            toast(_t("Bakiye hesaba aktarıldı ve hedef silindi.") if refund else _t("Hedef silindi."))
            return True

        def _discard(*_):
            if _finish():
                decision.dismiss()

        def _open_refund(*_):
            decision.dismiss()
            self._open_savings_refund_account_dialog(_finish)

        buttons = [
            ftheme.secondary_button(_t("İPTAL"), self.theme_cls, on_release=lambda x: decision.dismiss()),
            MDFlatButton(text=_t("SADECE SİL"), theme_text_color="Error", on_release=_discard),
        ]
        if current > 0:
            buttons.append(ftheme.primary_button(_t("HESABA AKTAR VE SİL"), self.theme_cls,
                                                  on_release=_open_refund))
        decision = MDDialog(title=_tf("Hedefi Sil: {name}", name=name),
                            type="custom",
                            content_cls=content, buttons=buttons)
        decision.open()

    def _open_savings_refund_account_dialog(self, on_confirm):
        accounts = [a for a in AccountService.get_accounts() if a["account_type"] == CHECKING]
        if not accounts:
            toast(_t("Bakiyenin aktarılabileceği vadesiz hesap bulunamadı."))
            return
        selected_id = accounts[0]["id"]
        account_btn = MDRaisedButton(size_hint_x=1, elevation=0,
                                     md_bg_color=ftheme.elevated_bg(self.theme_cls),
                                     theme_text_color="Custom", text_color=self.theme_cls.text_color)

        def _text(account):
            return f"{account['name']} (Bakiye: {account['balance']:,.2f} ₺)"

        def _select(account):
            nonlocal selected_id
            selected_id = account["id"]
            account_btn.text = _text(account)
            menu.dismiss()

        menu = MDDropdownMenu(caller=account_btn, width_mult=4, items=[{
            "text": _text(account), "viewclass": "OneLineListItem",
            "on_release": lambda account=account: _select(account),
        } for account in accounts])
        account_btn.text = _text(accounts[0])
        account_btn.on_release = lambda: menu.open()
        content = MDBoxLayout(size_hint_y=None, height=dp(56))
        content.add_widget(account_btn)

        def _confirm(*_):
            if on_confirm(True, selected_id):
                refund_dialog.dismiss()

        refund_dialog = MDDialog(
            title=_t("Bakiyenin Aktarılacağı Hesap"), type="custom", content_cls=content,
            buttons=[
                ftheme.secondary_button(_t("İPTAL"), self.theme_cls,
                                        on_release=lambda x: refund_dialog.dismiss()),
                ftheme.primary_button(_t("AKTAR VE SİL"), self.theme_cls, on_release=_confirm),
            ],
        )
        refund_dialog.open()


    ICON_BY_COLOR = {"green": "piggy-bank", "blue": "bullseye-arrow", "red": "flag-checkered"}

    # ─── Main goal card renderer ──────────────────────────────────────────
    def render_savings_goals(self, total_balance, *args):
        """Aktif birikim hedeflerini premium 'SavingsGoalCard' bileşenleriyle çizer.

        Her kart: sola yaslı keskin başlık + simge, hedef oranını gösteren
        MDProgressBar (value = biriken/hedef * 100), Toplanan/Hedef tutarları ve
        tek 'Biriktir' butonu. Yatay yamulma bileşendeki sabit
        size_hint/width/halign değerleriyle önlenir.
        """
        from ui.components import SavingsGoalCard
        if not (self.root and 'goals_container' in self.root.ids):
            return
        container = self.root.ids.goals_container
        container.clear_widgets()
        self._savings_render_generation = getattr(
            self, "_savings_render_generation", 0
        ) + 1
        generation = self._savings_render_generation

        if not self.savings_goals:


            empty_text = (
                _t("Birikim hedefleri şu anda açılamıyor — şifreleme "
                   "anahtarına ulaşılamadı. Verileriniz yerinde.")
                if getattr(self, "_savings_unavailable", False)
                else _t("Birikim hedefi belirlenmedi — Araçlar sekmesinden hedef ekleyebilirsin!")
            )
            lbl = MDLabel(
                text=empty_text,
                font_style="Caption",
                italic=True,
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(40),
                halign="center",
            )
            lbl.bind(size=lbl.setter('text_size'))
            container.add_widget(lbl)
            return

        def draw_goal(idx):
            if generation != self._savings_render_generation:
                return
            if idx >= len(self.savings_goals):
                return
            goal = self.savings_goals[idx]
            target    = float(goal.get("target", 1)) or 1.0
            current   = float(goal.get("current", 0.0))
            pct       = max(0.0, min(100.0, (current / target) * 100))
            color_key = goal.get("color", "green")

            formatted_target  = f"₺{target:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            formatted_current = f"₺{current:,.2f}".replace(",","X").replace(".",",").replace("X",".")

            card = SavingsGoalCard(
                goal_index=idx,
                goal_name=str(goal.get("name", "Birikim Hedefim")),
                goal_icon=self.ICON_BY_COLOR.get(color_key, "piggy-bank"),
                progress=pct,
                pct_text=f"%{pct:.0f}",
                status_text=self._estimate_goal_eta(goal),
                saved_text=formatted_current,
                target_text=formatted_target,
            )
            container.add_widget(card)
            Clock.schedule_once(lambda dt: draw_goal(idx + 1), 0)

        draw_goal(0)
