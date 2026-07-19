from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
from services.transaction_service import TransactionService
from services.queries import CategoryService


class TransactionMixin:
    """Gelir/gider işlemi ekleme akışı: dialog, kategori seçimi ve kayıt.

    FinoraApp'e karışan (mixin) sınıf; self.dialog, self.selected_type gibi
    durumları app örneği üzerinde tutar. Kayıt işlemi şifreleme içerdiği için
    arka plan thread'inde yapılır, UI güncellemeleri Clock ile ana thread'e döner.
    """

    def show_add_dialog(self):
        """"Yeni İşlem" dialogunu açar: miktar alanı, gelir/gider seçici, kategori,
        ve isteğe bağlı "tekrarlanan ödeme" alanları (isim, sıklık, otomatik düş)."""
        from kivymd.uix.selectioncontrol import MDSwitch

        self.selected_type = "income"
        self.selected_category = "Kategori Seç"
        self.selected_frequency = "monthly"

        dialog_layout = MDBoxLayout(orientation="vertical", spacing="15dp", size_hint_y=None, height="430dp")
        self.amount_input = MDTextField(hint_text="Miktar (₺)", input_filter="float", size_hint_y=None, height="48dp")

        self.type_segment = MDSegmentedControl(size_hint_x=1)
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gelir"))
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gider"))
        self.type_segment.bind(on_active=self.on_segment_active)

        self.category_button = MDRaisedButton(text="Kategori Seç", size_hint_x=1, elevation=0, on_release=self.open_category_menu)

        # Tekrarlanan ödeme mi? (Kira, Netflix, Spotify vb. her ay tekrar eden giderler)
        recurring_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        recurring_lbl = MDLabel(text="Tekrarlanan Ödeme mi?", valign="center")
        recurring_lbl.bind(size=recurring_lbl.setter('text_size'))
        self.recurring_switch = MDSwitch(size_hint_x=None, width=dp(65))
        recurring_row.add_widget(recurring_lbl)
        recurring_row.add_widget(self.recurring_switch)

        self.recurring_name_input = MDTextField(
            hint_text="Ödeme Adı (örn: Netflix)", size_hint_y=None, height="48dp"
        )

        self.recurring_freq_segment = MDSegmentedControl(size_hint_x=1)
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text="Aylık"))
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text="Yıllık"))
        self.recurring_freq_segment.bind(on_active=self.on_recurring_freq_active)

        auto_deduct_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        auto_deduct_lbl = MDLabel(text="Vadesi Gelince Otomatik Düş", valign="center")
        auto_deduct_lbl.bind(size=auto_deduct_lbl.setter('text_size'))
        self.auto_deduct_switch = MDSwitch(size_hint_x=None, width=dp(65))
        auto_deduct_row.add_widget(auto_deduct_lbl)
        auto_deduct_row.add_widget(self.auto_deduct_switch)

        dialog_layout.add_widget(self.amount_input)
        dialog_layout.add_widget(self.type_segment)
        dialog_layout.add_widget(self.category_button)
        dialog_layout.add_widget(recurring_row)
        dialog_layout.add_widget(self.recurring_name_input)
        dialog_layout.add_widget(self.recurring_freq_segment)
        dialog_layout.add_widget(auto_deduct_row)

        self.dialog = MDDialog(
            title="Yeni Bir İşlem Ekle",
            type="custom",
            content_cls=dialog_layout,
            buttons=[MDRaisedButton(text="KAYDET", on_release=self.save_transaction)]
        )
        self.dialog.open()

    def on_recurring_freq_active(self, segmented_control, segmented_item):
        """Tekrarlanan ödeme sıklığı seçimini (Aylık/Yıllık) günceller."""
        self.selected_frequency = "yearly" if segmented_item.text == "Yıllık" else "monthly"

    def on_segment_active(self, segmented_control, segmented_item):
        """Gelir/Gider seçimi değişince türü günceller ve kategori seçimini sıfırlar
        (kategoriler türe bağlı olduğu için eski seçim geçersiz kalır)."""
        self.selected_type = "expense" if segmented_item.text == "Gider" else "income"
        self.selected_category = "Kategori Seç"
        self.category_button.text = "Kategori Seç"

    def open_category_menu(self, *args):
        categories = CategoryService.get_categories(self.selected_type)
        menu_items = [{"text": str(cat[1]), "viewclass": "OneLineListItem", "on_release": lambda x=str(cat[1]): self.set_category(x)} for cat in categories]
        self.category_menu = MDDropdownMenu(caller=self.category_button, items=menu_items, width_mult=4)
        self.category_menu.open()

    def set_category(self, text_item):
        self.category_button.text = text_item
        self.selected_category = text_item
        self.category_menu.dismiss()

    def save_transaction(self, *args):
        """Girilen işlemi doğrular ve arka planda şifreleyip veritabanına yazar.

        Doğrulama (kategori seçili mi, miktar geçerli ve pozitif mi) ana thread'de;
        AES şifreleme + DB yazma ayrı thread'de yapılır ki dialog donmasın.
        """
        if self.selected_category == "Kategori Seç":
            toast("Lütfen bir kategori seçin!") 
            return 
            
        try:
            user_amount = float(self.amount_input.text)
            if user_amount <= 0:
                toast("Miktar 0'dan büyük olmalıdır!")
                return
        except ValueError:
            toast("Lütfen geçerli bir sayı girin!")
            return

        is_recurring = self.recurring_switch.active
        recurring_name = self.recurring_name_input.text.strip() or self.selected_category
        recurring_frequency = self.selected_frequency
        recurring_auto_deduct = self.auto_deduct_switch.active

        if is_recurring and self.selected_type == "expense":
            # Abonelik Duplikasyonu koruması: aynı isimle (harf duyarsız)
            # ikinci kez aktif bir abonelik eklenmesin.
            from database.db import has_active_recurring_payment
            if has_active_recurring_payment(recurring_name):
                toast("Bu isimde aktif bir aboneliğiniz zaten var!")
                return

        toast("İşlem şifreleniyor...")

        import threading
        import datetime
        from kivy.clock import Clock

        def success_callback(dt):
            self.dialog.dismiss()
            self.refresh_dashboard_data()
            self.generate_financial_advice()
            if is_recurring and hasattr(self, "load_upcoming_recurring"):
                self.load_upcoming_recurring()
            toast("İşlem başarıyla eklendi!")

        def error_callback(dt):
            toast("İşlem kaydedilirken bir hata oluştu!")

        def background_task():
            try:
                from database.db import DEFAULT_ACCOUNT_ID
                TransactionService.add_transaction(
                    account_id=DEFAULT_ACCOUNT_ID,
                    amount=user_amount,
                    transaction_type=self.selected_type,
                    category=self.selected_category,
                    description=self.selected_category
                )
                if is_recurring and self.selected_type == "expense":
                    from database.db import insert_recurring_payment, _advance_due_date
                    next_due = _advance_due_date(datetime.date.today().isoformat(), recurring_frequency)
                    insert_recurring_payment(
                        recurring_name, user_amount, self.selected_category,
                        recurring_frequency, next_due, recurring_auto_deduct
                    )
                Clock.schedule_once(success_callback, 0)
            except Exception as e:
                print(f"Save Transaction Error: {e}")
                Clock.schedule_once(error_callback, 0)

        threading.Thread(target=background_task, daemon=True).start()

    def load_recent_transactions(self, list_filter=None):
        self.refresh_dashboard_data(list_filter)

