import os
import math
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivy.uix.scrollview import ScrollView
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
from kivymd.uix.label import MDLabel


class CalculatorMixin:
    """Finansal hesaplayıcılar: basit hesap makinesi, bileşik faiz, kredi/taksit
    hesaplama, birikim hedefi ve ödeme planı tablosu + PDF dışa aktarma.

    open_calculator(calc_type) tek giriş noktasıdır; calc_type'a göre ("basic",
    "interest", "compound", "loan", "savings_goal") ilgili dialogu kurar. Hesap sonuçları
    self.last_calculated_loan gibi alanlarda tutulur ve DebtMixin bunları okur.
    """

    def open_calculator(self, calc_type):

        if calc_type == "basic":
            self.calc_layout = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="380dp")
            
            self.calc_input = MDTextField(
                text="",
                hint_text="0", 
                halign="right", 
                readonly=True, 
                font_size="28sp",
                size_hint_y=None,
                height="60dp"
            )
            self.calc_layout.add_widget(self.calc_input)
            
            self.calc_grid = MDGridLayout(cols=4, spacing="5dp", size_hint_y=1)
            
            buttons = [
                'C', '(', ')', '/',
                '7', '8', '9', '*',
                '4', '5', '6', '-',
                '1', '2', '3', '+',
                '.', '0', 'pi', 'e',
                'sin(', 'cos(', 'tan(', 'log(',
                'sqrt(', '**', '', '='
            ]
            
            def on_calc_button_press(instance):
                btn_text = instance.text
                current_text = self.calc_input.text
                
                if not btn_text:
                    return

                if current_text == "Hata":
                    current_text = ""
                
                if btn_text == 'C':
                    self.calc_input.text = ""
                elif btn_text == '=':
                    try:
                        safe_dict = {
                            "sin": math.sin, "cos": math.cos, "tan": math.tan,
                            "sqrt": math.sqrt, "log": math.log10, 
                            "pi": math.pi, "e": math.e
                        }
                        result = str(eval(current_text, {"__builtins__": None}, safe_dict))
                        self.calc_input.text = result
                    except Exception:
                        self.calc_input.text = "Hata"
                else:
                    self.calc_input.text = current_text + btn_text

            for btn_text in buttons:
                if btn_text == '=':
                    bg_col = (0.13, 0.59, 0.95, 1)
                    txt_col = (1, 1, 1, 1)
                elif btn_text == 'C':
                    bg_col = (0.9, 0.2, 0.2, 1)
                    txt_col = (1, 1, 1, 1)
                elif btn_text == '':
                    bg_col = (1, 1, 1, 0)
                    txt_col = (1, 1, 1, 0)
                else:
                    bg_col = (0.9, 0.9, 0.9, 1)
                    txt_col = (0.1, 0.1, 0.1, 1)
                
                btn = MDRaisedButton(
                    text=btn_text, 
                    md_bg_color=bg_col,
                    theme_text_color="Custom",
                    text_color=txt_col,
                    size_hint=(1, 1)
                )
                btn.bind(on_release=on_calc_button_press)
                self.calc_grid.add_widget(btn)

            self.calc_layout.add_widget(self.calc_grid)

            self.calc_dialog = MDDialog(
                title="Bilimsel Hesap Makinesi",
                type="custom",
                content_cls=self.calc_layout,
                buttons=[
                    MDRaisedButton(
                        text="KAPAT", 
                        on_release=lambda x: self.calc_dialog.dismiss(), 
                        md_bg_color=(0.8, 0.2, 0.2, 1)
                    )
                ]
            )
            self.calc_dialog.open()
            
        elif calc_type == "interest":
            self.int_layout = MDBoxLayout(orientation="vertical", spacing="15dp", size_hint_y=None, height="280dp")
            self.int_principal = MDTextField(hint_text="Ana Para (₺)", input_filter="float")
            self.int_rate = MDTextField(hint_text="Yıllık Faiz Oranı (%)", input_filter="float")
            self.int_days = MDTextField(hint_text="Vade (Gün)", input_filter="int")
            self.int_result_label = MDLabel(text="Sonuç bekleniyor...", theme_text_color="Primary", bold=True, halign="center", font_style="Subtitle2")
            
            self.int_layout.add_widget(self.int_principal)
            self.int_layout.add_widget(self.int_rate)
            self.int_layout.add_widget(self.int_days)
            self.int_layout.add_widget(self.int_result_label)
            
            self.int_dialog = MDDialog(
                title="Faiz Getirisi", type="custom", content_cls=self.int_layout,
                buttons=[
                    MDRaisedButton(text="KAPAT", on_release=lambda x: self.int_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                    MDRaisedButton(text="HESAPLA", on_release=self.calculate_interest)
                ]
            )
            self.int_dialog.open()
            
        elif calc_type == "compound":
            self.comp_layout = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="380dp")
            
            self.comp_mode = MDSegmentedControl(size_hint_x=1)
            self.comp_mode.add_widget(MDSegmentedControlItem(text="Basit"))
            self.comp_mode.add_widget(MDSegmentedControlItem(text="Gelişmiş"))
            self.comp_mode.bind(on_active=self.toggle_compound_mode)
            
            self.comp_principal = MDTextField(hint_text="Ana Para (₺)", input_filter="float")
            self.comp_rate = MDTextField(hint_text="Yıllık Faiz Oranı (%)", input_filter="float")
            self.comp_time = MDTextField(hint_text="Süre (Yıl)", input_filter="int")
            
            # Gelişmiş mod için
            self.comp_deposit = MDTextField(hint_text="Aylık Eklenen Tutar (₺)", input_filter="float", opacity=0, disabled=True)
            
            self.comp_result_label = MDLabel(text="Sonuç bekleniyor...", theme_text_color="Primary", bold=True, halign="center", font_style="Subtitle2")
            
            self.comp_layout.add_widget(self.comp_mode)
            self.comp_layout.add_widget(self.comp_principal)
            self.comp_layout.add_widget(self.comp_rate)
            self.comp_layout.add_widget(self.comp_time)
            self.comp_layout.add_widget(self.comp_deposit)
            self.comp_layout.add_widget(self.comp_result_label)
            
            self.comp_dialog = MDDialog(
                title="Bileşik Faiz", type="custom", content_cls=self.comp_layout,
                buttons=[
                    MDRaisedButton(text="KAPAT", on_release=lambda x: self.comp_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                    MDRaisedButton(text="HESAPLA", on_release=self.calculate_compound)
                ]
            )
            self.comp_dialog.open()
            
        elif calc_type == "loan":
            self.loan_scroll = ScrollView(size_hint=(1, None), height="400dp")
            
            self.loan_layout = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None)
            self.loan_layout.bind(minimum_height=self.loan_layout.setter('height'))
            
            self.loan_mode = MDSegmentedControl(size_hint_x=1)
            self.loan_mode.add_widget(MDSegmentedControlItem(text="Basit"))
            self.loan_mode.add_widget(MDSegmentedControlItem(text="Gelişmiş"))
            self.loan_mode.bind(on_active=self.toggle_loan_mode)
            
            self.loan_custom_name = MDTextField(hint_text="Borç/Kredi Adı (Örn: Araba Kredisi)", max_text_length=30)
            self.loan_amount = MDTextField(hint_text="Kredi Tutarı (₺)", input_filter="float")
            self.loan_rate = MDTextField(hint_text="Aylık Faiz Oranı (%)", input_filter="float")
            self.loan_term = MDTextField(hint_text="Vade (Ay - Maks 36)", input_filter="int")
            
            self.loan_type_selected = "İhtiyaç"
            self.loan_type = MDSegmentedControl(size_hint_x=1, opacity=0, disabled=True)
            self.loan_type.add_widget(MDSegmentedControlItem(text="İhtiyaç"))
            self.loan_type.add_widget(MDSegmentedControlItem(text="Taşıt"))
            self.loan_type.add_widget(MDSegmentedControlItem(text="Konut"))
            self.loan_type.bind(on_active=self.update_loan_type)
            
            self.custom_expenses = []
            
            self.expense_header_layout = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="40dp", opacity=0, disabled=True)
            self.expense_header_label = MDLabel(text="Özel Masraflar (0/10)", font_style="Caption")
            self.add_expense_btn = MDFlatButton(text="+ EKLE", on_release=self.open_expense_dialog, text_color=(0.13, 0.59, 0.95, 1))
            self.expense_header_layout.add_widget(self.expense_header_label)
            self.expense_header_layout.add_widget(self.add_expense_btn)
            
            self.expense_list_scroll = ScrollView(size_hint_y=None, height="60dp", opacity=0, disabled=True)
            self.expense_list_layout = MDBoxLayout(orientation="vertical", spacing="4dp", size_hint_y=None)
            self.expense_list_layout.bind(minimum_height=self.expense_list_layout.setter('height'))
            self.expense_list_scroll.add_widget(self.expense_list_layout)
            
            self.loan_result_label = MDLabel(text="Hesaplama bekleniyor...", theme_text_color="Primary", bold=True, halign="center", font_style="Subtitle2")
            
            self.loan_layout.add_widget(self.loan_mode)
            self.loan_layout.add_widget(self.loan_custom_name)
            self.loan_layout.add_widget(self.loan_amount)
            self.loan_layout.add_widget(self.loan_rate)
            self.loan_layout.add_widget(self.loan_term)
            self.loan_layout.add_widget(self.loan_type)
            self.loan_layout.add_widget(self.expense_header_layout)
            self.loan_layout.add_widget(self.expense_list_scroll)
            self.loan_layout.add_widget(self.loan_result_label)
            
            self.loan_scroll.add_widget(self.loan_layout)
            
            self.loan_table_btn = MDRaisedButton(text="TABLO", on_release=self.show_payment_plan_table, opacity=0, disabled=True, md_bg_color=(0.13, 0.59, 0.95, 1))
            self.add_debt_btn = MDRaisedButton(text="Borç Olarak Ekle", on_release=self.add_loan_to_debts, opacity=0, disabled=True, md_bg_color=(0.18, 0.8, 0.25, 1))
            self.loan_dialog = MDDialog(
                title="Kredi Hesaplama", type="custom", content_cls=self.loan_scroll,
                buttons=[
                    MDRaisedButton(text="KAPAT", on_release=lambda x: self.loan_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                    self.loan_table_btn,
                    self.add_debt_btn,
                    MDRaisedButton(text="HESAPLA", on_release=self.calculate_loan)
                ]
            )
            self.loan_dialog.open()
            
        elif calc_type == "savings_goal":
            self.sg_auto_deposit = False
            self.sg_layout = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="420dp")

            self.sg_name_input   = MDTextField(hint_text="Hedef Ad\u0131 (\u00d6rn: Raspberry Pi Projesi)", max_text_length=30)
            self.sg_target_input = MDTextField(hint_text="Hedef Miktar (\u20ba)", input_filter="float")
            self.sg_deposit_input= MDTextField(hint_text="D\u00fczenli Eklenecek Tutar (\u20ba)", input_filter="float")

            self.sg_period_segment = MDSegmentedControl(size_hint_x=1)
            self.sg_period_segment.add_widget(MDSegmentedControlItem(text="G\u00fcnl\u00fck"))
            self.sg_period_segment.add_widget(MDSegmentedControlItem(text="Ayl\u0131k"))
            self.sg_period = "G\u00fcnl\u00fck"
            self.sg_period_segment.bind(on_active=self.update_sg_period)

            # Auto-deposit switch row
            from kivymd.uix.selectioncontrol import MDSwitch
            switch_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
            switch_lbl = MDLabel(
                text="Bu tutar her d\u00f6nem otomatik eklensin mi?",
                valign="center",
            )
            switch_lbl.bind(size=switch_lbl.setter('text_size'))
            self.sg_auto_switch = MDSwitch(size_hint_x=None, width=dp(65))
            def _on_switch(instance, val):
                self.sg_auto_deposit = val
            self.sg_auto_switch.bind(active=_on_switch)
            switch_row.add_widget(switch_lbl)
            switch_row.add_widget(self.sg_auto_switch)

            self.sg_result_label = MDLabel(
                text="Hesaplama bekleniyor...",
                theme_text_color="Primary", bold=True, halign="center", font_style="Subtitle2"
            )

            self.sg_layout.add_widget(self.sg_name_input)
            self.sg_layout.add_widget(self.sg_target_input)
            self.sg_layout.add_widget(self.sg_deposit_input)
            self.sg_layout.add_widget(self.sg_period_segment)
            self.sg_layout.add_widget(switch_row)
            self.sg_layout.add_widget(self.sg_result_label)

            self.sg_dialog = MDDialog(
                title="Birikim Hedefi", type="custom", content_cls=self.sg_layout,
                buttons=[
                    MDRaisedButton(text="KAPAT", on_release=lambda x: self.sg_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                    MDRaisedButton(text="HESAPLA", on_release=self.calculate_savings_goal),
                    MDRaisedButton(text="HEDEFE EKLE", on_release=self.commit_savings_goal, md_bg_color=(0.18, 0.8, 0.25, 1)),
                ]
            )
            self.sg_dialog.open()

    def calculate_compound(self, *args):
        """Bileşik faiz hesaplar (A = P * (1 + r)^t).
        Aylık düzenli ekleme varsa gelecek değer (FV) formülünü de sürece katar.
        """
        try:
            p = float(self.comp_principal.text)
            r = float(self.comp_rate.text) / 100
            t = int(self.comp_time.text)
            deposit = float(self.comp_deposit.text) if self.comp_deposit.text else 0.0
            
            if p <= 0 or r <= 0 or t <= 0:
                toast("Lütfen 0'dan büyük değerler girin!")
                return
                
            # Bileşik faiz (Yıllık bileşme)
            amount = p * ((1 + r) ** t)
            
            # Aylık ekleme varsa
            if deposit > 0:
                months = t * 12
                monthly_rate = r / 12
                # Gelecek değer formülü: PMT * (((1 + r/n)^(nt) - 1) / (r/n)) * (1+r/n) -> opsiyonel 1+r/n dönemi başı ödeme ise
                amount += deposit * (((1 + monthly_rate)**months - 1) / monthly_rate)
                
            total_invested = p + (deposit * t * 12)
            profit = amount - total_invested
            
            f_invest = f"{total_invested:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            f_profit = f"{profit:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            f_amount = f"{amount:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            
            self.comp_result_label.text = f"Yatırım: {f_invest}\nKazanç: + {f_profit}\nToplam: {f_amount}"
            self.comp_result_label.theme_text_color = "Custom"
            self.comp_result_label.text_color = (0.6, 0.2, 0.8, 1)
        except ValueError:
            toast("Lütfen geçerli sayılar girin!")

    def calculate_loan(self, *args):
        """Kredi hesaplar (Anüite formülü: Taksit = P * (i * (1+i)^n) / ((1+i)^n - 1)).
        Gelişmiş modda ek masrafları (peşin/taksitli) ve vergileri (KKDF/BSMV) dahil eder.
        """
        try:
            p = float(self.loan_amount.text)
            r_percent = float(self.loan_rate.text)
            n = int(self.loan_term.text)
            
            if p <= 0 or r_percent <= 0 or n <= 0:
                toast("Lütfen 0'dan büyük değerler girin!")
                return
            
            # --- YENİ DİNAMİK VADE KONTROLÜ ---
            max_term = 36 # Varsayılan (Basit mod veya İhtiyaç)
            
            if not self.loan_type.disabled: # Eğer "Gelişmiş" mod açıksa
                if self.loan_type_selected == "Taşıt":
                    max_term = 48
                elif self.loan_type_selected == "Konut":
                    max_term = 120
                    
            if n > max_term:
                toast(f"Seçtiğiniz kredi türü için vade en fazla {max_term} ay olabilir!")
                return
            # -----------------------------------
                
            r = r_percent / 100
            is_advanced = not self.loan_type.disabled
            
            kkdf = 0.15
            bsmv = 0.15
            
            i = r * (1 + kkdf + bsmv)
            emi = p * (i * ((1 + i)**n)) / (((1 + i)**n) - 1)
            
            total_custom_upfront = 0.0
            total_all_recurring = 0.0
            
            if is_advanced:
                for exp in self.custom_expenses:
                    if exp["type"] == "Tek Seferlik":
                        total_custom_upfront += exp["amount"]
                    else:
                        total_all_recurring += exp["amount"]
                        
            file_expense_taxed = 0.0
            insurance = 0.0
            net_cash = p
            
            total_upfront = 0.0
            
            if is_advanced:
                file_expense_taxed = (p * 0.005) * 1.15
                insurance = p * 0.008
                total_upfront = file_expense_taxed + insurance + total_custom_upfront
                net_cash = p - total_upfront
                
            total_payment = (emi * n) + total_all_recurring
            
            f_emi = f"{emi:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            f_total = f"{total_payment:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            
            res_text = f"Temel Taksit: {f_emi}\nToplam Geri Ödeme: {f_total}"
            if is_advanced:
                f_net = f"{net_cash:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
                res_text += f"\nEle Geçecek: {f_net} (Tüm Peşin Masraflar Düşülmüş)"
                
            self.loan_result_label.text = res_text
            self.loan_result_label.theme_text_color = "Custom"
            self.loan_result_label.text_color = (0.9, 0.2, 0.3, 1)
            
            self.loan_table_data = []
            kalan = p
            for ay in range(1, n + 1):
                faiz = kalan * r
                _kkdf = faiz * kkdf
                _bsmv = faiz * bsmv
                anapara_odenen = emi - (faiz + _kkdf + _bsmv)
                kalan -= anapara_odenen
                if kalan < 0.01:
                    kalan = 0
                
                ek_masraf = 0.0
                if is_advanced:
                    for exp in self.custom_expenses:
                        if exp["type"] == "Çok Seferlik" and ay <= exp["term"]:
                            ek_masraf += (exp["amount"] / exp["term"])
                            
                toplam_odeme = emi + ek_masraf
                faiz_vergi = faiz + _kkdf + _bsmv
                
                f_ay = str(ay)
                f_t = f"{emi:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                f_ek = f"{ek_masraf:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                f_toplam = f"{toplam_odeme:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                f_a = f"{anapara_odenen:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                f_fv = f"{faiz_vergi:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                f_bal = f"{kalan:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                self.loan_table_data.append((f_ay, f_t, f_ek, f_toplam, f_a, f_fv, f_bal))

            if is_advanced:
                self.loan_table_btn.opacity = 1
                self.loan_table_btn.disabled = False
            else:
                self.loan_table_btn.opacity = 0
                self.loan_table_btn.disabled = True
            
            self.add_debt_btn.opacity = 1
            self.add_debt_btn.disabled = False
            self.last_calculated_loan = {
                "name": self.loan_custom_name.text.strip() if self.loan_custom_name.text.strip() else f"{self.loan_type_selected} Kredisi",
                "total_amount": total_payment,
                "monthly_payment": emi,
                "total_installments": n
            }
            
        except ValueError:
            toast("Lütfen tüm alanları sayılarla doldurun!")

    def export_plan_to_pdf(self, *args):
        """Kredi ödeme planını masaüstüne 'Ödeme_Planı.pdf' olarak dışa aktarır."""
        import os
        from fpdf import FPDF
        
        def tr(text):
            return str(text).replace("₺", "TL").replace("İ", "I").replace("ı", "i").replace("Ş", "S").replace("ş", "s").replace("Ğ", "G").replace("ğ", "g").replace("Ü", "U").replace("ü", "u").replace("Ö", "O").replace("ö", "o").replace("Ç", "C").replace("ç", "c")
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.cell(200, 10, text=tr("Ödeme Planı"), ln=True, align="C")
        pdf.ln(10)
        
        pdf.set_font("Helvetica", style="B", size=8)
        cols = ["Ay", "Temel Taksit", "Ek Masraf", "Toplam Ödeme", "Anapara", "Faiz/Vergi", "Bakiye"]
        col_widths = [10, 25, 25, 30, 25, 25, 30]
        
        for i, col in enumerate(cols):
            pdf.cell(col_widths[i], 10, text=tr(col), border=1, align="C")
        pdf.ln()
        
        pdf.set_font("Helvetica", size=8)
        for row in self.loan_table_data:
            for i, val in enumerate(row):
                pdf.cell(col_widths[i], 10, text=tr(val), border=1, align="C")
            pdf.ln()
            
        if not self.loan_type.disabled:
            pdf.ln(10)
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.cell(200, 10, text=tr("--- TEK SEFERLİK (PEŞİN) MASRAFLAR DETAYI ---"), ln=True, align="L")
            
            pdf.set_font("Helvetica", size=10)
            p = float(self.loan_amount.text)
            file_exp = (p * 0.005) * 1.15
            ins_exp = p * 0.008
            
            pdf.cell(200, 8, text=tr(f"- Kredi Tahsis Ücreti: {file_exp:,.2f} TL"), ln=True, align="L")
            pdf.cell(200, 8, text=tr(f"- Hayat Sigortası (Ortalama): {ins_exp:,.2f} TL"), ln=True, align="L")
            
            total_pesin = file_exp + ins_exp
            
            for exp in self.custom_expenses:
                if exp["type"] == "Tek Seferlik":
                    pdf.cell(200, 8, text=tr(f"- {exp['name']}: {exp['amount']:,.2f} TL"), ln=True, align="L")
                    total_pesin += exp["amount"]
            
            pdf.ln(4)
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.cell(200, 8, text=tr(f"- Toplam Peşin Kesinti: {total_pesin:,.2f} TL"), ln=True, align="L")
            net_tutar = p - total_pesin
            pdf.cell(200, 8, text=tr(f"- Krediden Ele Geçecek Net Tutar: {net_tutar:,.2f} TL"), ln=True, align="L")

        home_dir = os.path.expanduser("~")
        desk_dir = os.path.join(home_dir, "Masaüstü")
        if not os.path.exists(desk_dir):
            desk_dir = os.path.join(home_dir, "Desktop")
            if not os.path.exists(desk_dir):
                desk_dir = home_dir
        
        filepath = os.path.join(desk_dir, "Ödeme_Planı.pdf")
        pdf.output(filepath)
        toast(f"PDF kaydedildi: {filepath}")


    # ── Kredi/faiz hesaplayıcı yardımcıları ──────────────────────────────
    # Bu metodlar main.py'deki FinoraApp gövdesinden taşındı; open_calculator
    # içindeki buton bind'ları zaten bunlara başvuruyordu, artık aynı sınıfta
    # tanımlılar. Davranışları değişmedi.

    def toggle_compound_mode(self, segment, item):
        """Bileşik faiz hesaplayıcısında basit/gelişmiş mod geçişini yönetir."""
        if item.text == "Gelişmiş":
            self.comp_deposit.opacity = 1
            self.comp_deposit.disabled = False
        else:
            self.comp_deposit.opacity = 0
            self.comp_deposit.disabled = True
            self.comp_deposit.text = ""

    def toggle_loan_mode(self, segment, item):
        """Kredi hesaplayıcısında gelişmiş mod açıldığında özel masraf alanlarını görünür yapar."""
        if item.text == "Gelişmiş":
            self.loan_type.opacity = 1
            self.loan_type.disabled = False
            self.expense_header_layout.opacity = 1
            self.expense_header_layout.disabled = False
            self.expense_list_scroll.opacity = 1
            self.expense_list_scroll.disabled = False
        else:
            self.loan_type.opacity = 0
            self.loan_type.disabled = True
            self.expense_header_layout.opacity = 0
            self.expense_header_layout.disabled = True
            self.expense_list_scroll.opacity = 0
            self.expense_list_scroll.disabled = True
            
    def update_loan_type(self, segment, item):
        """Kredi türü (İhtiyaç/Taşıt/Konut) değiştikçe maksimum vade uyarısını ve ipucunu günceller."""
        self.loan_type_selected = item.text
        
        # Seçime göre dinamik hint_text (İpucu) güncellemesi
        if item.text == "İhtiyaç":
            self.loan_term.hint_text = "Vade (Ay - Maks 36)"
        elif item.text == "Taşıt":
            self.loan_term.hint_text = "Vade (Ay - Maks 48)"
        elif item.text == "Konut":
            self.loan_term.hint_text = "Vade (Ay - Maks 120)"
        
    def open_expense_dialog(self, *args):
        """Krediye özel masraf eklemek için bir diyalog penceresi açar (maks. 10 masraf)."""
        if len(self.custom_expenses) >= 10:
            toast("Maksimum 10 masraf ekleyebilirsiniz.")
            return
            
        self.exp_dialog_layout = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="260dp")
        
        self.exp_name = MDTextField(hint_text="Masraf Adı (Örn: Ekspertiz)", max_text_length=30)
        
        self.exp_type_segment = MDSegmentedControl(size_hint_x=1)
        self.exp_type_segment.add_widget(MDSegmentedControlItem(text="Tek Seferlik"))
        self.exp_type_segment.add_widget(MDSegmentedControlItem(text="Çok Seferlik"))
        
        self.exp_amount = MDTextField(hint_text="Toplam Tutar (₺)", input_filter="float")
        
        self.exp_term = MDTextField(hint_text="Süre (Ay)", input_filter="int", opacity=0, disabled=True)
        
        def toggle_term_field(segment, item):
            if item.text == "Çok Seferlik":
                self.exp_term.opacity = 1
                self.exp_term.disabled = False
            else:
                self.exp_term.opacity = 0
                self.exp_term.disabled = True
                self.exp_term.text = ""
                
        self.exp_type_segment.bind(on_active=toggle_term_field)
        
        self.exp_dialog_layout.add_widget(self.exp_name)
        self.exp_dialog_layout.add_widget(self.exp_type_segment)
        self.exp_dialog_layout.add_widget(self.exp_amount)
        self.exp_dialog_layout.add_widget(self.exp_term)
        
        self.expense_dialog = MDDialog(
            title="Özel Masraf Ekle",
            type="custom",
            content_cls=self.exp_dialog_layout,
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.expense_dialog.dismiss()),
                MDFlatButton(text="EKLE", on_release=self.add_custom_expense)
            ]
        )
        self.expense_dialog.open()

    def add_custom_expense(self, *args):
        """Girilen özel masrafı doğrular ve kredi masrafları listesine ekler."""
        name = self.exp_name.text.strip()
        amount_text = self.exp_amount.text
        
        if not name or not amount_text:
            toast("Lütfen ad ve tutar girin!")
            return
            
        amount = float(amount_text)
        if amount <= 0:
            toast("Tutar 0'dan büyük olmalı!")
            return
            
        is_cok = not self.exp_term.disabled
        exp_type = "Çok Seferlik" if is_cok else "Tek Seferlik"
        
        term = 0
        if is_cok:
            if not self.exp_term.text:
                toast("Lütfen süre girin!")
                return
            term = int(self.exp_term.text)
            if term <= 0:
                toast("Süre 1 aydan büyük olmalı!")
                return
            if self.loan_term.text and term > int(self.loan_term.text):
                toast(f"Süre, kredi vadesinden büyük olamaz ({self.loan_term.text} ay)!")
                return

        exp_data = {
            "name": name,
            "type": exp_type,
            "amount": amount,
            "term": term
        }
        self.custom_expenses.append(exp_data)
        
        self.expense_dialog.dismiss()
        self.update_expense_list_ui()

    def update_expense_list_ui(self):
        """Özel masraflar listesi arayüzünü (UI) yeniden çizer."""
        self.expense_list_layout.clear_widgets()
        self.expense_header_label.text = f"Özel Masraflar ({len(self.custom_expenses)}/10)"
        
        for idx, exp in enumerate(self.custom_expenses):
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
            
            desc = f"{exp['name']} ({exp['type']}) - {exp['amount']} ₺"
            if exp["type"] == "Çok Seferlik":
                desc += f" / {exp['term']} Ay"
                
            lbl = MDLabel(text=desc, font_style="Caption")
            
            del_btn = MDIconButton(
                icon="close", 
                icon_size="16sp",
                size_hint=(None, None), 
                size=("24dp", "24dp"),
                pos_hint={"center_y": 0.5},
                on_release=lambda x, index=idx: self.remove_custom_expense(index)
            )
            row.add_widget(lbl)
            row.add_widget(del_btn)
            self.expense_list_layout.add_widget(row)

    def remove_custom_expense(self, index):
        """Belirtilen indeksteki özel masrafı listeden çıkarır."""
        if 0 <= index < len(self.custom_expenses):
            self.custom_expenses.pop(index)
            self.update_expense_list_ui()

    def calculate_interest(self, *args):
        """Basit mevduat faizi hesaplar (Getiri = P * r * d / 36500) ve %5 stopaj düşer."""
        try:
            p = float(self.int_principal.text)
            r = float(self.int_rate.text)
            d = int(self.int_days.text)
            
            if p <= 0 or r <= 0 or d <= 0:
                toast("Lütfen 0'dan büyük değerler girin!")
                return
                
            gross_profit = p * r * d / 36500
            net_profit = gross_profit * 0.95 # Varsayılan %5 stopaj (Vergi)
            total = p + net_profit
            
            f_profit = f"{net_profit:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            f_total = f"{total:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            
            self.int_result_label.text = f"Net Getiri: + {f_profit}\nVade Sonu: {f_total}\n(%5 Stopaj düşülmüştür)"
            self.int_result_label.theme_text_color = "Custom"
            self.int_result_label.text_color = (0.13, 0.59, 0.95, 1)
        except ValueError:
            toast("Lütfen geçerli sayılar girin!")

    def show_payment_plan_table(self, *args):
        """Hesaplanan kredi ödeme planını bir veri tablosu (Data Table) diyaloğunda gösterir."""
        from kivymd.uix.datatables import MDDataTable
        from kivy.metrics import dp
        from kivymd.uix.boxlayout import MDBoxLayout
        
        table_layout = MDBoxLayout(orientation="vertical")
        self.table = MDDataTable(
            use_pagination=True,
            rows_num=10,
            column_data=[
                ("Ay", dp(15)),
                ("Temel Taksit", dp(30)),
                ("Ek Masraf", dp(25)),
                ("Toplam Ödeme", dp(30)),
                ("Anapara", dp(25)),
                ("Faiz/Vergi", dp(25)),
                ("Bakiye", dp(30)),
            ],
            row_data=self.loan_table_data,
        )
        table_layout.add_widget(self.table)
        
        self.table_dialog = MDDialog(
            title="Ödeme Planı",
            type="custom",
            content_cls=table_layout,
            size_hint=(0.95, 0.95),
            buttons=[
                MDRaisedButton(text="KAPAT", on_release=lambda x: self.table_dialog.dismiss(), md_bg_color=(0.8, 0.2, 0.2, 1)),
                MDRaisedButton(text="PDF İNDİR", on_release=self.export_plan_to_pdf, md_bg_color=(0.13, 0.59, 0.95, 1))
            ]
        )
        self.table_dialog.open()
