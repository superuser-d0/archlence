from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
from services.transaction_service import TransactionService
from services.category_service import CategoryService


class TransactionMixin:
    def show_add_dialog(self):
        self.selected_type = "income"
        self.selected_category = "Kategori Seç"
        
        dialog_layout = MDBoxLayout(orientation="vertical", spacing="15dp", size_hint_y=None, height="180dp")
        self.amount_input = MDTextField(hint_text="Miktar (₺)", input_filter="float", size_hint_y=None, height="48dp")
        
        self.type_segment = MDSegmentedControl(size_hint_x=1)
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gelir"))
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gider"))
        self.type_segment.bind(on_active=self.on_segment_active)

        self.category_button = MDRaisedButton(text="Kategori Seç", size_hint_x=1, elevation=0, on_release=self.open_category_menu)

        dialog_layout.add_widget(self.amount_input)
        dialog_layout.add_widget(self.type_segment)
        dialog_layout.add_widget(self.category_button)

        self.dialog = MDDialog(
            title="Yeni Bir İşlem Ekle",
            type="custom",
            content_cls=dialog_layout,
            buttons=[MDRaisedButton(text="KAYDET", on_release=self.save_transaction)]
        )    
        self.dialog.open()

    def on_segment_active(self, segmented_control, segmented_item):
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

        toast("İşlem şifreleniyor...")

        import threading
        from kivy.clock import Clock

        def success_callback(dt):
            self.dialog.dismiss()
            self.refresh_dashboard_data()
            self.generate_financial_advice()
            toast("İşlem başarıyla eklendi!")

        def error_callback(dt):
            toast("İşlem kaydedilirken bir hata oluştu!")

        def background_task():
            try:
                TransactionService.add_transaction(
                    account_id=1,
                    amount=user_amount,
                    transaction_type=self.selected_type,
                    category=self.selected_category,
                    description=self.selected_category 
                )
                Clock.schedule_once(success_callback, 0)
            except Exception as e:
                print(f"Save Transaction Error: {e}")
                Clock.schedule_once(error_callback, 0)

        threading.Thread(target=background_task, daemon=True).start()

    def load_recent_transactions(self, list_filter=None):
        self.refresh_dashboard_data(list_filter)

