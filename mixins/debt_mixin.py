from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.button import MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
import threading
from kivymd.uix.card import MDCard
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.slider import MDSlider
import ui.theme as ftheme
from ui.components import is_read_only_asset_account
from ui.i18n import tr as _t
from utils.formatters import attach_amount_mask, read_amount, set_amount

class DebtMixin:
    """Borç/kredi takibi: hesaplanan krediyi borç olarak kaydetme, aktif borç
    kartlarını listeleme, taksit ödeme ve borcu tamamen kapatma akışları.

    Taksit ödemeleri aynı zamanda "expense" tipinde bir işlem kaydı üretir; böylece
    borç ödemeleri bakiye ve grafiklere de yansır. DB erişimleri thread'de yapılır.
    """

    def add_loan_to_debts(self, *args):
        """CalculatorMixin'in son kredi hesabını (last_calculated_loan) borç olarak kaydeder."""
        if not hasattr(self, 'last_calculated_loan'):
            toast(_t("Önce hesaplama yapın!"))
            return
            
        from database.db import insert_debt

        def save_debt():
            try:
                loan = self.last_calculated_loan
                insert_debt(
                    loan["name"],
                    loan["total_amount"],
                    loan["monthly_payment"],
                    loan["total_installments"]
                )
                Clock.schedule_once(lambda dt: toast(_t("Borç başarıyla eklendi!")), 0)
                Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                Clock.schedule_once(lambda dt: self.loan_dialog.dismiss(), 0)
            except Exception as e:
                print("Error adding debt:", e)
                Clock.schedule_once(lambda dt: toast(_t("Borç eklenirken hata oluştu!")), 0)
                
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
                lbl = MDLabel(text=_t("Henüz aktif bir borcunuz bulunmuyor."), theme_text_color="Secondary", font_style="Body2", halign="center")
                container.add_widget(lbl)
                return

            for debt in debts:

                card = ftheme.apply_card_theme(
                    MDCard(orientation="vertical", padding="12dp", spacing="8dp",
                           size_hint_y=None, height="140dp", radius=[10]),
                    self.theme_cls)
                
                header = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="24dp")
                name_lbl = MDLabel(text=f"{debt['debt_name']}", font_style="Subtitle2", bold=True)
                amount_lbl = MDLabel(text=_t(f"Aylık: {debt['monthly_payment']:,.2f} ₺"), font_style="Caption", theme_text_color="Secondary", halign="right")
                auto_pay_btn = MDIconButton(
                    icon="calendar-sync" if debt.get("is_auto_pay") else "calendar-sync-outline",
                    theme_text_color="Custom",
                    text_color=ftheme.accent(
                        self.theme_cls, "green" if debt.get("is_auto_pay") else "muted"
                    ),
                    icon_size="18dp",
                    size_hint_x=None,
                    width="24dp",
                    pos_hint={"center_y": .5},
                    on_release=lambda x, d=debt: self.show_auto_pay_dialog(d),
                )
                header.add_widget(name_lbl)
                header.add_widget(amount_lbl)
                header.add_widget(auto_pay_btn)

                progress = MDProgressBar(value=debt["paid_installments"], max=debt["total_installments"], size_hint_y=None, height="8dp")

                status_text = _t(f"Kalan: {debt['total_installments'] - debt['paid_installments']}/{debt['total_installments']} Taksit")
                if debt.get("is_auto_pay"):
                    status_text += _t(f"   •  Ayın {debt.get('auto_pay_day', 1)}. günü otomatik ödenecek")
                status_lbl = MDLabel(
                    text=status_text, font_style="Caption",
                    theme_text_color="Custom",
                    text_color=ftheme.accent(
                        self.theme_cls, "green" if debt.get("is_auto_pay") else "muted"
                    ),
                )

                btn_layout = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="36dp")
                pay_btn = ftheme.secondary_button(
                    _t("Taksit Öde"), self.theme_cls,
                    on_release=lambda x, d=debt: self.pay_debt_installments(d),
                )
                close_btn = ftheme.danger_button(
                    _t("Tamamen Kapat"), self.theme_cls,
                    on_release=lambda x, d=debt: self.close_debt_completely(d),
                )
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
            from database.db import update_debt_progress, DEFAULT_ACCOUNT_ID
            from services.transaction_service import TransactionService

            def process():
                try:
                    update_debt_progress(debt['id'], remaining_installments, is_active=0)
                    TransactionService.add_transaction(
                        account_id=DEFAULT_ACCOUNT_ID,
                        amount=remaining_balance,
                        transaction_type="expense",
                        category="Borç Ödeme",
                        description=f"{debt['debt_name']} (Tamamen Kapatma)"
                    )
                    Clock.schedule_once(lambda dt: toast(_t("Borç tamamen kapatıldı!")), 0)
                    Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                except Exception as e:
                    print("Error closing debt:", e)
                    Clock.schedule_once(lambda dt: toast(_t("İşlem sırasında hata oluştu!")), 0)

            threading.Thread(target=process, daemon=True).start()

        self.dialog = MDDialog(
            title=_t("Borcu Kapat"),
            text=_t(f"Kalan {remaining_balance:,.2f} ₺ bakiyeyi kapatmak istediğinize emin misiniz?"),
            buttons=[
                ftheme.secondary_button(_t("İPTAL"), self.theme_cls, on_release=lambda x: self.dialog.dismiss()),
                ftheme.danger_button(_t("EVET, KAPAT"), self.theme_cls, on_release=confirm),
            ]
        )
        self.dialog.open()

    def pay_debt_installments(self, debt):
        """Slider ile seçilen sayıda taksiti öder; son taksit ödeniyorsa borcu
        pasife çeker. Ödeme "Kredi Taksiti" kategorisinde gider olarak kaydedilir."""

        remaining_installments = debt['total_installments'] - debt['paid_installments']
        if remaining_installments <= 0:
            toast(_t("Bu borç zaten tamamen ödenmiş!"))
            return

        content = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="120dp")
        lbl = MDLabel(text=_t(f"Kaç taksit ödemek istiyorsunuz? (Maks: {remaining_installments})"), theme_text_color="Secondary")
        slider = MDSlider(min=1, max=remaining_installments, value=1, step=1)
        val_lbl = MDLabel(text=_t("Seçilen: 1 Taksit"), halign="center", bold=True)

        def on_slider_value(instance, value):
            val_lbl.text = _t(f"Seçilen: {int(value)} Taksit")
            
        slider.bind(value=on_slider_value)

        content.add_widget(lbl)
        content.add_widget(slider)
        content.add_widget(val_lbl)

        def confirm(*args):
            self.dialog.dismiss()
            selected_installments = int(slider.value)
            amount_to_pay = selected_installments * debt['monthly_payment']
            is_active = 0 if selected_installments == remaining_installments else 1

            from database.db import update_debt_progress, DEFAULT_ACCOUNT_ID
            from services.transaction_service import TransactionService

            def process():
                try:
                    update_debt_progress(debt['id'], selected_installments, is_active=is_active)
                    TransactionService.add_transaction(
                        account_id=DEFAULT_ACCOUNT_ID,
                        amount=amount_to_pay,
                        transaction_type="expense",
                        category="Kredi Taksiti",
                        description=f"{debt['debt_name']} ({selected_installments} Taksit Ödemesi)"
                    )
                    Clock.schedule_once(lambda dt: toast(_t(f"{selected_installments} taksit başarıyla ödendi!")), 0)
                    Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                    Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                    Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
                except Exception as e:
                    print("Error paying installment:", e)
                    Clock.schedule_once(lambda dt: toast(_t("İşlem sırasında hata oluştu!")), 0)

            threading.Thread(target=process, daemon=True).start()

        self.dialog = MDDialog(
            title=_t("Taksit Öde"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(_t("İPTAL"), self.theme_cls, on_release=lambda x: self.dialog.dismiss()),
                ftheme.primary_button(_t("ÖDE"), self.theme_cls, on_release=confirm),
            ]
        )
        self.dialog.open()

    def show_auto_pay_dialog(self, debt):
        """Borç kartındaki takvim ikonuna basılınca açılır: otomatik ödemeyi
        açıp/kapatma ve ödeme gününü (1-31) belirleme diyaloğu. Kaydedilince
        active_debts.is_auto_pay / auto_pay_day sütunlarını günceller."""
        from kivymd.uix.selectioncontrol import MDSwitch

        content = MDBoxLayout(orientation="vertical", spacing="14dp", size_hint_y=None, height="110dp")

        switch_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="40dp")
        switch_lbl = MDLabel(text=_t("Otomatik Ödeme"), theme_text_color="Secondary")
        auto_switch = MDSwitch(active=bool(debt.get("is_auto_pay")))
        switch_row.add_widget(switch_lbl)
        switch_row.add_widget(auto_switch)

        day_input = ftheme.make_text_field(
            _t("Ödeme Günü (1-31)"), self.theme_cls,
            filter="int",
            text=str(debt.get("auto_pay_day", 1)),
        )

        content.add_widget(switch_row)
        content.add_widget(day_input)

        def confirm(*args):
            self.auto_pay_dialog.dismiss()
            day_text = day_input.text.strip()
            auto_pay_day = int(day_text) if day_text.isdigit() and 1 <= int(day_text) <= 31 else 1
            is_auto_pay = auto_switch.active

            from database.db import update_debt_auto_pay

            def process():
                try:
                    update_debt_auto_pay(debt["id"], is_auto_pay, auto_pay_day)
                    Clock.schedule_once(lambda dt: toast(_t("Otomatik ödeme ayarları güncellendi!")), 0)
                    Clock.schedule_once(lambda dt: self.load_active_debts(), 0)
                except Exception as e:
                    print("Error updating auto-pay settings:", e)
                    Clock.schedule_once(lambda dt: toast(_t("Güncellenirken hata oluştu!")), 0)

            threading.Thread(target=process, daemon=True).start()

        self.auto_pay_dialog = MDDialog(
            title=_t(f"{debt['debt_name']} — Otomatik Ödeme"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(_t("İPTAL"), self.theme_cls, on_release=lambda x: self.auto_pay_dialog.dismiss()),
                ftheme.primary_button(_t("KAYDET"), self.theme_cls, on_release=confirm),
            ],
        )
        self.auto_pay_dialog.open()

    def open_pay_debt_dialog(self, credit_card_id):
        from services.account_service import AccountService, CHECKING
        import threading
        from kivymd.uix.menu import MDDropdownMenu

        card = AccountService.get_account(credit_card_id)
        if not card:
            toast(_t("Kredi kartı bulunamadı."))
            return

        accounts = AccountService.get_accounts()
        # Salt okunur 'Aktif Varlıklarım' kartı vadesiz gibi görünse de borç
        # ödeme kaynağı OLAMAZ; harcama izolasyonu bu pencerede de geçerli.
        checking_accounts = [
            acc for acc in accounts
            if acc["account_type"] == CHECKING and not is_read_only_asset_account(acc)
        ]

        if not checking_accounts:
            toast(_t("Ödeme yapabileceğiniz vadesiz/nakit hesabınız bulunmamaktadır."))
            return

        content = MDBoxLayout(orientation="vertical", spacing="14dp", size_hint_y=None, height="120dp")

        # Maskeleme kendi input_filter'ını kurar; mevcut borç set_amount ile
        # yazılır çünkü ham "3500.0" metni maskede "35.000" olurdu.
        amount_input = attach_amount_mask(ftheme.make_text_field(
            _t("Ödenecek Tutar (₺)"), self.theme_cls,
        ))
        if card["debt"] > 0:
            set_amount(amount_input, card["debt"])
        content.add_widget(amount_input)

        selected_account_id = checking_accounts[0]["id"]
        account_btn = ftheme.primary_button(
            _t(f"{checking_accounts[0]['name']} (Bakiye: {checking_accounts[0]['balance']:,.2f} ₺)"),
            self.theme_cls,
            size_hint_x=1
        )
        content.add_widget(account_btn)

        self.pay_debt_menu = MDDropdownMenu(
            caller=account_btn,
            width_mult=4,
        )

        def set_selected_account(acc):
            nonlocal selected_account_id
            selected_account_id = acc["id"]
            account_btn.text = _t(f"{acc['name']} (Bakiye: {acc['balance']:,.2f} ₺)")
            self.pay_debt_menu.dismiss()

        def open_menu(*args):
            accounts_now = AccountService.get_accounts()
            checking_now = [
                a for a in accounts_now
                if a["account_type"] == CHECKING and not is_read_only_asset_account(a)
            ]
            
            # Ana buton metnini güncel veriyle zorla güncelle (stale state koruması)
            for acc in checking_now:
                if acc["id"] == selected_account_id:
                    account_btn.text = _t(f"{acc['name']} (Bakiye: {acc['balance']:,.2f} ₺)")
                    break
            
            menu_items = []
            for acc in checking_now:
                menu_items.append({
                    "text": _t(f"{acc['name']} (Bakiye: {acc['balance']:,.2f} ₺)"),
                    "viewclass": "OneLineListItem",
                    "on_release": lambda x=acc: set_selected_account(x),
                })
            self.pay_debt_menu.items = menu_items
            self.pay_debt_menu.open()

        account_btn.on_release = open_menu

        def confirm(*args):
            if not amount_input.text.strip():
                toast(_t("Lütfen tutar giriniz."))
                return
            try:
                # read_amount kanonik değeri okur; maskelenmiş "3.500" metnini
                # float() 3.5 diye okurdu.
                amount = read_amount(amount_input)
            except (ValueError, TypeError):
                toast(_t("Geçersiz tutar."))
                return

            if amount <= 0:
                toast(_t("Tutar 0'dan büyük olmalıdır."))
                return

            def process():
                try:
                    AccountService.pay_credit_card_debt(credit_card_id, selected_account_id, amount)
                    Clock.schedule_once(lambda dt: toast(_t("Borç başarıyla ödendi!")), 0)
                    Clock.schedule_once(lambda dt: self.pay_debt_dialog.dismiss(), 0)
                    
                    # Kart bilgilerini tazele. `render_accounts` tek başına
                    # yeterli: `pay_credit_card_debt` -> `record_balance_event`
                    # RAM snapshot'ını bayat işaretler, `render_accounts` da
                    # okumadan önce `ensure_account_cache_fresh()` ile tazeler.
                    #
                    # Burada eskiden ek olarak kart ELLE yamanıyordu
                    # (AccountService.get_account ile taze okuyup
                    # debt_ratio/available_limit/current_debt alanlarını tek tek
                    # set ederek). O kod, snapshot'ın bayat kalması yüzünden
                    # `render_accounts`'ın eski bakiyeyi geri çizmesine karşı bir
                    # ÇÖZÜM DEĞİL SEMPTOM YAMASIYDI; kök neden giderildiği için
                    # kaldırıldı. Yaptığı iş zaten
                    # `_render_account_widget`'ın kredi kartı dalının birebir
                    # alt kümesiydi (aynı oran formülü, aynı ₺ biçimleyici).
                    #
                    # Zamanlama da bozulmuyor: `render_accounts` içindeki
                    # gecikmeli `add_next` döngüsü yalnızca YENİ widget'lar için;
                    # hâlihazırda ekranda olan kart aynı karede senkron güncellenir.
                    Clock.schedule_once(lambda dt: self.render_accounts(), 0)
                except Exception as e:
                    print("Error paying credit card debt:", e)
                    error_msg = str(e)
                    Clock.schedule_once(lambda dt: toast(_t(f"Hata: {_t(error_msg)}")), 0)

            threading.Thread(target=process, daemon=True).start()

        self.pay_debt_dialog = MDDialog(
            title=_t(f"{card['name']} Borç Ödeme"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    _t("İPTAL"), self.theme_cls,
                    on_release=lambda x: self.pay_debt_dialog.dismiss(),
                ),
                ftheme.primary_button(_t("ÖDE"), self.theme_cls, on_release=confirm),
            ]
        )
        self.pay_debt_dialog.open()
