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

        # AŞAMALI GÖSTERİM: içerik artık sabit yükseklikli değil, adaptive.
        # Abonelik alanları gizlenince kutu küçülür, açılınca büyür; diyalog
        # kendini _toggle_recurring_fields içindeki update_height ile yeniden
        # ölçer. spacing 15 -> 18: temel alanların çevresi biraz daha ferah.
        dialog_layout = MDBoxLayout(
            orientation="vertical", spacing=dp(18),
            size_hint_y=None, adaptive_height=True,
            padding=[0, dp(4), 0, dp(4)],
        )
        self.amount_input = MDTextField(hint_text="Miktar (₺)", input_filter="float", size_hint_y=None, height="48dp")

        # Segment ve butonlara açık yükseklik: adaptive konteynerde her çocuğun
        # size_hint_y=None + net height olmalı, yoksa kutu doğru ölçülmez.
        self.type_segment = MDSegmentedControl(size_hint_x=1, size_hint_y=None, height="48dp")
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gelir"))
        self.type_segment.add_widget(MDSegmentedControlItem(text="Gider"))
        self.type_segment.bind(on_active=self.on_segment_active)

        self.category_button = MDRaisedButton(text="Kategori Seç", size_hint_x=1, size_hint_y=None, height="44dp", elevation=0, on_release=self.open_category_menu)

        # Ödeme yöntemi: işlemin HANGİ hesaptan/karttan geçeceği.
        # Buradan seçilen hesabın id'si add_transaction'a gider; kredi kartı
        # seçilirse tutar aynı commit içinde karta borç olarak işlenir
        # (database/db.py::adjust_account_balance işaret konvansiyonu).
        self.selected_account_id = None
        self.account_button = MDRaisedButton(
            text="Ödeme Yöntemi", size_hint_x=1, size_hint_y=None, height="44dp", elevation=0,
            on_release=self.open_account_menu,
        )
        self._load_payment_methods()

        # Tekrarlanan ödeme mi? (Kira, Netflix, Spotify vb. her ay tekrar eden giderler)
        # Switch açılınca aşağıdaki abonelik alanları belirir.
        recurring_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        recurring_lbl = MDLabel(text="Tekrarlanan Ödeme mi?", valign="center")
        recurring_lbl.bind(size=recurring_lbl.setter('text_size'))
        self.recurring_switch = MDSwitch(size_hint_x=None, width=dp(65))
        self.recurring_switch.bind(active=self._toggle_recurring_fields)
        recurring_row.add_widget(recurring_lbl)
        recurring_row.add_widget(self.recurring_switch)

        # ── Aşamalı olarak açılan (varsayılan GİZLİ) abonelik alanları ──────────
        self.recurring_name_input = MDTextField(
            hint_text="Ödeme Adı (örn: Netflix)", size_hint_y=None, height="48dp"
        )

        self.recurring_freq_segment = MDSegmentedControl(size_hint_x=1, size_hint_y=None, height="48dp")
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text="Aylık"))
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text="Yıllık"))
        self.recurring_freq_segment.bind(on_active=self.on_recurring_freq_active)

        auto_deduct_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        auto_deduct_lbl = MDLabel(text="Vadesi Gelince Otomatik Düş", valign="center")
        auto_deduct_lbl.bind(size=auto_deduct_lbl.setter('text_size'))
        self.auto_deduct_switch = MDSwitch(size_hint_x=None, width=dp(65))
        auto_deduct_row.add_widget(auto_deduct_lbl)
        auto_deduct_row.add_widget(self.auto_deduct_switch)

        # Abonelik alanları TEK bir wrapper'da toplanır. Gizleme = wrapper'ı
        # ağaçtan çıkarmak. Neden height=0 DEĞİL: MDTextField ve
        # MDSegmentedControl kendi yüksekliklerini içeriden hesaplayıp dışarıdan
        # verilen height=0'ı EZİYOR (account_mixin'de de belgelenen davranış),
        # o yüzden gizli kalmıyorlardı. Ağaçtan çıkarınca kesin gizlenir ve
        # adaptive_height konteyner kendini küçültür.
        self._recurring_box = MDBoxLayout(
            orientation="vertical", size_hint_y=None, adaptive_height=True, spacing=dp(18),
        )
        self._recurring_box.add_widget(self.recurring_name_input)
        self._recurring_box.add_widget(self.recurring_freq_segment)
        self._recurring_box.add_widget(auto_deduct_row)
        self._recurring_visible = False

        dialog_layout.add_widget(self.amount_input)
        dialog_layout.add_widget(self.type_segment)
        dialog_layout.add_widget(self.category_button)
        dialog_layout.add_widget(self.account_button)
        dialog_layout.add_widget(recurring_row)
        # _recurring_box başta EKLENMEZ: ilk görünüm sade kalsın.

        self.dialog = MDDialog(
            title="Yeni Bir İşlem Ekle",
            type="custom",
            content_cls=dialog_layout,
            buttons=[MDRaisedButton(text="KAYDET", on_release=self.save_transaction)]
        )
        self.dialog.open()

    # ─── Aşamalı gösterim (progressive disclosure) ───────────────────────────

    def _toggle_recurring_fields(self, switch, active):
        """"Tekrarlanan Ödeme mi?" switch'iyle abonelik alanlarını aç/kapat.

        Açınca wrapper temel alanların (recurring_row) hemen ardına eklenir,
        kapanınca çıkarılır. adaptive_height konteyner büyüyüp küçülür; diyalog
        bir sonraki karede (layout oturunca) update_height ile yeniden ölçülür.
        """
        if active == self._recurring_visible:
            return
        layout = self.dialog.content_cls
        if active:
            # recurring_row'dan (en alttaki temel alan) hemen sonraya ekle.
            layout.add_widget(self._recurring_box)
        else:
            if self._recurring_box.parent is not None:
                layout.remove_widget(self._recurring_box)
        self._recurring_visible = active

        def _reflow(dt):
            try:
                self.dialog.update_height()
                self.dialog.height = self.dialog.ids.container.height
            except Exception:
                pass
        Clock.schedule_once(_reflow, 0)

    def on_recurring_freq_active(self, segmented_control, segmented_item):
        """Tekrarlanan ödeme sıklığı seçimini (Aylık/Yıllık) günceller."""
        self.selected_frequency = "yearly" if segmented_item.text == "Yıllık" else "monthly"

    def on_segment_active(self, segmented_control, segmented_item):
        """Gelir/Gider seçimi değişince türü günceller ve kategori seçimini sıfırlar
        (kategoriler türe bağlı olduğu için eski seçim geçersiz kalır).

        Ödeme yöntemi seçimine DOKUNULMAZ: kredi kartları artık her iki türde de
        seçilebilir (bkz. open_account_menu), o yüzden türe göre kart düşürme
        mantığı kaldırıldı — kullanıcının seçtiği kart olduğu gibi korunur."""
        self.selected_type = "expense" if segmented_item.text == "Gider" else "income"
        self.selected_category = "Kategori Seç"
        self.category_button.text = "Kategori Seç"

    # ─── Ödeme yöntemi (hesap / kart seçimi) ─────────────────────────────────

    def _load_payment_methods(self):
        """Kayıtlı hesapları/kartları okur ve varsayılan seçimi kurar.

        Varsayılan olarak ilk vadesiz hesap seçilir; hiç yoksa listedeki ilk
        kayıt. Böylece kullanıcı seçim yapmasa da işlem eskisi gibi çalışır —
        fark, artık sabit DEFAULT_ACCOUNT_ID yerine gerçek bir hesap olması.
        """
        try:
            from services.account_service import AccountService, CREDIT_CARD
            self._payment_methods = AccountService.get_accounts()
        except Exception as e:
            print("Ödeme yöntemleri okunamadı:", e)
            self._payment_methods = []

        if not self._payment_methods:
            self.selected_account_id = None
            self.account_button.text = "Ödeme Yöntemi (hesap yok)"
            self.account_button.disabled = True
            return

        default = next(
            (a for a in self._payment_methods if a["account_type"] != "credit_card"),
            self._payment_methods[0],
        )
        self._set_payment_method(default, close_menu=False)

    def _payment_label(self, acc):
        """Menüde ve butonda görünen etiket: ad + tür (+ kart varsa son 4 hane)."""
        label = f"{acc['name']} · {acc['type_label']}"
        if acc.get("has_card_number") and acc.get("masked_number"):
            label += f" ({acc['masked_number'][-4:]})"
        return label

    def open_account_menu(self, *args):
        """Ödeme yöntemini seçtiren menüyü açar.

        TÜM hesaplar VE kredi kartları her zaman listelenir. Önceden kredi
        kartları "gelir" seçiliyken eleniyordu; bu, kartların görünürlüğünü
        MDSegmentedControl'ün o anki durumuna bağlıyordu ve kullanıcı gider
        eklerken kartını bulamıyordu. İşaret konvansiyonu (bkz.
        adjust_account_balance) her iki yönü de doğru işliyor:
          * gider  -> kart bakiyesi daha negatife gider (borç ARTAR),
          * gelir  -> kart bakiyesi 0'a yaklaşır (borç ÖDENİR).
        İkisi de geçerli işlemler; kartı kullanıcı bilinçli seçiyor.
        """
        methods = self._payment_methods
        if not methods:
            toast("Uygun bir hesap bulunamadı.")
            return

        items = [{
            "text": self._payment_label(a),
            "viewclass": "OneLineListItem",
            "on_release": (lambda x=a: self._set_payment_method(x)),
        } for a in methods]
        self.account_menu = MDDropdownMenu(caller=self.account_button, items=items, width_mult=5)
        self.account_menu.open()

    def _set_payment_method(self, acc, close_menu=True):
        self.selected_account_id = acc["id"]
        self.account_button.text = self._payment_label(acc)
        if close_menu and getattr(self, "account_menu", None):
            self.account_menu.dismiss()

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
            # Kartlarım listesini tazele: seçilen karta yazılan borç ve o kartın
            # "Son Hareketler" listesi anında güncellensin.
            if hasattr(self, "render_accounts"):
                try:
                    self.render_accounts()
                except Exception as e:
                    print("Kart listesi tazelenemedi:", e)
            toast("İşlem başarıyla eklendi!")

        # Kredi kartı limit aşımı gibi kullanıcıya anlamlı gelen hatalarda genel
        # "bir hata oluştu" yerine gerçek sebebi göstermek için mesaj taşınır.
        error_message = {"text": "İşlem kaydedilirken bir hata oluştu!"}

        def error_callback(dt):
            toast(error_message["text"])

        def background_task():
            try:
                from database.db import DEFAULT_ACCOUNT_ID
                # Kullanıcının seçtiği hesap/kart; seçim yoksa eski davranış.
                account_id = self.selected_account_id or DEFAULT_ACCOUNT_ID
                TransactionService.add_transaction(
                    account_id=account_id,
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
            except ValueError as e:
                # add_transaction doğrulama hatalarını (limit aşımı) ValueError
                # olarak fırlatır; metni doğrudan kullanıcıya gösterilebilir.
                error_message["text"] = str(e)
                Clock.schedule_once(error_callback, 0)
            except Exception as e:
                print(f"Save Transaction Error: {e}")
                Clock.schedule_once(error_callback, 0)

        threading.Thread(target=background_task, daemon=True).start()

    def load_recent_transactions(self, list_filter=None):
        self.refresh_dashboard_data(list_filter)

