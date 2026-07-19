import calendar
import datetime
import threading

from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel


class RecurringMixin:
    """Tekrarlanan ödemeler (Kira, Netflix, Spotify vb.) akışı: yaklaşan ödeme
    listesini yükleme/çizme, manuel ödeme, durdurma ve açılışta otomatik düşme.

    Kayıtlar mixins/transaction_mixin.py'nin "Yeni İşlem Ekle" dialogundan
    (tekrarlanan anahtarı açıkken) oluşturulur; bu mixin sadece vade takibini ve
    anasayfadaki uyarı kartını yönetir. debt_mixin.py'deki thread+Clock kalıbını
    izler.
    """

    def load_upcoming_recurring(self, *args):
        from database.db import get_active_recurring_payments

        def fetch():
            try:
                payments = get_active_recurring_payments()
                Clock.schedule_once(lambda dt: self.render_upcoming_payments(payments), 0)
            except Exception as e:
                print("Error fetching recurring payments:", e)

        threading.Thread(target=fetch, daemon=True).start()

    def render_upcoming_payments(self, payments):
        """Vadesi 7 gün içinde olan (gecikmiş dahil) ödemeleri kart olarak basar."""
        try:
            container = self.root.ids.upcoming_payments_container
            container.clear_widgets()

            today = datetime.date.today()
            visible = [
                p for p in payments
                if (datetime.date.fromisoformat(p["next_due_date"]) - today).days <= 7
            ]

            if not visible:
                lbl = MDLabel(
                    text="Yaklaşan ödeme bulunmuyor.",
                    theme_text_color="Secondary",
                    font_style="Body2",
                    halign="center",
                )
                lbl.bind(size=lbl.setter('text_size'))
                container.add_widget(lbl)
                return

            for p in visible:
                due = datetime.date.fromisoformat(p["next_due_date"])
                days_left = (due - today).days
                if days_left < 0:
                    status = f"Gecikti ({-days_left} gün)"
                elif days_left == 0:
                    status = "Bugün"
                else:
                    status = f"{days_left} gün kaldı"

                card = MDCard(
                    orientation="vertical", padding="12dp", spacing="6dp",
                    size_hint_y=None, height="100dp", elevation=1, radius=[10]
                )

                header = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
                name_lbl = MDLabel(text=p["name"], font_style="Subtitle2", bold=True)
                amount_lbl = MDLabel(
                    text=f"{p['amount']:,.2f} ₺", font_style="Caption",
                    theme_text_color="Secondary", halign="right"
                )
                header.add_widget(name_lbl)
                header.add_widget(amount_lbl)

                status_color = (0.9, 0.2, 0.2, 1) if days_left < 0 else (0.12, 0.53, 0.53, 1)
                status_lbl = MDLabel(
                    text=status, font_style="Caption",
                    theme_text_color="Custom", text_color=status_color
                )

                btn_layout = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="32dp")
                if not p["auto_deduct"]:
                    pay_btn = MDFlatButton(text="ÖDE", on_release=lambda x, pp=p: self.pay_recurring_now(pp))
                    btn_layout.add_widget(pay_btn)
                else:
                    auto_lbl = MDLabel(text="Otomatik düşecek", font_style="Caption", theme_text_color="Secondary")
                    btn_layout.add_widget(auto_lbl)
                pause_btn = MDFlatButton(text="DURDUR", on_release=lambda x, pid=p["id"]: self.deactivate_recurring(pid))
                btn_layout.add_widget(pause_btn)

                card.add_widget(header)
                card.add_widget(status_lbl)
                card.add_widget(btn_layout)
                container.add_widget(card)
        except Exception as e:
            print("Error rendering upcoming payments:", e)

    def pay_recurring_now(self, payment):
        from database.db import process_due_recurring_payment

        def process():
            try:
                process_due_recurring_payment(payment)
                Clock.schedule_once(lambda dt: toast(f"{payment['name']} ödendi!"), 0)
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception as e:
                print("Error paying recurring payment:", e)
                Clock.schedule_once(lambda dt: toast("İşlem sırasında hata oluştu!"), 0)

        threading.Thread(target=process, daemon=True).start()

    def deactivate_recurring(self, payment_id):
        from database.db import deactivate_recurring_payment

        def process():
            try:
                deactivate_recurring_payment(payment_id)
                Clock.schedule_once(lambda dt: toast("Tekrarlanan ödeme durduruldu."), 0)
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
            except Exception as e:
                print("Error deactivating recurring payment:", e)

        threading.Thread(target=process, daemon=True).start()

    def process_due_auto_deductions(self):
        from database.db import (
            get_active_recurring_payments, process_due_recurring_payment,
            get_active_debts, update_debt_progress, update_debt_last_auto_pay
        )
        from services.transaction_service import TransactionService

        def process():
            try:
                today = datetime.date.today()
                ui_needs_refresh = False
                
                # 1. MEVCUT TEKRARLANAN ÖDEMELER (Kira, Faturalar vb.)
                payments = get_active_recurring_payments()
                due_auto = [
                    p for p in payments
                    if p["auto_deduct"] and datetime.date.fromisoformat(p["next_due_date"]) <= today
                ]
                for p in due_auto:
                    process_due_recurring_payment(p)
                    ui_needs_refresh = True
                
                # 2. OTOMATİK BORÇ/KREDİ TAKSİT ÖDEMELERİ
                debts = get_active_debts()
                current_month_str = today.strftime("%Y-%m")

                for debt in debts:
                    if not debt.get("is_auto_pay"):
                        continue

                    remaining = debt['total_installments'] - debt['paid_installments']
                    if remaining <= 0:
                        continue

                    # 29-31 Taksit Tuzağı: auto_pay_day 31 seçilip ay 30 (veya Şubat
                    # 28/29) çekiyorsa today.day hiçbir zaman 31'e ulaşamaz ve taksit
                    # sessizce atlanırdı. Ayın gerçek son gününü aşmayan güvenli bir
                    # ödeme günü kullan.
                    days_in_month = calendar.monthrange(today.year, today.month)[1]
                    effective_pay_day = min(debt.get("auto_pay_day") or 1, days_in_month)
                    if today.day < effective_pay_day:
                        continue

                    last_pay_str = debt.get("last_auto_pay_date")
                    if last_pay_str == current_month_str:
                        continue  # bu ay zaten çekilmiş

                    # Birikmiş Dönem Kaybı: uygulama birkaç ay açılmadıysa, son çekilen
                    # ay ile şu an arasında kaç ay atlandığını hesaplayıp aradaki
                    # taksitleri geriye dönük düş (recurring_mixin'deki abonelik
                    # telafi mantığıyla aynı fikir: son bilinen tarihten şimdiye kaç
                    # periyot geçtiğini say). last_auto_pay_date hiç set edilmemişse
                    # (ilk otomatik ödeme) geriye dönük referans yok, sadece bu ayı öde.
                    if last_pay_str:
                        last_year, last_month = (int(x) for x in last_pay_str.split("-"))
                        months_missed = (today.year - last_year) * 12 + (today.month - last_month)
                    else:
                        months_missed = 1
                    months_missed = max(1, months_missed)

                    installments_to_pay = min(months_missed, remaining)
                    new_paid_total = debt['paid_installments'] + installments_to_pay
                    is_active = 0 if new_paid_total >= debt['total_installments'] else 1

                    update_debt_progress(debt['id'], installments_to_pay, is_active=is_active)
                    update_debt_last_auto_pay(debt['id'], current_month_str)

                    desc = f"{debt['debt_name']} (Otomatik Taksit Ödemesi)"
                    if installments_to_pay > 1:
                        desc = f"{debt['debt_name']} (Otomatik Taksit Ödemesi — {installments_to_pay} ay telafi)"

                    # Atlanan her ay için ayrı gider kaydı oluştur ki toplam bakiye
                    # ve işlem geçmişi gerçek taksit sayısını yansıtsın.
                    for _ in range(installments_to_pay):
                        TransactionService.add_transaction(
                            account_id=1,
                            amount=debt['monthly_payment'],
                            transaction_type="expense",
                            category="Kredi Taksiti",
                            description=desc
                        )
                    ui_needs_refresh = True

                # 3. ORTAK UI SENKRONİZASYONU
                if ui_needs_refresh:
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                    
                    # UI üzerindeki ilerleme çubuğu (progress bar) ve kalan taksit yazısını yenile
                    if hasattr(self, 'load_active_debts'):
                        Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                        
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
            except Exception as e:
                print("Error processing auto deductions:", e)

        threading.Thread(target=process, daemon=True).start()
