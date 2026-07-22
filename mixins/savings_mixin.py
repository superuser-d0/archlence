"""Birikim hedefleri (savings goals) mixin'i.

Hedef ekleme/hesaplama diyalogları, hedef kartlarının dashboard'da çizimi,
renk döngüsü ve hedefe para ekleme akışı. main.py'deki FinoraApp gövdesinden
taşındı; hedef verisi self.savings_goals listesinde tutulur ve self.store
(JsonStore) üzerinden savings_goals.json'a kalıcılaştırılır.
"""
import datetime
import math

from kivy.metrics import dp
from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu

from typing import Any
import ui.theme as ftheme
from services.account_service import AccountService, CHECKING
from services.savings_service import SavingsService


class SavingsMixin:
    savings_goals: list[dict[str, Any]]
    
    def calculate_savings_goal(self, *args):
        """Birikim hedefi için girilen verilere göre hedefe ulaşma süresini hesaplar
        ve sonucu dialog üzerinde gösterir."""
        try:
            target = float(self.sg_target_input.text)
            deposit = float(self.sg_deposit_input.text)
            name = self.sg_name_input.text if self.sg_name_input.text else "Hedef"
            
            if target <= 0 or deposit <= 0:
                toast("Lütfen 0'dan büyük tutarlar girin!")
                return
                
            periods = math.ceil(target / deposit)
            
            if self.sg_period == "Günlük":
                months = periods // 30
                days = periods % 30
                time_str = f"{months} Ay, {days} Gün" if months > 0 else f"{days} Gün"
                self.sg_result_label.text = f"'{name}' için gereken süre:\n{periods} Gün\n(~{time_str})"
            else:
                years = periods // 12
                months = periods % 12
                time_str = f"{years} Yıl, {months} Ay" if years > 0 else f"{months} Ay"
                self.sg_result_label.text = f"'{name}' için gereken süre:\n{periods} Ay\n(~{time_str})"
                
            self.sg_result_label.theme_text_color = "Custom"
            self.sg_result_label.text_color = ftheme.accent(self.theme_cls, "blue")

        except ValueError:
            toast("L\u00fctfen ge\u00e7erli say\u0131lar girin!")

    def commit_savings_goal(self, *args):
        """Yeni birikim hedefini listeye (maksimum 3 adet) ekler ve ana ekranı (dashboard) günceller."""
        try:
            target = float(self.sg_target_input.text)
            name   = self.sg_name_input.text.strip() or "Birikim Hedefim"
            if target <= 0:
                toast("Hedef tutar 0'dan b\u00fcy\u00fck olmal\u0131d\u0131r!")
                return
            if len(self.savings_goals) >= 3:
                toast("\u26a0\ufe0f En fazla 3 aktif hedef ekleyebilirsin!")
                return
            goal = {
                "name":         name,
                "target":       target,
                "color":        "green",
                "current":      0.0,
                "auto_deposit": getattr(self, "sg_auto_deposit", False),
                "created_at":   datetime.date.today().isoformat(),
            }
            goal["id"] = SavingsService.create_goal(name, target)
            self.savings_goals.append(goal)
            self.store.put('goals', data=self.savings_goals)
            toast(f"\u2714 '{name}' hedefi eklendi!")
            self.sg_dialog.dismiss()
            # Refresh the dashboard cards
            try:
                if self.root and 'goals_container' in self.root.ids:
                    self.render_savings_goals(0)  # balance=0 placeholder; real fetch below
            except Exception:
                pass
                self.safe_refresh_charts()
        except ValueError:
            toast("L\u00fctfen ge\u00e7erli bir hedef tutar girin!")

    def _estimate_goal_eta(self, goal):
        """Mevcut birikim hızına göre kalan ay tahminini metin olarak döndürür.
        created_at eksikse (eski hedef) veya hız hesaplanamıyorsa 'yeterli veri
        yok' döner."""
        target = float(goal.get("target", 0))
        current = float(goal.get("current", 0.0))
        created_at = goal.get("created_at")

        if target > 0 and current >= target:
            return "Tebrikler, hedefe ulaştın! 🎉"
        if not created_at or current <= 0:
            return "Henüz tahmin için yeterli veri yok"

        try:
            created = datetime.date.fromisoformat(created_at)
        except ValueError:
            return "Henüz tahmin için yeterli veri yok"

        days_elapsed = max(1, (datetime.date.today() - created).days)
        months_elapsed = max(1.0, days_elapsed / 30.0)
        avg_monthly_pace = current / months_elapsed

        if avg_monthly_pace <= 0:
            return "Henüz tahmin için yeterli veri yok"

        remaining_months = math.ceil((target - current) / avg_monthly_pace)
        return f"Şu anki hızla ~{remaining_months} ay kaldı"

    # ─── One-time deposit into a goal ────────────────────────────────────────
    def _ensure_goal_db_id(self, goal):
        """Eski JsonStore hedefini bir kez SQL servisine taşır."""
        goal_id = goal.get("id")
        if goal_id is not None:
            return int(goal_id)
        goal["id"] = SavingsService.create_goal(
            goal.get("name", "Birikim Hedefim"),
            float(goal.get("target", 0)),
            current_amount=float(goal.get("current", 0)),
        )
        self.store.put("goals", data=self.savings_goals)
        return int(goal["id"])

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
            toast("Para yatırabileceğiniz vadesiz/nakit hesabı bulunamadı.")
            return

        selected_account_id = checking_accounts[0]["id"]
        amount_field = ftheme.make_text_field(
            "Yatırılacak Tutar (\u20ba)", self.theme_cls, filter="float"
        )
        account_btn = MDRaisedButton(
            size_hint_x=1,
            elevation=0 if self.theme_cls.theme_style == "Light" else 1,
            md_bg_color=ftheme.elevated_bg(self.theme_cls),
            theme_text_color="Custom",
            text_color=self.theme_cls.text_color,
        )
        # MDRaisedButton KivyMD KV kuralı constructor'daki elevation değerini
        # on_kv_post sırasında varsayılan 2 ile ezebiliyor. Layout kurulduktan
        # sonraki frame'de tema değerini kesin olarak uygula.
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
                account_btn.text = "Kullanılabilir hesap yok"
                account_btn.disabled = True
                return
            selected_account_id = selected["id"]
            account_btn.disabled = False
            account_btn.text = _account_text(selected)

        def _open_account_menu(*args):
            # Borç ödeme diyaloğundaki stale-state koruması: menü her açılışta
            # yeniden kurulur, ana buton da aynı güncel satırla eşitlenir.
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
                amount = float(amount_field.text)
                if amount <= 0:
                    toast("0'dan b\u00fcy\u00fck bir tutar girin!")
                    return
                target = float(g.get("target", 1)) or 1.0
                old_pct = max(0.0, min(100.0, (g.get("current", 0.0) / target) * 100))
                goal_id = self._ensure_goal_db_id(g)
                updated = SavingsService.deposit_to_goal(goal_id, amount, selected_account_id)
                if updated is not None:
                    g["current"] = float(updated["current_amount"])
                new_pct = max(0.0, min(100.0, (g["current"] / target) * 100))
                self.store.put('goals', data=self.savings_goals)
                toast(f"\u20ba{amount:,.2f} eklendi!")
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
                        pass
                    msg = "\U0001F389\U0001F389\U0001F389 Hedefe ula\u015ft\u0131n!" if top == 100 else f"\U0001F389 %{top} tamamland\u0131!"
                    toast(msg)
            except ValueError:
                toast("Ge\u00e7erli bir say\u0131 girin!")

        fund_dlg = MDDialog(
            title=f"{g['name']} \u2014 Para Yatır",
            type="custom",
            content_cls=inner,
            buttons=[
                ftheme.secondary_button("İPTAL", self.theme_cls, on_release=lambda x: fund_dlg.dismiss()),
                ftheme.primary_button("YATIR", self.theme_cls, on_release=_do_add),
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
        message = (f"Bu hedef için şu ana kadar biriktirdiğiniz {formatted} ₺ ne yapılsın?"
                   if current > 0 else
                   "Bu hedefte birikmiş bakiye yok. Hedef kalıcı olarak silinsin mi?")
        content = MDLabel(text=message, theme_text_color="Secondary",
                          size_hint_y=None, height=dp(64), valign="middle")
        content.bind(size=content.setter("text_size"))

        def _finish(refund=False, account_id=None):
            try:
                goal_id = self._ensure_goal_db_id(goal)
                if not SavingsService.delete_goal(goal_id, account_id, refund=refund):
                    raise ValueError("Hedef bulunamadı")
            except (ValueError, TypeError) as exc:
                toast(str(exc))
                return False
            self.savings_goals.pop(goal_idx)
            self.store.put("goals", data=self.savings_goals)
            if card is not None and card.parent is not None:
                card.parent.remove_widget(card)
            Clock.schedule_once(lambda dt: self.render_savings_goals(0), 0)
            try:
                self.safe_refresh_charts()
                self.render_accounts()
            except Exception:
                pass
            toast("Bakiye hesaba aktarıldı ve hedef silindi." if refund else "Hedef silindi.")
            return True

        def _discard(*_):
            if _finish():
                decision.dismiss()

        def _open_refund(*_):
            decision.dismiss()
            self._open_savings_refund_account_dialog(_finish)

        buttons = [
            ftheme.secondary_button("İPTAL", self.theme_cls, on_release=lambda x: decision.dismiss()),
            MDFlatButton(text="SADECE SİL", theme_text_color="Error", on_release=_discard),
        ]
        if current > 0:
            buttons.append(ftheme.primary_button("HESABA AKTAR VE SİL", self.theme_cls,
                                                  on_release=_open_refund))
        decision = MDDialog(title=f"Hedefi Sil: {name}", type="custom",
                            content_cls=content, buttons=buttons)
        decision.open()

    def _open_savings_refund_account_dialog(self, on_confirm):
        accounts = [a for a in AccountService.get_accounts() if a["account_type"] == CHECKING]
        if not accounts:
            toast("Bakiyenin aktarılabileceği vadesiz hesap bulunamadı.")
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
            title="Bakiyenin Aktarılacağı Hesap", type="custom", content_cls=content,
            buttons=[
                ftheme.secondary_button("İPTAL", self.theme_cls,
                                        on_release=lambda x: refund_dialog.dismiss()),
                ftheme.primary_button("AKTAR VE SİL", self.theme_cls, on_release=_confirm),
            ],
        )
        refund_dialog.open()

    # ─── Renk → hedef simgesi eşlemesi ─────────────────────────────
    # Hedefin depolanmış rengi simgeye dönüşür; gerçek vurgu tonu KV tarafında
    # aktif Light/Dark tema token'ından alınır.
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

        if not self.savings_goals:
            lbl = MDLabel(
                text="Birikim hedefi belirlenmedi — Araçlar sekmesinden hedef ekleyebilirsin!",
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

        for idx, goal in enumerate(self.savings_goals):
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
