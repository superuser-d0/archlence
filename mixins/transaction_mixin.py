from kivy.clock import Clock
from kivy.metrics import dp
from utils.toast import toast
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
from services.transaction_service import TransactionService
from services.queries import CategoryService
import ui.theme as ftheme
from ui.components import is_read_only_asset_account, MiniCardPreviewWidget
from ui.i18n import tr as _t, trf as _tf
from utils.formatters import attach_amount_mask, read_amount


def _fmt(value):
    """Tutarı Türkçe biçimde (₺1.234,56) yazar — account_mixin._fmt ile aynı."""
    try:
        return f"₺{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "₺0,00"


#: Tekrarlayan işlem diyaloğunun sabit soru/açıklama çiftleri.
#:
#: KONTROLLÜ UYGULAMA METNİ — kullanıcı verisi değil; tam anahtarla
#: çevrilirler. Modül seviyesinde duruyorlar ki hem üretim hem testler AYNI
#: kaynaktan okusun.
RECURRING_PERIOD_PROMPTS = {
    True: (
        "Bu ayki gelir hesaba eklensin mi?",
        "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gelir hemen, "
        "gelmediyse seçilen günde eklenir.",
    ),
    False: (
        "Bu ayki gider hesaptan düşülsün mü?",
        "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gider hemen, "
        "gelmediyse seçilen günde düşülür.",
    ),
}


def recurring_period_prompt(is_income) -> str:
    """Tekrarlayan işlem diyaloğunun soru + açıklama metni.

    Saf fonksiyon: testler metni ÜRETEN kodun kendisini çağırır.
    """
    question, detail = RECURRING_PERIOD_PROMPTS[bool(is_income)]
    return _tf("{question}\n\n{detail}",
               question=_t(question), detail=_t(detail))


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

        # DÜZELTME (doğruluk hatası): "Gider" segmenti aşağıda İLK eklenen
        # (satır ~86) ve KivyMD'nin kendi göstergesi bunu varsayılan olarak
        # görsel açıdan aktif gösteriyor — ama MDSegmentedControl'ün kendi
        # kaynağı (`on_press_segment`) `on_active`'i YALNIZCA gerçek bir
        # dokunuşla tetikliyor, hiçbir varsayılan senkronizasyon yok.
        # `self.selected_type` burada "income" olarak kalsaydı: kullanıcı
        # "Gider" zaten seçili görünüyor diye sekmeye hiç dokunmadan tutarı
        # girip kaydederse, işlem SESSİZCE gelir olarak kaydedilirdi —
        # ekranda gördüğünün tam tersi. Python durumu, görsel varsayılanla
        # (Gider) eşleşecek şekilde burada kuruluyor.
        self.selected_type = "expense"
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
        # filter="float" VERİLMEZ: maskeleme '.'yi binlik ayraç olarak ekliyor,
        # Kivy'nin float filtresi ise onu ondalık nokta sayıp ikincisini
        # reddediyor — ikisi birlikte çalışmaz. attach_amount_mask kendi
        # filtresini kurar (yalnız rakam + tek ondalık ayraç).
        self.amount_input = attach_amount_mask(ftheme.make_text_field(
            _t("Miktar (₺)"), self.theme_cls,
            size_hint_y=None, height=dp(48),
        ))
        
        from kivymd.uix.card import MDCard
        self.amount_card = MDCard(
            size_hint_y=None, height=dp(56),
            padding=[dp(12), dp(4), dp(12), dp(4)],
            ripple_behavior=True,
            radius=[dp(8)],
        )
        self.amount_card.md_bg_color = self.theme_cls.bg_dark if self.theme_cls.theme_style == "Dark" else self.theme_cls.bg_light
        self.amount_card.add_widget(self.amount_input)
        # DÜZELTME (Aşama 2, madde 1.6 — "ince çizgiye basmadıkça yazamıyorum"):
        # MDCard'ın `on_release` olayı yok (ripple_behavior yalnız görsel
        # efekt verir; ButtonBehavior'dan gelmez) — bind(on_release=...)
        # sessizce hiç ateşlenmiyordu, dolayısıyla tıklanabilir alan asla
        # MDTextField'ın kendi dar sınırlarının ÖTESİNE genişlemiyordu.
        # bkz. ui/theme.py::bind_card_tap.
        ftheme.bind_card_tap(
            self.amount_card,
            lambda: setattr(self.amount_input, 'focus', True),
        )

        # Segment ve butonlara açık yükseklik: adaptive konteynerde her çocuğun
        # size_hint_y=None + net height olmalı, yoksa kutu doğru ölçülmez.
        self.type_segment = MDSegmentedControl(
            size_hint_x=1, size_hint_y=None, height="48dp",
            segment_color=self.theme_cls.primary_color,
        )
        self.type_segment.add_widget(MDSegmentedControlItem(text=_t("Gider")))
        self.type_segment.add_widget(MDSegmentedControlItem(text=_t("Gelir")))
        self.type_segment.bind(on_active=self.on_segment_active)

        self.category_button = ftheme.primary_button(
            _t("Kategori Seç"), self.theme_cls, size_hint_x=1,
            size_hint_y=None, height=dp(44), on_release=self.open_category_menu,
        )

        # ── İşlem tarihi ────────────────────────────────────────────────────
        # Varsayılan bugün; kullanıcı geçmiş (unutulmuş harcama) ya da gelecek
        # (maaş/fatura günü) bir tarih seçebilir. Gelecek tarih seçilirse işlem
        # bakiyeye HEMEN yansımaz, bekleyenler listesine düşer — bunu kullanıcı
        # kaydetmeden önce bilmeli, o yüzden altta canlı bir ibare gösteriyoruz.
        import datetime as _datetime
        self.selected_transaction_date = _datetime.date.today()
        self.date_button = ftheme.secondary_button(
            self._transaction_date_label(), self.theme_cls,
            size_hint_x=1, size_hint_y=None, height=dp(44),
            on_release=self.open_transaction_date_picker,
        )
        # Boş MDLabel yer kaplamasın: yalnız gelecek tarihte açılır
        # (height/opacity toggle — MDLabel bu deseni destekliyor, MDTextField
        # ve MDSegmentedControl kendi yüksekliğini ezdiği için desteklemiyor).
        self.date_hint_label = MDLabel(
            text="",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "amber"),
            size_hint_y=None,
            height=0,
            opacity=0,
        )
        self.date_hint_label.bind(
            size=self.date_hint_label.setter("text_size"))
        self._date_box = MDBoxLayout(
            orientation="vertical", size_hint_y=None, adaptive_height=True,
            spacing=dp(4),
        )
        self._date_box.add_widget(self.date_button)
        self._date_box.add_widget(self.date_hint_label)

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
        recurring_row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp",
            padding=[0, 0, dp(24), 0],
        )
        # Taksitli mod ile karşılıklı dışlama için self üzerinde tutulur.
        self._recurring_row = recurring_row
        self._recurring_label = MDLabel(
            text=_t("Tekrarlanan Ödeme mi?"), valign="center",
        )
        self._recurring_label.bind(
            size=self._recurring_label.setter('text_size'))
        self.recurring_switch = MDSwitch(size_hint_x=None, width=dp(65))
        self.recurring_switch.bind(active=self._toggle_recurring_fields)
        recurring_row.add_widget(self._recurring_label)
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

        self.recurring_freq_segment = MDSegmentedControl(
            size_hint_x=1, size_hint_y=None, height="48dp",
            segment_color=self.theme_cls.primary_color,
        )
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text=_t("Aylık")))
        self.recurring_freq_segment.add_widget(MDSegmentedControlItem(text=_t("Yıllık")))
        self.recurring_freq_segment.bind(on_active=self.on_recurring_freq_active)

        auto_deduct_row = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="44dp", spacing="12dp")
        self._auto_deduct_label = MDLabel(
            text=_t("Vadesi Gelince Otomatik Düş"), valign="center",
        )
        self._auto_deduct_label.bind(
            size=self._auto_deduct_label.setter("text_size"),
        )
        self.auto_deduct_switch = MDSwitch(size_hint_x=None, width=dp(65))
        auto_deduct_row.add_widget(self._auto_deduct_label)
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
        self._update_recurring_copy()

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
        self.installment_segment = MDSegmentedControl(
            size_hint_x=1, size_hint_y=None, height="48dp",
            segment_color=self.theme_cls.primary_color,
        )
        self.installment_segment.add_widget(MDSegmentedControlItem(text=_t("Tek Çekim")))
        self.installment_segment.add_widget(MDSegmentedControlItem(text=_t("Taksitli")))
        self.installment_segment.bind(on_active=self._on_installment_mode_active)

        self.installment_count_button = ftheme.primary_button(
            _tf("Taksit Sayısı: {selected_installments}", selected_installments=self.selected_installments), self.theme_cls,
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

        dialog_layout.add_widget(self.amount_card)
        dialog_layout.add_widget(self.type_segment)
        dialog_layout.add_widget(self.category_button)
        dialog_layout.add_widget(self._date_box)
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
        self._rebuild_focus_chain()

    # ─── Klavye navigasyonu ──────────────────────────────────────────────────

    def _rebuild_focus_chain(self):
        """İşlem formundaki alanların TAB sırasını (yeniden) kurar.

        Abonelik alanları aşamalı gösterimle ağaca eklenip çıkarıldığı için
        zincir SABİT olamaz: gizli bir alana TAB ile geçilirse odak görünmeyen
        bir yere gider ve kullanıcı klavyeyi kaybeder. Bu yüzden görünürlük her
        değiştiğinde zincir baştan kurulur.

        `write_tab=False` TAB'ın metne sekme yazmasını engeller; odağın NEREYE
        gideceğini `focus_next` belirler — ikisi birlikte olmadan TAB hiçbir şey
        yapmaz (ilk hatanın sebebi buydu).
        """
        chain = [getattr(self, "amount_input", None)]
        if getattr(self, "_recurring_visible", False):
            chain.append(getattr(self, "recurring_name_input", None))
            chain.append(getattr(self, "recurrence_day_input", None))
        fields = [field for field in chain if field is not None]
        if not fields:
            return

        for index, field in enumerate(fields):
            field.write_tab = False
            # Son alandan sonra başa dön: odak formdan dışarı kaçmasın.
            field.focus_next = fields[(index + 1) % len(fields)]
            field.focus_previous = fields[(index - 1) % len(fields)]

    # ─── İşlem tarihi ────────────────────────────────────────────────────────

    def _transaction_date_label(self):
        """Tarih butonunun metni: bugün için 'Bugün', diğerlerinde ISO tarih."""
        import datetime
        selected = getattr(self, "selected_transaction_date", None)
        if selected is None:
            selected = datetime.date.today()
        if selected == datetime.date.today():
            return _t("Tarih: Bugün")
        return _tf("Tarih: {date}", date=selected.isoformat())

    def open_transaction_date_picker(self, *args):
        """İşlem tarihi için takvimi açar — BUGÜN ve sonrası.

        Geçmişe dönük işlem ekleme kaldırıldı (kullanıcı kararı, v0.0.1).
        Gerekçe: geçmiş tarihli bir kayıt bakiyeyi ANINDA değiştiriyor ama
        defterde (balance_events) geriye dönük olarak doğru yere
        oturmuyordu; bu da "Cüzdanım" ile grafik/defter toplamlarının
        birbirinden ayrışmasına yol açan bir kaynak. İleri tarihli işlem
        akışı olduğu gibi duruyor: bekleyenler listesine düşer ve tarihi
        gelince bakiyeye işlenir.
        """
        import datetime
        today = datetime.date.today()
        initial = getattr(self, "selected_transaction_date", today)
        if initial < today:
            initial = today

        def on_save(_picker, selected_date, _range):
            # Savunma katmanı: seçici zaten geçmişi kapatıyor, ama tarih
            # buraya başka bir yoldan gelirse sessizce geçmişe yazmayalım.
            self.selected_transaction_date = max(selected_date, today)
            self._refresh_transaction_date_ui()

        # HistoryMixin'deki seçici, Kivy 2.3.1'in Python 3.14'te ihtiyaç duyduğu
        # ast.Str yamasını ve TR/EN başlıkları zaten kuruyor; kopyalamak o yamayı
        # iki yere dağıtırdı.
        self._open_date_picker(initial, on_save, min_date=today)

    def _refresh_transaction_date_ui(self):
        """Buton metnini ve gelecek tarih ibaresini seçime göre günceller."""
        import datetime
        selected = getattr(
            self, "selected_transaction_date", datetime.date.today())

        button = getattr(self, "date_button", None)
        if button is not None:
            button.text = self._transaction_date_label()

        hint = getattr(self, "date_hint_label", None)
        if hint is None:
            return

        if selected > datetime.date.today():
            hint.text = _t(
                "Bu işlem bekleyenler listesine eklenecek; tarihi geldiğinde "
                "bakiyeye yansıyacak."
            )
            hint.height = dp(34)
            hint.opacity = 1
        else:
            # Geçmiş/bugün: uyarıya gerek yok, satırı tamamen kapat.
            hint.text = ""
            hint.height = 0
            hint.opacity = 0
        self._reflow_dialog()

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
        # Zincir görünürlükle birlikte yenilenir: gizli bir alana TAB ile
        # geçilirse odak görünmeyen bir yere gider.
        self._rebuild_focus_chain()
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
                from utils.logging_config import get_logger
                get_logger().exception("İşlem diyaloğu yeniden yerleşimi (2. aşama) tamamlanamadı")

        def _stage1(dt):
            if getattr(self, "dialog", None) is not dialog:
                return
            try:
                self._transaction_form_layout.do_layout()
                dialog.content_cls.do_layout()
                dialog.update_height()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("İşlem diyaloğu yeniden yerleşimi (1. aşama) tamamlanamadı")
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
            "text": _tf("{count} Taksit", count=n),
            "viewclass": "OneLineListItem",
            "on_release": (lambda n=n: self._set_installment_count(n)),
        } for n in range(1, 13)]
        self.installment_count_menu = MDDropdownMenu(
            caller=self.installment_count_button, items=items, width_mult=3,
        )
        self.installment_count_menu.open()

    def _set_installment_count(self, count):
        self.selected_installments = int(count)
        self.installment_count_button.text = _tf("Taksit Sayısı: {count}", count=count)
        menu = getattr(self, "installment_count_menu", None)
        if menu is not None:
            try:
                menu.dismiss()
            except AttributeError:
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
        self._update_recurring_copy()
        self._update_installment_visibility()
        self._update_mini_card_preview()

    def _update_recurring_copy(self):
        """Tekrarlama alanlarını seçilen nakit-akışı yönüne göre adlandırır."""
        is_income = getattr(self, "selected_type", "expense") == "income"
        day_field = getattr(self, "recurrence_day_input", None)
        auto_label = getattr(self, "_auto_deduct_label", None)
        recurring_label = getattr(self, "_recurring_label", None)
        name_field = getattr(self, "recurring_name_input", None)
        if recurring_label is not None:
            recurring_label.text = _t(
                "Tekrarlanan Gelir mi?"
                if is_income
                else "Tekrarlanan Ödeme mi?"
            )
        if day_field is not None:
            day_field.hint_text = _t(
                "Her Ayın Hangi Günü Yatacak? (1-31)"
                if is_income
                else "Her Ayın Hangi Günü Ödenecek? (1-31)"
            )
        if auto_label is not None:
            auto_label.text = _t(
                "Vadesi Gelince Otomatik Ekle"
                if is_income
                else "Vadesi Gelince Otomatik Düş"
            )
        if name_field is not None:
            name_field.hint_text = _t(
                "Gelir Adı (örn: Maaş)"
                if is_income
                else "Ödeme Adı (örn: Netflix)"
            )

    # ─── Ödeme yöntemi (hesap / kart seçimi) ─────────────────────────────────

    def _load_payment_methods(self):
        """Kayıtlı hesapları/kartları okur ve varsayılan seçimi kurar.

        Varsayılan olarak ilk vadesiz hesap seçilir; hiç yoksa listedeki ilk
        kayıt. Böylece kullanıcı seçim yapmasa da işlem eskisi gibi çalışır —
        fark, artık sabit DEFAULT_ACCOUNT_ID yerine gerçek bir hesap olması.
        """
        try:
            from services.account_service import AccountService
            self._payment_methods = [
                account for account in AccountService.get_accounts()
                if not is_read_only_asset_account(account)
            ]
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Ödeme yöntemleri okunamadı")
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
            except AttributeError:
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
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Ödeme yöntemleri yenilenemedi")
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

        self._category_populate_generation = getattr(self, "_category_populate_generation", 0)

        def populate(query=""):
            """Listeyi arama sorgusuna göre (harf duyarsız) yeniden doldurur.

            DÜZELTME (performans): eskiden bu fonksiyon eşleşen TÜM
            kategorileri (boş aramada ~30-50 tanesi, bkz. database/init_db.py)
            TEK karede, senkron olarak inşa ediyordu — ve arama kutusuna her
            karakter yazıldığında YENİDEN çalışıyordu (aşağıdaki
            `search_field.bind`). main.py::load_categories'teki aynı hata
            sınıfı (bkz. o fonksiyonun kendi düzeltme notu), burada daha da
            sık tetikleniyordu. Aynı kademeli-ekleme + jenerasyon-koruması
            deseni uygulandı: bir seferde yalnızca birkaç `OneLineListItem`
            eklenir, kalanı sonraki kareye bırakılır; kullanıcı yazmaya devam
            ederse bayat (bir önceki karakterin) yükleme kendini durdurur.
            """
            self._category_list.clear_widgets()
            q = query.strip().lower()
            matches = [
                n for n in self._all_categories
                if q in n.lower() or q in _t(n).lower()
            ]
            self._category_populate_generation += 1
            generation = self._category_populate_generation
            if not matches:
                self._category_list.add_widget(
                    OneLineListItem(text=_t("Sonuç yok"), disabled=True))
                return
            self._add_category_items_incrementally(matches, generation)

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

    _CATEGORY_MENU_BATCH_SIZE = 8

    def _add_category_items_incrementally(self, names, generation, index=0):
        from kivymd.uix.list import OneLineListItem

        if generation != self._category_populate_generation:
            return  # bayat arama sonucu — kullanıcı yazmaya devam etti
        category_list = getattr(self, "_category_list", None)
        if category_list is None:
            return
        end = min(index + self._CATEGORY_MENU_BATCH_SIZE, len(names))
        for name in names[index:end]:
            item = OneLineListItem(text=_t(name))
            item.bind(on_release=lambda inst, n=name: self.set_category(n))
            category_list.add_widget(item)
        if end < len(names):
            Clock.schedule_once(
                lambda dt: self._add_category_items_incrementally(names, generation, end),
                0,
            )

    def set_category(self, text_item):
        self.category_button.text = _t(text_item)
        self.selected_category = text_item
        self.on_category_select(text_item)
        # Aranabilir kategori diyaloğunu kapat (eski dropdown ile de uyumlu).
        dlg = getattr(self, "category_dialog", None) or getattr(self, "category_menu", None)
        if dlg is not None:
            try:
                dlg.dismiss()
            except AttributeError:
                pass

    def on_category_select(self, category):
        """Dijital Abonelik kategorisi seçildiğinde tekrarlama alanını açar."""
        from services.recurring_service import apply_category_trigger

        switch = getattr(self, "recurring_switch", None)
        if switch is not None:
            apply_category_trigger(category, switch)

    def save_transaction(self, *args, include_current_period=None):
        """Girilen işlemi doğrular ve arka planda şifreleyip veritabanına yazar.

        Doğrulama (kategori seçili mi, miktar geçerli ve pozitif mi) ana thread'de;
        AES şifreleme + DB yazma ayrı thread'de yapılır ki dialog donmasın.
        """
        if self.selected_category == _t("Kategori Seç"):
            toast(_t("Lütfen bir kategori seçin!"))
            return 
            
        # read_amount, maskelemenin widget üzerinde tuttuğu KANONİK değeri okur.
        # Doğrudan float(self.amount_input.text) çağırmak felaket olurdu:
        # maskelenmiş "250.000" metnini float() 250.0 diye okur, yani 250 bin
        # lira sessizce 250 liraya dönerdi.
        try:
            user_amount = read_amount(self.amount_input)
        except (ValueError, TypeError):
            toast(_t("Geçersiz tutar"))
            return
        if user_amount <= 0:
            toast(_t("Miktar 0'dan büyük olmalıdır!"))
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
                toast(_t("Tekrarlama günü 1 ile 31 arasında olmalıdır."))
                return

        if (
            is_recurring
            and include_current_period is None
        ):
            self._ask_include_current_period()
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

        import threading
        import datetime
        from kivy.clock import Clock

        # Worker başladıktan sonra form yeniden açılır/değişirse self üzerindeki
        # alanlar başka dialoga ait olabilir. DB işi ve başarı callback'i bu
        # gönderime ait değişmez değerleri ve dialog örneğini kullanmalı.
        submitted_dialog = self.dialog
        submitted_account_id = self.selected_account_id
        # Dialog açılırken zaten okunan snapshot'ı worker'a taşı. Her kayıt
        # işleminde bütün hesapları yeniden sorgulayıp çözmek gereksiz DB ve
        # şifreleme yükünün yanı sıra SQLite kilit rekabeti yaratıyordu.
        submitted_account = next(
            (account for account in getattr(self, "_payment_methods", [])
             if account["id"] == submitted_account_id),
            None,
        )
        submitted_type = self.selected_type
        submitted_category = self.selected_category
        # Seçilen tarih de gönderime ait değişmez bir değer: worker çalışırken
        # kullanıcı formu yeniden açarsa self.selected_transaction_date başka
        # bir diyaloga ait olabilir.
        submitted_date = getattr(self, "selected_transaction_date", None)
        if is_recurring and include_current_period:
            from services.recurring_service import initial_recurring_income_date
            submitted_date = initial_recurring_income_date(
                datetime.date.today(), recurrence_day, True,
            )
        submitted_is_future = bool(
            submitted_date and submitted_date > datetime.date.today()
        )

        if is_recurring:
            # Aynı isimle ikinci aktif gelir/gider planı oluşturulmasın.
            from database.db import has_active_recurring_payment
            if has_active_recurring_payment(recurring_name):
                toast(_t("Bu isimde aktif bir aboneliğiniz zaten var!"))
                return

        toast(_t("İşlem şifreleniyor..."))

        def success_callback(dt):
            try:
                submitted_dialog.dismiss()
            except AttributeError:
                pass
            # PERFORMANS (kullanıcı raporu: "her yeni işlem eklendiğinde aşırı
            # kasıyor"): bu dört ağır tazeleme TEK Clock karesinde peş peşe
            # çalışıyordu — dashboard metrikleri + grafikler, finansal tavsiye,
            # tekrarlayan ödemeler ve Kartlarım listesinin tamamı. Hepsi aynı
            # karede bittiği için kullanıcı her kayıtta gözle görülür bir donma
            # yaşıyordu. Artık her iş KENDİ karesinde çalışıyor: Kivy aradaki
            # karelerde girdi işleyip çizim yapabiliyor, tek kare bloklanmıyor.
            # (Aynı "kareye yay" tekniği main.py::_add_categories_incrementally
            # içinde zaten kullanılıyor.)
            jobs = [self.refresh_dashboard_data, self.generate_financial_advice]
            if is_recurring and hasattr(self, "load_upcoming_recurring"):
                jobs.append(self.load_upcoming_recurring)
            # Kartlarım listesini tazele: seçilen karta yazılan borç ve o kartın
            # "Son Hareketler" listesi anında güncellensin.
            if hasattr(self, "render_accounts"):
                jobs.append(self.render_accounts)
            self._run_refresh_jobs_across_frames(jobs)
            # İleri tarihli işlem bakiyeye yansımadı; kullanıcı "kaydettim ama
            # bakiyem değişmedi" diye tereddüt etmesin, mesaj bunu söylesin ve
            # bekleyenler paneli anında güncellensin.
            if (
                is_recurring
                and include_current_period is False
            ):
                toast(_t(
                    "Tekrarlayan işlem kaydedildi; bu ay dahil edilmedi."
                ))
            elif submitted_is_future:
                if hasattr(self, "load_pending_transactions"):
                    try:
                        self.load_pending_transactions()
                    except Exception:
                        from utils.logging_config import get_logger
                        get_logger().exception("Bekleyen özeti tazelenemedi")
                toast(_tf("İşlem {date} tarihine planlandı; bekleyenler listesinde.", date=submitted_date.isoformat()))
            else:
                toast(_t("İşlem başarıyla eklendi!"))

        # Kredi kartı limit aşımı gibi kullanıcıya anlamlı gelen hatalarda genel
        # "bir hata oluştu" yerine gerçek sebebi göstermek için mesaj taşınır.
        error_message = {"text": "İşlem kaydedilirken bir hata oluştu!"}

        def error_callback(dt):
            toast(_t(error_message["text"]))

        def background_task():
            try:
                from database.db import DEFAULT_ACCOUNT_ID
                # Kullanıcının seçtiği hesap/kart; seçim yoksa eski davranış.
                account_id = submitted_account_id or DEFAULT_ACCOUNT_ID
                selected_account = submitted_account
                if selected_account and is_read_only_asset_account(selected_account):
                    raise ValueError(
                        "Aktif Varlık hesabı salt okunurdur ve harcama kaynağı olamaz."
                    )
                description = submitted_category
                if use_installments:
                    description = f"{submitted_category} ({use_installments} Taksit)"
                # Tarih seçilmediyse None geçilir ve servis "şu an"ı kullanır
                # (eski davranış). Seçildiyse saat bileşeni EKLENİR: ui/charts.py
                # zaman kovaları tam zaman damgası bekliyor, tarih-only bir satır
                # tüm zaman grafiğini sessizce çizilmez hâle getiriyor.
                submitted_timestamp = None
                if submitted_date is not None:
                    if submitted_date == datetime.date.today():
                        # Bugün için gerçek saati koru; gün içi sıralama ve
                        # 'Bugün' filtresindeki saat kovaları buna dayanıyor.
                        submitted_timestamp = datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S")
                    else:
                        submitted_timestamp = f"{submitted_date.isoformat()} 09:00:00"

                include_initial_transaction = not (
                    is_recurring
                    and include_current_period is False
                )
                if include_initial_transaction:
                    TransactionService.add_transaction(
                        account_id=account_id,
                        amount=user_amount,
                        transaction_type=submitted_type,
                        category=submitted_category,
                        description=description,
                        transaction_date=submitted_timestamp,
                        installments=use_installments,
                        # Plan kaydını aşağıdaki akış yazar; interceptor aynı
                        # aboneliği ikinci kez oluşturmamalı.
                        detect_subscription=not is_recurring,
                    )
                    # Başarı callback'i yalnız RAM snapshot'ından çiziyor.
                    from services.asset_service import (
                        refresh_account_cache_snapshot,
                    )
                    refresh_account_cache_snapshot()
                if is_recurring:
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
                        transaction_type=submitted_type,
                    )
                Clock.schedule_once(success_callback, 0)
            except ValueError as e:
                # add_transaction doğrulama hatalarını (limit aşımı) ValueError
                # olarak fırlatır; metni doğrudan kullanıcıya gösterilebilir.
                error_message["text"] = str(e)
                Clock.schedule_once(error_callback, 0)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Save Transaction Error")
                Clock.schedule_once(error_callback, 0)

        threading.Thread(target=background_task, daemon=True).start()

    def _ask_include_current_period(self):
        """Tekrarlanan işlemin ilk ayını kullanıcıya açıkça seçtirir."""
        existing = getattr(self, "recurring_period_dialog", None)
        if existing is not None:
            try:
                existing.dismiss()
            except AttributeError:
                pass

        is_income = getattr(self, "selected_type", "expense") == "income"

        content = MDLabel(
            text=recurring_period_prompt(is_income),
            size_hint_y=None,
            height=dp(110),
            theme_text_color="Secondary",
        )

        def choose(value):
            self.recurring_period_dialog.dismiss()
            self.save_transaction(include_current_period=value)

        self.recurring_period_dialog = MDDialog(
            title=_t("Bu Ay Dahil Edilsin mi?"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    _t("BU AYI DAHİL ETME"), self.theme_cls,
                    on_release=lambda _button: choose(False),
                ),
                ftheme.primary_button(
                    _t("BU AYI DAHİL ET"), self.theme_cls,
                    on_release=lambda _button: choose(True),
                ),
            ],
        )
        self.recurring_period_dialog.open()

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
                self.refresh_dashboard_data(reuse_if_fresh=True)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Varlıklarım paneli yüklenemedi")
            try:
                self.load_active_assets()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Aktif varlıklar yüklenemedi")

        self._assets_tab_load_ev = Clock.schedule_once(_load, 0.1)

    def _run_refresh_jobs_across_frames(self, jobs):
        """Verilen tazeleme işlerini HER BİRİ AYRI KAREDE çalıştırır.

        `Clock.schedule_once(cb, 0)` bir tick sırasında çağrıldığında bir
        SONRAKİ kareye düşer; işleri zincirleyerek tek bir karenin uzun süre
        bloklanmasını önlüyoruz.

        Bir işin patlaması diğerlerini iptal etmez: kayıt zaten commit edildi,
        sunum katmanındaki bir hata kullanıcıya "işlem eklenemedi" izlenimi
        vermemeli (aynı gerekçe asset_mixin::_run_asset_refresh'te de var).
        """
        def run_next(index):
            if index >= len(jobs):
                return
            try:
                jobs[index]()
            except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
                # Sunum katmanının gerçekçi hata kümesi: eksik/yeniden kurulmuş
                # widget (AttributeError/KeyError), Kivy yaşam döngüsü
                # (RuntimeError) ve veri biçimi (TypeError/ValueError). Kasıtlı
                # olarak DAR: buradaki amaç hataları yutmak değil, zaten
                # commit edilmiş bir kaydın ardından gelen bir çizim hatasının
                # kalan tazelemeleri iptal etmesini önlemek. Gerçek bir
                # programlama hatası (ör. ImportError) yukarı çıkmalı.
                # Aynı gerekçe ve aynı küme asset_mixin::_run_asset_refresh'te.
                from utils.logging_config import get_logger
                get_logger().exception("İşlem sonrası tazeleme başarısız")
            Clock.schedule_once(lambda _dt: run_next(index + 1), 0)

        run_next(0)

    def load_recent_transactions(self, list_filter=None):
        # Bu metodun adı yalnız işlem listesini vaat ediyor. Eskiden tüm
        # dashboard'u çağırdığı için `safe_refresh_charts()` ile peş peşe
        # kullanıldığı her yerde grafik/metric/insight worker'ları iki kez
        # başlıyordu.
        self._refresh_recent_transactions(list_filter)
