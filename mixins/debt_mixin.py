from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from services.transaction_service import TransactionService
import threading
from kivymd.uix.card import MDCard
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.slider import MDSlider


class DebtMixin:
    """Borç/kredi takibi: hesaplanan krediyi borç olarak kaydetme, aktif borç
    kartlarını listeleme, taksit ödeme ve borcu tamamen kapatma akışları.

    Taksit ödemeleri aynı zamanda "expense" tipinde bir işlem kaydı üretir; böylece
    borç ödemeleri bakiye ve grafiklere de yansır. DB erişimleri thread'de yapılır.
    """

    def add_loan_to_debts(self, *args):
        """CalculatorMixin'in son kredi hesabını (last_calculated_loan) borç olarak kaydeder."""
        if not hasattr(self, 'last_calculated_loan'):
            toast("Önce hesaplama yapın!")
            return
            
        from database.db import insert_debt

        def save_debt():
            try:
                loan = self.last_calculated_loan
                insert_debt(loan["name"], loan["total_amount"], loan["monthly_payment"], loan["total_installments"])
                Clock.schedule_once(lambda dt: toast("Borç başarıyla eklendi!"), 0)
                Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                Clock.schedule_once(lambda dt: self.loan_dialog.dismiss(), 0)
            except Exception as e:
                print("Error adding debt:", e)
                Clock.schedule_once(lambda dt: toast("Borç eklenirken hata oluştu!"), 0)
                
        threading.Thread(target=save_debt, daemon=True).start()

    def load_active_debts(self, *args):
        from database.db import get_active_debts

        def fetch_debts():
            try:
                debts = get_active_debts()
                Clock.schedule_once(lambda dt: self.render_active_debts(debts), 0)
            except Exception as e:
                print("Error fetching debts:", e)

        threading.Thread(target=fetch_debts, daemon=True).start()

    def render_active_debts(self, debts):
        try:
            container = self.root.ids.active_debts_container
            container.clear_widgets()

            if not debts:
                lbl = MDLabel(text="Henüz aktif bir borcunuz bulunmuyor.", theme_text_color="Secondary", font_style="Body2", halign="center")
                container.add_widget(lbl)
                return

            for debt in debts:

                card = MDCard(orientation="vertical", padding="12dp", spacing="8dp", size_hint_y=None, height="140dp", elevation=1, radius=[10])
                
                header = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
                name_lbl = MDLabel(text=f"{debt['debt_name']}", font_style="Subtitle2", bold=True)
                amount_lbl = MDLabel(text=f"Aylık: {debt['monthly_payment']:,.2f} ₺", font_style="Caption", theme_text_color="Secondary", halign="right")
                header.add_widget(name_lbl)
                header.add_widget(amount_lbl)

                progress = MDProgressBar(value=debt["paid_installments"], max=debt["total_installments"], size_hint_y=None, height="8dp")
                
                status_lbl = MDLabel(text=f"Kalan: {debt['total_installments'] - debt['paid_installments']}/{debt['total_installments']} Taksit", font_style="Caption", theme_text_color="Primary")

                btn_layout = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="36dp")
                pay_btn = MDFlatButton(text="Taksit Öde", on_release=lambda x, d=debt: self.pay_debt_installments(d))
                close_btn = MDRaisedButton(text="Tamamen Kapat", md_bg_color=(0.9, 0.2, 0.2, 1), on_release=lambda x, d=debt: self.close_debt_completely(d))
                btn_layout.add_widget(pay_btn)
                btn_layout.add_widget(close_btn)

                card.add_widget(header)
                card.add_widget(progress)
                card.add_widget(status_lbl)
                card.add_widget(btn_layout)

                container.add_widget(card)
        except Exception as e:
            print("Error rendering debts:", e)

    def close_debt_completely(self, debt):
        """Kalan tüm taksitleri tek seferde kapatır: onay dialogu gösterir, onayda
        borcu pasife çeker ve kalan bakiye tutarında gider işlemi oluşturur."""

        remaining_installments = debt['total_installments'] - debt['paid_installments']
        remaining_balance = remaining_installments * debt['monthly_payment']
        
        def confirm(*args):
            self.dialog.dismiss()
            from database.db import update_debt_progress
            from services.transaction_service import TransactionService

            def process():
                try:
                    update_debt_progress(debt['id'], remaining_installments, is_active=0)
                    TransactionService.add_transaction(
                        account_id=1,
                        amount=remaining_balance,
                        transaction_type="expense",
                        category="Borç Ödeme",
                        description=f"{debt['debt_name']} (Tamamen Kapatma)"
                    )
                    Clock.schedule_once(lambda dt: toast("Borç tamamen kapatıldı!"), 0)
                    Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                except Exception as e:
                    print("Error closing debt:", e)
                    Clock.schedule_once(lambda dt: toast("İşlem sırasında hata oluştu!"), 0)

            threading.Thread(target=process, daemon=True).start()

        self.dialog = MDDialog(
            title="Borcu Kapat",
            text=f"Kalan {remaining_balance:,.2f} ₺ bakiyeyi kapatmak istediğinize emin misiniz?",
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.dialog.dismiss()),
                MDFlatButton(text="EVET, KAPAT", on_release=confirm)
            ]
        )
        self.dialog.open()

    def pay_debt_installments(self, debt):
        """Slider ile seçilen sayıda taksiti öder; son taksit ödeniyorsa borcu
        pasife çeker. Ödeme "Kredi Taksiti" kategorisinde gider olarak kaydedilir."""

        remaining_installments = debt['total_installments'] - debt['paid_installments']
        if remaining_installments <= 0:
            toast("Bu borç zaten tamamen ödenmiş!")
            return

        content = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="120dp")
        lbl = MDLabel(text=f"Kaç taksit ödemek istiyorsunuz? (Maks: {remaining_installments})", theme_text_color="Secondary")
        slider = MDSlider(min=1, max=remaining_installments, value=1, step=1)
        val_lbl = MDLabel(text="Seçilen: 1 Taksit", halign="center", bold=True)

        def on_slider_value(instance, value):
            val_lbl.text = f"Seçilen: {int(value)} Taksit"
            
        slider.bind(value=on_slider_value)

        content.add_widget(lbl)
        content.add_widget(slider)
        content.add_widget(val_lbl)

        def confirm(*args):
            self.dialog.dismiss()
            selected_installments = int(slider.value)
            amount_to_pay = selected_installments * debt['monthly_payment']
            is_active = 0 if selected_installments == remaining_installments else 1

            from database.db import update_debt_progress
            from services.transaction_service import TransactionService

            def process():
                try:
                    update_debt_progress(debt['id'], selected_installments, is_active=is_active)
                    TransactionService.add_transaction(
                        account_id=1,
                        amount=amount_to_pay,
                        transaction_type="expense",
                        category="Kredi Taksiti",
                        description=f"{debt['debt_name']} ({selected_installments} Taksit Ödemesi)"
                    )
                    Clock.schedule_once(lambda dt: toast(f"{selected_installments} taksit başarıyla ödendi!"), 0)
                    Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                except Exception as e:
                    print("Error paying installment:", e)
                    Clock.schedule_once(lambda dt: toast("İşlem sırasında hata oluştu!"), 0)

            threading.Thread(target=process, daemon=True).start()

        self.dialog = MDDialog(
            title="Taksit Öde",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.dialog.dismiss()),
                MDFlatButton(text="ÖDE", on_release=confirm)
            ]
        )
        self.dialog.open()
