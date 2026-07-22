"""Birikim hedefleri (savings goals) mixin'i.

Hedef ekleme/hesaplama diyalogları, hedef kartlarının dashboard'da çizimi,
renk döngüsü ve hedefe para ekleme akışı. main.py'deki FinoraApp gövdesinden
taşındı; hedef verisi self.savings_goals listesinde tutulur ve self.store
(JsonStore) üzerinden savings_goals.json'a kalıcılaştırılır.
"""
import datetime
import math

from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from typing import Any


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
            self.sg_result_label.text_color = (0.13, 0.59, 0.95, 1)

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
    def add_funds_to_goal(self, goal_idx, *args):
        """Belirtilen hedefe tek seferlik fon/para eklemek için bir diyalog penceresi açar.

        Kart üzerindeki tek 'Biriktir' butonundan `app.add_funds_to_goal(idx)`
        olarak çağrılır; ekleme sonrası tüm kartlar yeniden çizilir (bar/tutarlar
        kendiliğinden güncellenir), o yüzden ekstra widget referansı gerekmez.
        """
        if goal_idx >= len(self.savings_goals):
            return
        g = self.savings_goals[goal_idx]
        amount_field = MDTextField(hint_text="Eklenecek Tutar (\u20ba)", input_filter="float")
        inner = MDBoxLayout(orientation="vertical", size_hint_y=None, height="80dp")
        inner.add_widget(amount_field)

        def _do_add(instance):
            try:
                amount = float(amount_field.text)
                if amount <= 0:
                    toast("0'dan b\u00fcy\u00fck bir tutar girin!")
                    return
                target = float(g.get("target", 1)) or 1.0
                old_pct = max(0.0, min(100.0, (g.get("current", 0.0) / target) * 100))
                g["current"] = g.get("current", 0.0) + amount
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
            title=f"{g['name']} \u2014 Miktar Ekle",
            type="custom",
            content_cls=inner,
            buttons=[
                MDFlatButton(text="KAPAT", on_release=lambda x: fund_dlg.dismiss()),
                MDRaisedButton(text="EKLE",  on_release=_do_add, md_bg_color=self.theme_cls.primary_color, elevation=0),
            ]
        )
        fund_dlg.open()

    # ─── Renk → hedef simgesi eşlemesi ─────────────────────────────
    # Kart artık tek, sabit teal vurgu kullanıyor; hedefin depolanmış rengi
    # (yeşil/mavi/kırmızı) keskin bir Kivy ikonuna dönüşür.
    ICON_BY_COLOR = {"green": "piggy-bank", "blue": "bullseye-arrow", "red": "flag-checkered"}
    ACCENT_TEAL = (0.10, 0.80, 0.72, 1)

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
                accent_color=self.ACCENT_TEAL,
            )
            container.add_widget(card)
