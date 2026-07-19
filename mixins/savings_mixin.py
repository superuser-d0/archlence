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
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from ui.charts import LiquidWaveWidget


class SavingsMixin:
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

    # ─── Color cycling ────────────────────────────────────────────────────────
    COLOR_CYCLE = ["green", "blue", "red"]
    COLOR_MAP = {
        "green": (0.1,  0.8,  0.2,  0.85),
        "blue":  (0.1,  0.5,  0.95, 0.85),
        "red":   (0.9,  0.15, 0.15, 0.85),
    }

    def cycle_goal_color(self, goal_idx, wave_widget, *args):
        """Belirtilen hedefin tema rengini (yeşil, mavi, kırmızı) döngüsel olarak değiştirir
        ve dalga (wave) animasyon widget'ını canlı günceller."""
        if goal_idx >= len(self.savings_goals):
            return
        g = self.savings_goals[goal_idx]
        cur = g.get("color", "green")
        nxt = self.COLOR_CYCLE[(self.COLOR_CYCLE.index(cur) + 1) % len(self.COLOR_CYCLE)]
        g["color"] = nxt
        wave_widget.wave_color = self.COLOR_MAP[nxt]
        self.store.put('goals', data=self.savings_goals)
        color_names = {"green": "Yeşil", "blue": "Mavi", "red": "Kırmızı"}
        toast(f"Renk değiştirildi: {color_names[nxt]}")

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
    def add_funds_to_goal(self, goal_idx, wave_widget, pct_label, *args):
        """Belirtilen hedefe tek seferlik fon/para eklemek için bir diyalog penceresi açar."""
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
                MDRaisedButton(text="KAPAT", on_release=lambda x: fund_dlg.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                MDRaisedButton(text="EKLE",  on_release=_do_add, md_bg_color=(0.18, 0.8, 0.25, 1)),
            ]
        )
        fund_dlg.open()

    # ─── Main goal card renderer ──────────────────────────────────────────────
    def render_savings_goals(self, total_balance, *args):
        """Aktif birikim hedefleri için dashboard üzerinde her bir hedefe özel dinamik
        çerçeveli kartlar (MDCard) oluşturur ve çizer."""
        from kivymd.uix.card import MDCard as _MDCard
        if not (self.root and 'goals_container' in self.root.ids):
            return
        container = self.root.ids.goals_container
        container.clear_widgets()

        if not self.savings_goals:
            lbl = MDLabel(
                text="Birikim hedefi belirlenmedi \u2014 Ara\u00e7lar sekmesinden hedef ekleyebilirsin!",
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
            target    = float(goal.get("target", 1))
            current   = float(goal.get("current", 0.0))
            pct       = max(0.0, min(100.0, (current / target) * 100))
            color_key = goal.get("color", "green")
            wave_clr  = self.COLOR_MAP.get(color_key, self.COLOR_MAP["green"])

            if pct >= 100:
                quote = "Tebrikler! B\u00fct\u00e7e tamamland\u0131, hedeflenen donan\u0131mlar\u0131 almaya haz\u0131rs\u0131n!"
            elif current < 0:
                quote = "B\u00fct\u00e7en alarm veriyor \u2014 harcamalar\u0131n\u0131 optimize et!"
            elif pct < 25:
                quote = "Her b\u00fcy\u00fck ba\u015far\u0131 k\u00fc\u00e7\u00fck bir ad\u0131mla ba\u015flar. Devam!"
            elif pct < 75:
                quote = "Harika! Yar\u0131 yola geldin. Sab\u0131r en b\u00fcy\u00fck sermaye!"
            else:
                quote = "Hedefe ramak kald\u0131! Son hamleyi yap!"

            formatted_target  = f"\u20ba{target:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            formatted_current = f"\u20ba{current:,.2f}".replace(",","X").replace(".",",").replace("X",".")

            card = _MDCard(
                orientation="vertical",
                size_hint_y=None,
                height=dp(198),
                padding=dp(16),
                spacing=dp(12),
                style="outlined",
                md_bg_color=getattr(self.theme_cls, 'bg_darkest', getattr(self.theme_cls, 'bg_normal', (1, 1, 1, 1))),
                line_color=(0.5, 0.5, 0.5, 0.35),
                radius=[dp(14), dp(14), dp(14), dp(14)],
            )

            # Header row: trophy icon + goal name
            hdr = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
            ico = MDIconButton(
                icon="trophy",
                theme_text_color="Custom",
                icon_color=(0.95, 0.75, 0.1, 1),
                size_hint_x=None,
                width=dp(36),
                pos_hint={"center_y": .5}
            )
            name_lbl = MDLabel(
                text=f"{goal['name']}  \u2014  Hedef: {formatted_target}  |  Biriken: {formatted_current}",
                bold=True,
                theme_text_color="Primary",
                font_style="Subtitle2",
                pos_hint={"center_y": .5}
            )
            hdr.add_widget(ico)
            hdr.add_widget(name_lbl)
            card.add_widget(hdr)

            # Daha kibar ve ince dalga barı (Height dp(20))
            wave = LiquidWaveWidget(
                size_hint_x=1,
                size_hint_y=None,
                height=dp(20),
                progress=pct,
                wave_color=wave_clr,
            )
            card.add_widget(wave)

            # Motivation Label: theme_text_color="Secondary", italicized.
            pct_lbl = MDLabel(
                text=f"%{pct:.1f} Tamamland\u0131 \u2014 {quote}".replace(".", ","),
                bold=False,
                font_size=dp(13),
                italic=True,
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(20),
            )
            pct_lbl.bind(size=pct_lbl.setter('text_size'))
            card.add_widget(pct_lbl)

            # Tahmini süre: mevcut birikim hızına göre "~N ay kaldı"
            eta_lbl = MDLabel(
                text=self._estimate_goal_eta(goal),
                font_style="Caption",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(18),
            )
            card.add_widget(eta_lbl)

            # Footer: MDBoxLayout with icon_size="28sp" buttons (Palette, Plus).
            act_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(40),
                spacing=dp(16),
            )
            btn_color = MDIconButton(
                icon="palette",
                theme_text_color="Custom",
                icon_color=wave_clr[:3] + (1,),
                icon_size="28sp",
                pos_hint={"center_y": .5}
            )
            btn_color.bind(on_release=lambda inst, i=idx, w=wave: self.cycle_goal_color(i, w))

            btn_funds = MDIconButton(
                icon="cash-plus",
                theme_text_color="Custom",
                icon_color=(0.1, 0.8, 0.2, 1),
                icon_size="28sp",
                pos_hint={"center_y": .5}
            )
            btn_funds.bind(on_release=lambda inst, i=idx, w=wave, p=pct_lbl: self.add_funds_to_goal(i, w, p))

            act_row.add_widget(btn_color)
            act_row.add_widget(btn_funds)
            card.add_widget(act_row)

            container.add_widget(card)
