import calendar
import datetime
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
import ui.theme as ftheme
from ui.i18n import tr as _t


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

        self._recurring_load_generation = (
            getattr(self, "_recurring_load_generation", 0) + 1
        )
        generation = self._recurring_load_generation

        def apply_result(payments):
            # Hızlı ekran geçişlerinde eski worker yeni sonucu ezmesin.
            if generation != getattr(self, "_recurring_load_generation", 0):
                return
            self.render_upcoming_payments(payments)

        def fetch():
            try:
                payments = get_active_recurring_payments()
                Clock.schedule_once(
                    lambda dt, value=payments: apply_result(value), 0,
                )
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Error fetching recurring payments")

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
                # Yükseklik açıkça veriliyor: kart içeriğe uyduğu için
                # (ui/dashboard.kv, upcoming_payments_card) size_hint_y=1 olan
                # bir etiket kapsayıcıya sıfır yükseklik katkısı yapardı.
                lbl = MDLabel(
                    text=_t("Yaklaşan ödeme bulunmuyor."),
                    theme_text_color="Secondary",
                    font_style="Body2",
                    halign="center",
                    size_hint_y=None,
                    height=dp(40),
                )
                lbl.bind(size=lbl.setter('text_size'))
                container.add_widget(lbl)
                return

            for p in visible:
                due = datetime.date.fromisoformat(p["next_due_date"])
                days_left = (due - today).days
                if days_left < 0:
                    status = _t(f"Gecikti ({-days_left} gün)")
                elif days_left == 0:
                    status = _t("Bugün")
                else:
                    status = _t(f"{days_left} gün kaldı")

                card = ftheme.apply_card_theme(MDCard(
                    orientation="vertical", padding="12dp", spacing="6dp",
                    size_hint_y=None, height="100dp", radius=[10]
                ), self.theme_cls)

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
                is_income = p.get("transaction_type") == "income"
                if not p["auto_deduct"]:
                    pay_btn = MDFlatButton(
                        text=_t("EKLE" if is_income else "ÖDE"),
                        on_release=lambda x, pp=p: self.pay_recurring_now(pp),
                    )
                    btn_layout.add_widget(pay_btn)
                else:
                    auto_lbl = MDLabel(
                        text=_t(
                            "Otomatik eklenecek"
                            if is_income else "Otomatik düşecek"
                        ),
                        font_style="Caption",
                        theme_text_color="Secondary",
                    )
                    btn_layout.add_widget(auto_lbl)
                pause_btn = MDFlatButton(text=_t("DURDUR"), on_release=lambda x, pid=p["id"]: self.deactivate_recurring(pid))
                btn_layout.add_widget(pause_btn)

                card.add_widget(header)
                card.add_widget(status_lbl)
                card.add_widget(btn_layout)
                container.add_widget(card)
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Error rendering upcoming payments")

    def pay_recurring_now(self, payment):
        from database.db import process_due_recurring_payment

        def process():
            try:
                process_due_recurring_payment(payment)
                action = (
                    "hesaba eklendi!"
                    if payment.get("transaction_type") == "income"
                    else "ödendi!"
                )
                message = f"{payment['name']} {action}"
                Clock.schedule_once(
                    lambda dt, value=message: toast(_t(value)), 0,
                )
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Error paying recurring payment")
                Clock.schedule_once(lambda dt: toast(_t("İşlem sırasında hata oluştu!")), 0)

        threading.Thread(target=process, daemon=True).start()

    def deactivate_recurring(self, payment_id):
        from database.db import deactivate_recurring_payment

        def process():
            try:
                deactivate_recurring_payment(payment_id)
                Clock.schedule_once(lambda dt: toast(_t("Tekrarlanan ödeme durduruldu.")), 0)
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
                if hasattr(self, "refresh_insights"):
                    Clock.schedule_once(lambda dt: self.refresh_insights(), 0)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Error deactivating recurring payment")

        threading.Thread(target=process, daemon=True).start()

    def process_due_auto_deductions(self):
        from database.db import (
            get_active_recurring_payments, process_due_recurring_payment,
            get_active_debts,
            DEFAULT_ACCOUNT_ID,
        )
        from services.transaction_service import TransactionService
        from services.debt_payment_service import DebtPaymentService

        def process():
            try:
                from services.account_service import AccountService
                # Hiç hesap yoksa (onboarding tamamlanmamış) yazılacak bir yer
                # de yok; denemek yalnızca "hesap bulunamadı" hatası üretirdi.
                if not AccountService.has_any_account():
                    return

                today = datetime.date.today()
                ui_needs_refresh = False

                # 0. VADESİ GELEN İLERİ TARİHLİ İŞLEMLER
                # Kullanıcının ileri tarih seçerek girdiği maaş/fatura kayıtları
                # o güne kadar bakiyeye işlenmez; vadesi gelenler burada
                # bakiyeye aktarılır. İdempotent, her açılışta güvenle çağrılır.
                try:
                    if TransactionService.settle_due_transactions():
                        ui_needs_refresh = True
                except Exception:
                    from utils.logging_config import get_logger
                    get_logger().exception("Bekleyen işlemler işlenemedi")

                # 1. MEVCUT TEKRARLANAN ÖDEMELER (Kira, Faturalar vb.)
                payments = get_active_recurring_payments()
                due_auto = [
                    p for p in payments
                    if p["auto_deduct"] and datetime.date.fromisoformat(p["next_due_date"]) <= today
                ]
                for p in due_auto:
                    # HER ÖDEME KENDİ BAŞINA KORUNUR. Eskiden bu çağrı
                    # korumasızdı ve tüm rutini saran dıştaki tek
                    # `except Exception` yakalıyordu — yani vadesi gelen
                    # ödemelerden BİRİ patlarsa (ör. tutarsız bir account_id),
                    # istisna kendisinden SONRAKİ bütün tekrarlanan ödemeleri
                    # ve aşağıdaki otomatik borç taksitlerinin TAMAMINI da
                    # atlayarak yukarı kaçıyordu. Kullanıcının kirası/faturası
                    # o açılışta sessizce hiç işlenmiyordu; tek iz, paketlenmiş
                    # derlemede (console=False) hiçbir yere gitmeyen bir
                    # print()'ti. Artık bozuk kayıt yalnızca kendini atlar.
                    try:
                        process_due_recurring_payment(p)
                        ui_needs_refresh = True
                    except Exception:
                        from utils.logging_config import get_logger
                        get_logger().exception(
                            f"Tekrarlanan ödeme işlenemedi (id={p.get('id')}), "
                            "diğerleri sürdürülüyor"
                        )
                
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
                    # `is_active` ARTIK BURADA HESAPLANMIYOR: borcun kapanıp
                    # kapanmadığına `DebtPaymentService.pay_auto` aynı
                    # transaction içinde karar veriyor. Buradaki kopya
                    # kullanılmıyordu ve servisinkinden sapabilirdi.

                    # Yukarıdaki tekrarlanan ödeme döngüsüyle AYNI gerekçe:
                    # tek bir bozuk borç kaydı, kendisinden sonraki borçların
                    # otomatik taksitlerini sessizce iptal etmemeli.
                    try:
                        DebtPaymentService.pay_auto(
                            debt['id'], DEFAULT_ACCOUNT_ID,
                            installments_to_pay, current_month_str,
                        )
                        ui_needs_refresh = True
                    except Exception:
                        from utils.logging_config import get_logger
                        get_logger().exception(
                            f"Otomatik borç taksiti işlenemedi (id={debt.get('id')}), "
                            "diğerleri sürdürülüyor"
                        )

                # 3. ORTAK UI SENKRONİZASYONU
                if ui_needs_refresh:
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                    
                    # UI üzerindeki ilerleme çubuğu (progress bar) ve kalan taksit yazısını yenile
                    if hasattr(self, 'load_active_debts'):
                        Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                        
                Clock.schedule_once(lambda dt: self.load_upcoming_recurring(), 0)
                # Bekleyen özeti bu thread bittikten SONRA okunmalı: burada
                # uzlaştırılan ileri tarihli işlemler artık bekleyen değil,
                # açılışta paralel okunsa listede hayalet kayıt görünürdü.
                if hasattr(self, "load_pending_transactions"):
                    Clock.schedule_once(
                        lambda dt: self.load_pending_transactions(), 0)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Error processing auto deductions")

        threading.Thread(target=process, daemon=True).start()
