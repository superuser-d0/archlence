from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
from services.transaction_service import TransactionService
from services.queries import CategoryService
import ui.theme as ftheme
from ui.components import is_read_only_asset_account, MiniCardPreviewWidget
from ui.i18n import tr as _t


def _fmt(value):
    """Tutarı Türkçe biçimde (₺1.234,56) yazar — account_mixin._fmt ile aynı."""
    try:
        return f"₺{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "₺0,00"


class TransactionMixin:
    """Gelir/gider işlemi ekleme akışı: dialog, kategori seçimi ve kayıt.

    ArchlenceApp'e karışan (mixin) sınıf; self.dialog, self.selected_type gibi
    durumları app örneği üzerinde tutar. Kayıt işlemi şifreleme içerdiği için
    arka plan thread'inde yapılır, UI güncellemeleri Clock ile ana thread'e döner.
    """

    def show_add_dialog(self):
        """"Yeni İşlem" dialogunu açar: miktar alanı, gelir/gider seçici, kategori,
        ve isteğe bağlı "tekrarlanan ödeme" alanları (isim, sıklık, otomatik düş)."""
        from kivymd.uix.selectioncontrol import MDSwitch

        self.selected_type = "income"
        self.selected_category = _t("Kategori Seç")
        self.selected_frequency = "monthly"

        # AŞAMALI GÖSTERİM: içerik artık sabit yükseklikli değil, adaptive.
        # Abonelik alanları gizlenince kutu küçülür, açılınca büyür; diyalog
        # kendini _toggle_recurring_fields içindeki update_height ile yeniden
        # ölçer. spacing 15 -> 18: temel alanların çevresi biraz daha ferah.
        dialog_layout = MDBoxLayout(
            orientation="vertical", spacing=dp(18),
            size_hint_y=None, adaptive_height=True,
            padding=[dp(16), dp(4), dp(16), dp(4)],
        )
        self.amount_input = ftheme.make_text_field(
            _t("Miktar (₺)"), self.theme_cls, filter="float",
            size_hint_y=None, height=dp(48),
        )

        # Segment ve butonlara açık yükseklik: adaptive konteynerde her çocuğun
        # size_hint_y=None + net height olmalı, yoksa kutu doğru ölçülmez.
        self.type_segment = MDSegmentedControl(size_hint_x=1, size_hint_y=None, height="48dp")
        self.type_segment.add_widget(MDSegmentedControlItem(text=_t("Gelir")))
        self.type_segment.add_widget(MDSegmentedControlItem(text=_t("Gider")))
        self.type_segment.bind(on_active=self.on_segment_active)

        self.category_button = ftheme.primary_button(
            _t("Kategori Seç"), self.theme_cls, size_hint_x=1,
            size_hint_y=None, height=dp(44), on_release=self.open_category_menu,
        )

        # Ödeme yöntemi: işlemin HANGİ hesaptan/karttan geçeceği.
        # Buradan seçilen hesabın id'si add_transaction'a gider; kredi kartı
        # seçilirse tutar aynı commit içinde karta borç olarak işlenir
        # (database/db.py::adjust_account_balance işaret konvansiyonu).
        self.selected_account_id = None
        self.account_button = ftheme.primary_button(
            _t("Ödeme Yöntemi"), self.theme_cls,
            size_hint_x=1, size_hint_y=None, height=dp(44),
            on_release=self.open_account_menu,
        )
        self._load_payment_methods()

        # Ödeme yöntemi butonunun HEMEN ALTINDAKİ dinamik alan: mini kart
        # önizlemesi + (Gider+kredi kartında) taksit bloğu bu kutuda yaşar.
        # Sabit bir konteyner kullanmak, dialog_layout'ta kırılgan index
        # hesabı yapmadan ekleme/çıkarma sırasını garanti eder.
        self._below_payment_box = MDBoxLayout(
            orientation="vertical", size_hint_y=None, adaptive_height=True, spacing=dp(12),
        )
        self._mini_card_preview = MiniCardPreviewWidget()
        self._below_payment_box.add_widget(self._mini_card_preview)

        # Tekrarlanan ödeme mi? (Kira, Netflix, Spotify vb. her ay tekrar eden giderler)
        # Switch açılınca aşağıdaki abonelik alanları belirir.
        recurring_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        # Taksitli mod ile karşılıklı dışlama için self üzerinde tutulur.
        self._recurring_row = recurring_row
        recurring_lbl = MDLabel(text=_t("Tekrarlanan Ödeme mi?"), valign="center")
        recurring_lbl.bind(size=recurring_lbl.setter('text_size'))
        self.recurring_switch = MDSwitch(size_hint_x=None, width=dp(65))
        self.recurring_switch.bind(active=self._toggle_recurring_fields)
        recurring_row.add_widget(recurring_lbl)
        recurring_row.add_widget(self.recurring_switch)

        # ── Aşamalı olarak açılan (varsayılan GİZLİ) abonelik alanları ──────────
        self.recurring_name_input = ftheme.make_text_field(
            _t("Ödeme Adı (örn: Netflix)"), self.theme_cls,
            size_hint_y=None, height=dp(48),
        )
        import datetime
        self.recurrence_day_input = ftheme.make_text_field(
            _t("Her Ayın Hangi Günü Ödenecek? (1-31)"),
            self.theme_cls,
            filter="int",
            size_hint_y=None,
            height=dp(48),
        )
        self.recurrence_day_input.text = str(datetime.date.today().day)

        self.recurring_freq_segment = MDSegmentedControl(size_hint_x=1, size_hint_y=None, height="48dp")
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text=_t("Aylık")))
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text=_t("Yıllık")))
        self.recurring_freq_segment.bind(on_active=self.on_recurring_freq_active)

        auto_deduct_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        auto_deduct_lbl = MDLabel(text=_t("Vadesi Gelince Otomatik Düş"), valign="center")
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
        self._recurring_box.add_widget(self.recurrence_day_input)
        self._recurring_box.add_widget(self.recurring_freq_segment)
        self._recurring_box.add_widget(auto_deduct_row)
        self._recurring_visible = False

        # ── Taksit alanları (varsayılan GİZLİ) ─────────────────────────────────
        # Yalnızca Gider + kredi kartı seçiliyken görünür (aşamalı gösterim,
        # _recurring_box ile aynı remove/add deseni). 'Taksitli' seçilince
        # 1-12 arası taksit sayısı seçici belirir; aylık tutar kayıtta
        # toplam / taksit sayısı olarak hesaplanır (vade farkı uygulanmaz).
        self.selected_installments = 2
        self._installment_mode = "single"
        self._installment_visible = False
        self._installment_count_visible = False

        pay_type_lbl = MDLabel(
            text=_t("Ödeme Tipi"), font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(18),
        )
        self.installment_segment = MDSegmentedControl(size_hint_x=1, size_hint_y=None, height="48dp")
        self.installment_segment.add_widget(MDSegmentedControlItem(text=_t("Tek Çekim")))
        self.installment_segment.add_widget(MDSegmentedControlItem(text=_t("Taksitli")))
        self.installment_segment.bind(on_active=self._on_installment_mode_active)

        self.installment_count_button = ftheme.primary_button(
            _t(f"Taksit Sayısı: {self.selected_installments}"), self.theme_cls,
            size_hint_x=1, size_hint_y=None, height=dp(44),
            on_release=self.open_installment_count_menu,
        )
        self._installment_count_box = MDBoxLayout(
            orientation="vertical", size_hint_y=None, adaptive_height=True,
        )
        self._installment_count_box.add_widget(self.installment_count_button)

        self._installment_box = MDBoxLayout(
            orientation="vertical", size_hint_y=None, adaptive_height=True, spacing=dp(18),
        )
        self._installment_box.add_widget(pay_type_lbl)
        self._installment_box.add_widget(self.installment_segment)
        # _installment_count_box başta EKLENMEZ: Tek Çekim varsayılandır.

        dialog_layout.add_widget(self.amount_input)
        dialog_layout.add_widget(self.type_segment)
        dialog_layout.add_widget(self.category_button)
        dialog_layout.add_widget(self.account_button)
        dialog_layout.add_widget(self._below_payment_box)
        dialog_layout.add_widget(recurring_row)
        # _recurring_box başta EKLENMEZ: ilk görünüm sade kalsın.

        from kivy.uix.scrollview import ScrollView
        from kivy.core.window import Window
        form_scroll = ScrollView(
            do_scroll_x=False,
            size_hint_y=None,
            height=min(dp(440), Window.height * 0.68),
        )
        form_scroll.add_widget(dialog_layout)
        self._transaction_form_layout = dialog_layout
        self._transaction_form_scroll = form_scroll

        self.dialog = MDDialog(
            title=_t("Yeni Bir İşlem Ekle"),
            type="custom",
            content_cls=form_scroll,
            buttons=[ftheme.primary_button(
                _t("KAYDET"), self.theme_cls, on_release=self.save_transaction
            )]
        )
        self.dialog.open()
        # Varsayılan seçili ödeme yöntemini mini kartta göster.
        self._update_mini_card_preview()

    # ─── Aşamalı gösterim (progressive disclosure) ───────────────────────────

    def _toggle_recurring_fields(self, switch, active):
        """"Tekrarlanan Ödeme mi?" switch'iyle abonelik alanlarını aç/kapat.

        Açınca wrapper temel alanların (recurring_row) hemen ardına eklenir,
        kapanınca çıkarılır. adaptive_height konteyner büyüyüp küçülür; diyalog
        bir sonraki karede (layout oturunca) update_height ile yeniden ölçülür.
        """
        if active == self._recurring_visible:
            return
        layout = self._transaction_form_layout
        if active:
            # recurring_row'dan (en alttaki temel alan) hemen sonraya ekle.
            layout.add_widget(self._recurring_box)
        else:
            if self._recurring_box.parent is not None:
                layout.remove_widget(self._recurring_box)
        self._recurring_visible = active
        self._reflow_dialog()
        if active:
            Clock.schedule_once(
                lambda dt: self._transaction_form_scroll.scroll_to(
                    self.recurrence_day_input, padding=dp(12), animate=False
                ),
                0,
            )

    def _reflow_dialog(self):
        """Adaptive içerik büyüyüp küçülünce diyaloğu iki KAREDE yeniden ölçer.

        Siyah ekran/overlay hatasının kökü: remove/add_widget sonrası
        adaptive_height (content_cls) ve `_spacer_top -> container` KV bağı
        yüksekliği ancak SONRAKİ karede günceller. Tek karede update_height
        bayat yükseklik okuyup dialog kartını yanlış boyutlandırıyor, arkadaki
        ModalView siyah örtüsü ekranı kaplıyordu.

        Kare 1: içerik layout'unu zorla + update_height (_spacer_top'u tazeler).
        Kare 2: container layout'unu zorla + dialog.height'ı güncel container'dan
        oku (boyut değişimi ModalView'i yeniden ortalar).
        """
        dialog = getattr(self, "dialog", None)
        if dialog is None:
            return

        def _stage2(dt):
            if getattr(self, "dialog", None) is not dialog:
                return
            try:
                dialog.ids.container.do_layout()
                dialog.height = dialog.ids.container.height
            except Exception:
                pass

        def _stage1(dt):
            if getattr(self, "dialog", None) is not dialog:
                return
            try:
                self._transaction_form_layout.do_layout()
                dialog.content_cls.do_layout()
                dialog.update_height()
            except Exception:
                pass
            Clock.schedule_once(_stage2, 0)

        Clock.schedule_once(_stage1, 0)

    # ─── Taksit alanları (Gider + kredi kartı) ───────────────────────────────

    def _selected_payment_is_credit_card(self):
        acc = next(
            (a for a in getattr(self, "_payment_methods", [])
             if a["id"] == self.selected_account_id),
            None,
        )
        return bool(acc and acc["account_type"] == "credit_card")

    def _update_installment_visibility(self, *args):
        """'Ödeme Tipi' bloğunu yalnızca Gider + kredi kartı iken gösterir.

        Görünürlük koşulu düştüğünde mod da Tek Çekim'e sıfırlanır ki gizliyken
        bayat bir 'Taksitli' seçimi kayda sızmasın."""
        box = getattr(self, "_installment_box", None)
        container = getattr(self, "_below_payment_box", None)
        if box is None or container is None:
            return
        should_show = (
            self.selected_type == "expense" and self._selected_payment_is_credit_card()
        )
        if should_show == self._installment_visible:
            return
        if should_show:
            # Mini kart önizlemesinin hemen altına ekle (sabit konteyner).
            if box.parent is None:
                container.add_widget(box)
        else:
            if box.parent is not None:
                container.remove_widget(box)
            self._set_installment_mode("single")
        self._installment_visible = should_show
        self._reflow_dialog()

    def _set_installment_mode(self, mode):
        """Tek Çekim/Taksitli iç durumu; taksit sayısı seçicisini gösterir ve
        'Tekrarlanan Ödeme' alanını KARŞILIKLI DIŞLAR (Taksitli iken gizler)."""
        self._installment_mode = mode
        installment_on = mode == "installment"

        # Taksit sayısı seçici (yalnızca Taksitli iken).
        if installment_on != self._installment_count_visible:
            if installment_on:
                self._installment_box.add_widget(self._installment_count_box)
            elif self._installment_count_box.parent is not None:
                self._installment_box.remove_widget(self._installment_count_box)
            self._installment_count_visible = installment_on

        # Taksitli seçiliyken 'Tekrarlanan Ödeme' switch'i (ve açıksa abonelik
        # alanları) formdan tamamen kaldırılır; Tek Çekim'de geri eklenir.
        self._set_recurring_row_visible(not installment_on)

        self._reflow_dialog()

    def _set_recurring_row_visible(self, visible):
        """'Tekrarlanan Ödeme mi?' satırını forma ekler/çıkarır (taksit dışlaması)."""
        row = getattr(self, "_recurring_row", None)
        dialog = getattr(self, "dialog", None)
        if row is None or dialog is None:
            return
        layout = dialog.content_cls
        if visible:
            if row.parent is None:
                layout.add_widget(row)  # en alta geri döner
        else:
            # Önce açık abonelik alanlarını kapat (switch sıfırlanınca
            # _toggle_recurring_fields _recurring_box'ı çıkarır), sonra satırı çıkar.
            if self.recurring_switch.active:
                self.recurring_switch.active = False
            if row.parent is not None:
                layout.remove_widget(row)

    def _on_installment_mode_active(self, segmented_control, segmented_item):
        self._set_installment_mode(
            "installment" if segmented_item.text == _t("Taksitli") else "single"
        )

    def open_installment_count_menu(self, *args):
        """1-12 arası taksit sayısı menüsü (1 = fiilen tek çekim)."""
        items = [{
            "text": _t(f"{n} Taksit"),
            "viewclass": "OneLineListItem",
            "on_release": (lambda n=n: self._set_installment_count(n)),
        } for n in range(1, 13)]
        self.installment_count_menu = MDDropdownMenu(
            caller=self.installment_count_button, items=items, width_mult=3,
        )
        self.installment_count_menu.open()

    def _set_installment_count(self, count):
        self.selected_installments = int(count)
        self.installment_count_button.text = _t(f"Taksit Sayısı: {count}")
        menu = getattr(self, "installment_count_menu", None)
        if menu is not None:
            try:
                menu.dismiss()
            except Exception:
                pass

    def on_recurring_freq_active(self, segmented_control, segmented_item):
        """Tekrarlanan ödeme sıklığı seçimini (Aylık/Yıllık) günceller."""
        self.selected_frequency = "yearly" if segmented_item.text == _t("Yıllık") else "monthly"

    def on_segment_active(self, segmented_control, segmented_item):
        """Gelir/Gider seçimi değişince türü günceller, kategori seçimini sıfırlar
        ve ödeme yöntemini yeniden doğrular.

        Kategoriler türe bağlı olduğu için eski seçim geçersiz kalır. Ödeme
        yöntemi de türe bağlı: gelir yalnızca vadesiz hesaba yatar (bkz.
        _valid_payment_methods), o yüzden gelire geçilince seçili kredi kartı
        varsa ilk geçerli hesaba düşürülür."""
        self.selected_type = "expense" if segmented_item.text == _t("Gider") else "income"
        self.selected_category = _t("Kategori Seç")
        self.category_button.text = _t("Kategori Seç")
        self._revalidate_payment_method()
        self._update_installment_visibility()
        self._update_mini_card_preview()

    # ─── Ödeme yöntemi (hesap / kart seçimi) ─────────────────────────────────

    def _load_payment_methods(self):
        """Kayıtlı hesapları/kartları okur ve varsayılan seçimi kurar.

        Varsayılan olarak ilk vadesiz hesap seçilir; hiç yoksa listedeki ilk
        kayıt. Böylece kullanıcı seçim yapmasa da işlem eskisi gibi çalışır —
        fark, artık sabit DEFAULT_ACCOUNT_ID yerine gerçek bir hesap olması.
        """
        try:
            from services.account_service import AccountService, CREDIT_CARD
            self._payment_methods = [
                account for account in AccountService.get_accounts()
                if not is_read_only_asset_account(account)
            ]
        except Exception as e:
            print("Ödeme yöntemleri okunamadı:", e)
            self._payment_methods = []

        if not self._payment_methods:
            self.selected_account_id = None
            self.account_button.text = _t("Ödeme Yöntemi (hesap yok)")
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

    def _valid_payment_methods(self):
        """Aktif işlem türüne göre seçilebilir ödeme yöntemleri.

        * Gelir  -> yalnızca vadesiz/banka hesapları (gelir kredi kartına
                    yatmaz; kredi kartına para girişi = borç ödemesi, bu ekranın
                    işi değil).
        * Gider  -> tüm vadesiz hesaplar + kayıtlı kredi kartları (karttan
                    harcama, tutarı karta borç olarak yazar).
        """
        spendable = [
            account for account in self._payment_methods
            if not is_read_only_asset_account(account)
        ]
        if self.selected_type == "income":
            return [a for a in spendable if a["account_type"] != "credit_card"]
        return spendable

    def _revalidate_payment_method(self, *args):
        """Tür değiştikten sonra seçili ödeme yöntemi hâlâ geçerli mi bakar.

        Geçersizse (ör. Gelir'e geçilmiş ama seçili kredi kartı kalmış) ilk
        geçerli hesaba düşürür ve butonu günceller. Açık bir menü varsa,
        içeriği artık eskidiği için kapatılır; kullanıcı yeniden açınca güncel
        liste gelir.
        """
        valid = self._valid_payment_methods()
        if not valid:
            return
        if self.selected_account_id not in [a["id"] for a in valid]:
            self._set_payment_method(valid[0], close_menu=False)
        menu = getattr(self, "account_menu", None)
        if menu is not None:
            try:
                menu.dismiss()
            except Exception:
                pass

    def open_account_menu(self, *args):
        """Ödeme yöntemini seçtiren menüyü açar.

        Liste, aktif işlem türüne göre filtrelenir (bkz. _valid_payment_methods):
        Gelir'de yalnızca vadesiz hesaplar, Gider'de hesaplar + kredi kartları.
        Gelir↔Gider geçişinde liste on_segment_active üzerinden yeniden doğrulanır.
        """
        # Hesap ekleme/silme veya dışarıdan bakiye güncellemesi sonrasında
        # bayat bir liste kullanılmasın. Mevcut seçim hâlâ geçerliyse koru.
        previous_account_id = self.selected_account_id
        try:
            from services.account_service import AccountService
            self._payment_methods = [
                account for account in AccountService.get_accounts()
                if not is_read_only_asset_account(account)
            ]
        except Exception as exc:
            print("Ödeme yöntemleri yenilenemedi:", exc)
        methods = self._valid_payment_methods()
        if not methods:
            toast(_t("Bu işlem türü için uygun bir hesap bulunamadı."))
            return
        current = next(
            (account for account in methods if account["id"] == previous_account_id),
            methods[0],
        )
        self._set_payment_method(current, close_menu=False)

        items = [{
            "text": self._payment_label(a),
            "viewclass": "OneLineListItem",
            "on_release": (lambda x=a: self._set_payment_method(x)),
        } for a in methods]
        self.account_menu = MDDropdownMenu(caller=self.account_button, items=items, width_mult=5)
        self.account_menu.open()

    def _set_payment_method(self, acc, close_menu=True):
        if is_read_only_asset_account(acc):
            toast(_t("Aktif Varlık hesabı salt okunurdur ve ödeme yöntemi olamaz."))
            return
        self.selected_account_id = acc["id"]
        self.account_button.text = self._payment_label(acc)
        if close_menu and getattr(self, "account_menu", None):
            self.account_menu.dismiss()
        # Kredi kartı seçilince 'Ödeme Tipi' (Tek Çekim/Taksitli) alanı belirir.
        self._update_installment_visibility()
        # Seçilen kart/hesabın mini önizlemesini (ad, son 4 hane, limit/bakiye) tazele.
        self._update_mini_card_preview()

    def _update_mini_card_preview(self, *args):
        """Ödeme yöntemi seçim alanının altındaki mini kartı seçime göre günceller.

        Kredi kartı → 'Güncel Limit' (kullanılabilir limit), vadesiz hesap →
        'Güncel Bakiye'. Diyalog kurulurken önizleme henüz yoksa sessiz çıkar."""
        widget = getattr(self, "_mini_card_preview", None)
        if widget is None:
            return
        acc = next(
            (a for a in getattr(self, "_payment_methods", [])
             if a["id"] == self.selected_account_id),
            None,
        )
        if acc is None:
            widget.card_name = _t("Ödeme yöntemi seçilmedi")
            widget.masked_text = ""
            widget.info_label = ""
            widget.info_value = ""
            widget.icon = "credit-card-outline"
            return

        style = self.theme_cls.theme_style
        widget.card_name = acc["name"]
        is_credit = acc["account_type"] == "credit_card"

        if acc.get("has_card_number") and acc.get("masked_number"):
            widget.masked_text = f"•••• {str(acc['masked_number'])[-4:]}"
        else:
            widget.masked_text = _t(acc.get("type_label", "Kredi Kartı" if is_credit else ""))

        if is_credit:
            widget.icon = "credit-card-outline"
            widget.info_label = _t("Güncel Limit")
            widget.info_value = _fmt(acc.get("available_limit", 0.0))
            widget.accent_color = ftheme.accent(style, "blue")
        else:
            widget.icon = "bank-outline"
            widget.info_label = _t("Güncel Bakiye")
            widget.info_value = _fmt(acc.get("balance", 0.0))
            widget.accent_color = ftheme.accent(style, "green")

    def open_category_menu(self, *args):
        """Kategori seçimini ARANABİLİR bir diyalogla açar.

        Kategori listesi çok uzun olduğu için düz MDDropdownMenu yerine, üstte
        bir arama alanı + altta filtrelenebilir kaydırılır liste kuruluyor.
        Arama alanına yazıldıkça (`on_text`) liste gerçek zamanlı filtrelenir;
        bir kategori seçilince diyalog kapanır ve ana formdaki buton güncellenir.
        """
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.list import MDList, OneLineListItem

        # Kategoriler türe bağlı (gelir/gider); her açılışta güncel çekilir.
        self._all_categories = [str(c[1]) for c in CategoryService.get_categories(self.selected_type)]

        search_field = ftheme.make_text_field(
            _t("Kategori ara..."), self.theme_cls,
            size_hint_y=None, height=dp(48),
        )
        self._category_list = MDList()
        scroll = ScrollView()
        scroll.add_widget(self._category_list)

        content = MDBoxLayout(
            orientation="vertical", spacing="8dp",
            size_hint_y=None, height="380dp",
        )
        content.add_widget(search_field)
        content.add_widget(scroll)

        def populate(query=""):
            """Listeyi arama sorgusuna göre (harf duyarsız) yeniden doldurur."""
            self._category_list.clear_widgets()
            q = query.strip().lower()
            matches = [
                n for n in self._all_categories
                if q in n.lower() or q in _t(n).lower()
            ]
            if not matches:
                self._category_list.add_widget(
                    OneLineListItem(text=_t("Sonuç yok"), disabled=True))
                return
            for name in matches:
                item = OneLineListItem(text=_t(name))
                item.bind(on_release=lambda inst, n=name: self.set_category(n))
                self._category_list.add_widget(item)

        search_field.bind(text=lambda inst, val: populate(val))
        populate()

        self.category_dialog = MDDialog(
            title=_t("Kategori Seç"),
            type="custom",
            content_cls=content,
            buttons=[ftheme.secondary_button(
                _t("KAPAT"), self.theme_cls,
                on_release=lambda x: self.category_dialog.dismiss(),
            )],
        )
        self.category_dialog.open()

    def set_category(self, text_item):
        self.category_button.text = _t(text_item)
        self.selected_category = text_item
        self.on_category_select(text_item)
        # Aranabilir kategori diyaloğunu kapat (eski dropdown ile de uyumlu).
        dlg = getattr(self, "category_dialog", None) or getattr(self, "category_menu", None)
        if dlg is not None:
            try:
                dlg.dismiss()
            except Exception:
                pass

    def on_category_select(self, category):
        """Dijital Abonelik kategorisi seçildiğinde tekrarlama alanını açar."""
        from services.recurring_service import apply_category_trigger

        switch = getattr(self, "recurring_switch", None)
        if switch is not None:
            apply_category_trigger(category, switch)

    def save_transaction(self, *args):
        """Girilen işlemi doğrular ve arka planda şifreleyip veritabanına yazar.

        Doğrulama (kategori seçili mi, miktar geçerli ve pozitif mi) ana thread'de;
        AES şifreleme + DB yazma ayrı thread'de yapılır ki dialog donmasın.
        """
        if self.selected_category == _t("Kategori Seç"):
            toast(_t("Lütfen bir kategori seçin!"))
            return 
            
        try:
            user_amount = float(self.amount_input.text)
            if user_amount <= 0:
                toast(_t("Miktar 0'dan büyük olmalıdır!"))
                return
        except ValueError:
            toast(_t("Lütfen geçerli bir sayı girin!"))
            return

        is_recurring = self.recurring_switch.active
        recurring_name = self.recurring_name_input.text.strip() or self.selected_category
        recurring_frequency = self.selected_frequency
        recurring_auto_deduct = self.auto_deduct_switch.active
        recurrence_day = None
        if is_recurring:
            try:
                recurrence_day = int(self.recurrence_day_input.text)
                if not 1 <= recurrence_day <= 31:
                    raise ValueError
            except (TypeError, ValueError):
                toast(_t("Ödeme günü 1 ile 31 arasında olmalıdır."))
                return

        # Taksit: yalnızca görünür Taksitli seçimde ve 2+ taksitte plan yazılır
        # (1 taksit fiilen tek çekimdir). Aylık tutar serviste toplam/ay olarak
        # hesaplanır; açıklamaya taksit bilgisi eklenir ki ekstrede ayırt edilsin.
        use_installments = None
        if (self.selected_type == "expense"
                and getattr(self, "_installment_visible", False)
                and getattr(self, "_installment_mode", "single") == "installment"
                and getattr(self, "selected_installments", 1) >= 2):
            use_installments = self.selected_installments

        # Worker başladıktan sonra form yeniden açılır/değişirse self üzerindeki
        # alanlar başka dialoga ait olabilir. DB işi ve başarı callback'i bu
        # gönderime ait değişmez değerleri ve dialog örneğini kullanmalı.
        submitted_dialog = self.dialog
        submitted_account_id = self.selected_account_id
        submitted_type = self.selected_type
        submitted_category = self.selected_category

        if is_recurring and self.selected_type == "expense":
            # Abonelik Duplikasyonu koruması: aynı isimle (harf duyarsız)
            # ikinci kez aktif bir abonelik eklenmesin.
            from database.db import has_active_recurring_payment
            if has_active_recurring_payment(recurring_name):
                toast(_t("Bu isimde aktif bir aboneliğiniz zaten var!"))
                return

        toast(_t("İşlem şifreleniyor..."))

        import threading
        import datetime
        from kivy.clock import Clock

        def success_callback(dt):
            try:
                submitted_dialog.dismiss()
            except Exception:
                pass
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
            toast(_t("İşlem başarıyla eklendi!"))

        # Kredi kartı limit aşımı gibi kullanıcıya anlamlı gelen hatalarda genel
        # "bir hata oluştu" yerine gerçek sebebi göstermek için mesaj taşınır.
        error_message = {"text": "İşlem kaydedilirken bir hata oluştu!"}

        def error_callback(dt):
            toast(_t(error_message["text"]))

        def background_task():
            try:
                from database.db import DEFAULT_ACCOUNT_ID
                from services.account_service import AccountService
                # Kullanıcının seçtiği hesap/kart; seçim yoksa eski davranış.
                account_id = submitted_account_id or DEFAULT_ACCOUNT_ID
                selected_account = next(
                    (account for account in AccountService.get_accounts()
                     if account["id"] == account_id),
                    None,
                )
                if selected_account and is_read_only_asset_account(selected_account):
                    raise ValueError(
                        "Aktif Varlık hesabı salt okunurdur ve harcama kaynağı olamaz."
                    )
                description = submitted_category
                if use_installments:
                    description = f"{submitted_category} ({use_installments} Taksit)"
                TransactionService.add_transaction(
                    account_id=account_id,
                    amount=user_amount,
                    transaction_type=submitted_type,
                    category=submitted_category,
                    description=description,
                    installments=use_installments,
                )
                # render_accounts ön-ısıtılmış snapshot okur. DB yazımından
                # hemen sonra snapshot'ı bu worker içinde yenilemezsek başarı
                # callback'i eski bakiyeyi tekrar çizer.
                from services.asset_service import refresh_account_cache_snapshot
                refresh_account_cache_snapshot()
                if is_recurring and submitted_type == "expense":
                    from database.db import insert_recurring_payment
                    from services.recurring_service import next_due_for_recurrence
                    next_due = next_due_for_recurrence(
                        datetime.date.today(),
                        recurring_frequency,
                        recurrence_day,
                    )
                    insert_recurring_payment(
                        recurring_name, user_amount, submitted_category,
                        recurring_frequency, next_due, recurring_auto_deduct,
                        account_id=account_id,
                        recurrence_day=recurrence_day,
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

    def on_assets_tab_enter(self, *args):
        """KV'deki Varlıklarım sekmesinin `on_enter` hedefi.

        Eski `on_tab_press` grafiği ve son işlem listesini animasyon başlarken
        senkron kuruyordu — mikro takılmanın kaynağı. `on_enter` animasyon
        bitince gelir; ağır işler yine de 0.1s'lik Clock ertelemesiyle çağrılır
        ki ekran önce yerine otursun. Peş peşe sekme geçişlerinde bekleyen
        yükleme iptal edilir (bayat sekmenin işi yenisini takoslamasın).
        """
        pending = getattr(self, "_assets_tab_load_ev", None)
        if pending is not None:
            pending.cancel()

        def _load(dt):
            self._assets_tab_load_ev = None
            # refresh_dashboard_data zaten grafikleri, metrikleri ve son işlem
            # listesini TEK yoldan tazeler. Eskiden burada chart_master_box
            # ayrıca doğrudan çağrılıyordu; her sekme girişinde grafikler iki
            # kez kurulup animasyon/yerleşim spam'i yaratıyordu.
            try:
                self.refresh_dashboard_data()
            except Exception as e:
                print("Varlıklarım paneli yüklenemedi:", e)
            try:
                self.load_active_assets()
            except Exception as e:
                print("Aktif varlıklar yüklenemedi:", e)

        self._assets_tab_load_ev = Clock.schedule_once(_load, 0.1)

    def load_recent_transactions(self, list_filter=None):
        self.refresh_dashboard_data(list_filter)
