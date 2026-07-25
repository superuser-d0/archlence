"""Hesaplarım / Kartlarım sekmesi mixin'i.

İş mantığı (doğrulama, kayıt, kart listesinin çizimi, net servet özeti) ve
hesap/kart ekleme diyaloğu burada. Arayüz katmanı alanları okuyup tek bir
çağrıyla `commit_new_account(...)` fonksiyonuna verir; doğrulama, hata mesajı ve
ekran tazeleme o fonksiyonun içindedir.

Diyalog yerleşimindeki temel kural: içerik kutusunun (`inner`) yüksekliği
SABİTTİR. Tür seçimine göre değişen alanlar sabit yükseklikli
`dynamic_container` içinde tutulur, çünkü MDDialog yüksekliğini yalnızca
açılışta hesaplar — içerik sonradan büyürse başlığın üzerine taşar.

Diyalog üslubu için örnek: mixins/savings_mixin.py::add_funds_to_goal
(MDDialog type="custom" + content_cls=MDBoxLayout + MDRaisedButton'lar).
"""
from kivy.metrics import dp
from ui.i18n import tr as _t
from kivy.uix.widget import Widget
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.spinner import MDSpinner

import ui.theme as ftheme
from services.account_service import (
    ACCOUNT_TYPE_LABELS,
    CHECKING,
    CREDIT_CARD,
    AccountService
)
from ui.components import (
    PremiumCreditCardWidget, PremiumDebitCardWidget, PremiumAssetMirrorWidget,
    BentoAccountWidget, ActiveAssetsBentoWidget, is_read_only_asset_account,
)


def _fmt(value):
    """Tutarı Türkçe biçimde (₺1.234,56) yazar — main.py'deki _fmt ile aynı kural."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class AccountMixin:
    # Diyaloğu kuran kod bu alana MDDialog örneğini atar; commit başarılı olunca
    # buradan dismiss edilir.
    account_dialog = None
    _active_assets_refresh_event = None
    _active_assets_refresh_busy = False
    _active_assets_bento = None
    _accounts_load_event = None
    _accounts_load_generation = 0

    # ─── Diyalog (UI katmanı burada tamamlanacak) ─────────────────────────────
    def open_add_account_dialog(self, *args):
        """'Hesap/Kart Ekle' diyaloğunu açar.

        Diyalog şu alanları toplar ve KAYDET'e basılınca aynen şu çağrıyı
        yapar (alan adları değiştirilmemeli):

            self.commit_new_account(
                name=<MDTextField metni>,
                account_type=<"checking" | "credit_card">,
                initial_balance=<vadesizde başlangıç bakiyesi,
                                 kredi kartında MEVCUT BORÇ (pozitif)>,
                credit_limit=<yalnızca kredi kartında toplam limit, yoksa 0>,
                statement_date=<opsiyonel 1-31 arası kesim günü, yoksa None>,
            )

        Dönüş True ise diyalog kapatılabilir; False ise kullanıcıya toast ile
        hata gösterilmiştir, diyalog AÇIK kalmalıdır ki kullanıcı düzeltebilsin.
        """
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
        from kivy.metrics import dp

        # ── Yerleşim sabitleri ────────────────────────────────────────────────
        # TAŞMA DÜZELTMESİ: içerik kutusu eskiden adaptive_height=True idi, yani
        # tür değişince (1 alan <-> 3 alan) yüksekliği değişiyordu. MDDialog ise
        # yüksekliğini yalnızca açılışta hesapladığından büyüyen içerik yukarı
        # taşıp başlığın üzerine biniyordu. Çözüm: içerik kutusunun yüksekliği
        # SABİT; değişen alanlar sabit yükseklikli `dynamic_container` içine
        # hapsedildi. Böylece diyalog hiç yeniden ölçülmek zorunda kalmıyor.
        PAD = dp(24)
        GAP = dp(16)
        SEG_H = dp(42)          # MDSegmentedControl.segment_panel_height varsayılanı
        # MDTextField kendi yüksekliğini içeriden hesaplar (bu sürümde ~32dp) ve
        # dışarıdan verilen height'i ezer; ayrıca doğrulama hatası gösterince
        # helper_text için büyür. Bu yüzden alan başına SLOT ayrılır: konteyner
        # en kötü durumda bile taşmaz, artan boşluk alanların altında kalır.
        FIELD_SLOT = dp(56)
        # En yüksek durum kredi kartıdır: borç + limit + kesim günü + kart no + SKT + CVC = 6 alan
        DYNAMIC_H = FIELD_SLOT * 6 + GAP * 5

        type_control = MDSegmentedControl(
            pos_hint={"center_x": 0.5},
            segment_panel_height=SEG_H,
        )
        type_checking = MDSegmentedControlItem(text=_t("Nakit / Vadesiz"))
        type_credit = MDSegmentedControlItem(text=_t("Kredi Kartı"))
        type_control.add_widget(type_checking)
        type_control.add_widget(type_credit)

        def create_modern_tf(hint, filter=None, password=False):
            return ftheme.make_text_field(
                hint, self.theme_cls, filter=filter,
                size_hint_y=None,
                password=password,
            )

        self.acc_name_field = create_modern_tf(_t("Hesap / Kart Adı"))
        self.acc_initial_balance_field = create_modern_tf(_t("Başlangıç Bakiyesi (₺)"), "float")
        self.acc_debt_field = create_modern_tf(_t("Mevcut Borç (₺)"), "float")
        self.acc_limit_field = create_modern_tf(_t("Toplam Limit (₺)"), "float")
        self.acc_statement_field = create_modern_tf(_t("Hesap Kesim Günü (1-31, opsiyonel)"), "int")
        self.acc_card_number_field = create_modern_tf(_t("Kart Numarası (Örn: 1234 5678 1234 5678)"))
        self.acc_expiry_field = create_modern_tf(_t("Son Kullanma Tarihi (AA/YY)"))
        self.acc_cvc_field = create_modern_tf(_t("CVC (Arkada yer alan 3 hane)"), filter="int", password=True)

        self.selected_account_type = _t("Nakit / Vadesiz")

        dynamic_container = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=DYNAMIC_H,
            spacing=GAP,
        )
        self.acc_dynamic_container = dynamic_container

        inner = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=GAP,
            padding=[PAD, PAD, PAD, PAD],
            height=PAD * 2 + SEG_H + GAP + FIELD_SLOT + GAP + DYNAMIC_H,
        )
        inner.add_widget(type_control)
        inner.add_widget(self.acc_name_field)
        inner.add_widget(dynamic_container)

        def fill_dynamic(account_type_label):
            dynamic_container.clear_widgets()
            if account_type_label == _t("Kredi Kartı"):
                dynamic_container.add_widget(self.acc_card_number_field)
                dynamic_container.add_widget(self.acc_expiry_field)
                dynamic_container.add_widget(self.acc_cvc_field)
                dynamic_container.add_widget(self.acc_debt_field)
                dynamic_container.add_widget(self.acc_limit_field)
                dynamic_container.add_widget(self.acc_statement_field)
            else:
                # Vadesiz hesabın da fiziksel bir banka kartı olabilir. Kart
                # numarası girilirse liste PremiumDebitCardWidget çizer, boş
                # bırakılırsa düz BentoAccountWidget — alanlar OPSİYONEL.
                # Bu dal eskiden yalnızca bakiye soruyordu; o yüzden banka
                # kartı widget'ı hiçbir zaman çizilemiyordu (ölü kod).
                dynamic_container.add_widget(self.acc_initial_balance_field)
                dynamic_container.add_widget(self.acc_card_number_field)
                dynamic_container.add_widget(self.acc_expiry_field)
                dynamic_container.add_widget(Widget())

        fill_dynamic(self.selected_account_type)

        def on_type_change(segment, item):
            self.selected_account_type = item.text
            fill_dynamic(item.text)

        type_control.bind(on_active=on_type_change)

        def do_save(instance):
            is_credit = (self.selected_account_type == _t("Kredi Kartı"))
            acc_type = "credit_card" if is_credit else "checking"
            
            # Kart bilgileri her iki türde de opsiyonel; boş string yerine None
            # geçiyoruz ki servis "kart yok" durumunu ayırt edebilsin.
            card_number_full = self.acc_card_number_field.text.strip() or None
            expiry_date = self.acc_expiry_field.text.strip() or None

            if is_credit:
                initial_balance = float(self.acc_debt_field.text or 0)
                credit_limit = float(self.acc_limit_field.text or 0)
                cvc_code = self.acc_cvc_field.text.strip() or None
            else:
                initial_balance = float(self.acc_initial_balance_field.text or 0)
                credit_limit = 0.0
                # CVC yalnızca kredi kartı formunda soruluyor.
                cvc_code = None

            statement_date = self.acc_statement_field.text or None
            
            self.commit_new_account(
                name=self.acc_name_field.text,
                account_type=acc_type,
                initial_balance=initial_balance,
                credit_limit=credit_limit,
                statement_date=statement_date,
                card_number_full=card_number_full,
                expiry_date=expiry_date,
                cvc_code=cvc_code
            )

        def do_cancel(instance):
            if getattr(self, "account_dialog", None):
                self.account_dialog.dismiss()

        btn_cancel = MDFlatButton(
            text=_t("VAZGEÇ"),
            on_release=do_cancel,
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls, 'muted'),
        )
        
        btn_save = MDRaisedButton(
            text=_t("KAYDET"),
            on_release=do_save,
            md_bg_color=self.theme_cls.primary_color,
            elevation=0,
            theme_text_color="Custom",
            text_color=ftheme.on_primary(self.theme_cls)
        )

        self.account_dialog = MDDialog(
            title=_t("Hesap / Kart Ekle"),
            type="custom",
            content_cls=inner,
            buttons=[btn_cancel, btn_save],
        )
        self.account_dialog.open()

    def _fill_card_recent(self, card, account_id, items=None):
        """Kartın "Kart Kullanım Özeti" panelindeki son hareket listesini doldurur.

        Kart widget'ı KV'de boş bir `recent_container` ile geliyor; satırlar
        burada üretiliyor çünkü tutar/açıklama şifreli ve çözüm Python tarafında
        (bkz. TransactionService.get_recent_for_account).
        """
        try:
            container = card.ids.recent_container
        except Exception:
            return
        container.clear_widgets()

        if items is None:
            try:
                from services.transaction_service import TransactionService
                items = TransactionService.get_recent_for_account(account_id, limit=3)
            except Exception as e:
                print("Kart hareketleri okunamadı:", e)
                return

        if not items:
            empty = MDLabel(
                text=_t("Bu kartta henüz hareket yok."),
                font_style="Caption",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(18),
            )
            empty.bind(size=empty.setter("text_size"))
            container.add_widget(empty)
            return

        style = self.theme_cls.theme_style
        for it in items:
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(18), spacing=dp(6))
            left = MDLabel(
                text=f"{it['date'][5:]}  {it['description']}",
                font_style="Caption",
                theme_text_color="Secondary",
                shorten=True,
                shorten_from="right",
            )
            # Gider kırmızı, gelir yeşil — işaret de tutarın önünde.
            is_income = it["type"] in ("income", "Gelir", "payment")
            right = MDLabel(
                text=("+" if is_income else "−") + _fmt(abs(it["amount"])),
                font_style="Caption",
                bold=True,
                halign="right",
                size_hint_x=None,
                width=dp(86),
                theme_text_color="Custom",
                text_color=ftheme.accent(style, "green" if is_income else "red"),
            )
            row.add_widget(left)
            row.add_widget(right)
            container.add_widget(row)

    def open_card_statement(self, account_id):
        """Kartın tüm hareket geçmişini ('Ekstre') gösteren kaydırılabilir liste
        diyaloğu açar. Gider kırmızı, gelir/iade yeşil renkte listelenir —
        `_fill_card_recent` ile aynı renk kuralı, sadece 3 ile sınırlı değil.
        """
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.list import MDList
        from services.transaction_service import TransactionService

        try:
            # Ekstre, son hareket özetinin aksine yapay bir kayıt sınırı taşımaz.
            items = TransactionService.get_recent_for_account(account_id, limit=None)
        except Exception as e:
            toast(_t(f"Ekstre okunamadı: {e}"))
            return

        body = MDList()
        if not items:
            empty = MDLabel(
                text=_t("Bu kartta henüz hareket yok."),
                font_style="Caption",
                theme_text_color="Secondary",
                halign="center",
                size_hint_y=None,
                height=dp(40),
            )
            empty.bind(size=empty.setter("text_size"))
            body.add_widget(empty)
        else:
            style = self.theme_cls.theme_style
            for it in items:
                row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                   height=dp(28), spacing=dp(6),
                                   padding=(dp(8), 0, dp(8), 0))
                left = MDLabel(
                    text=f"{it['date'][:10]}  {it['description']}",
                    font_style="Caption",
                    shorten=True,
                    shorten_from="right",
                )
                is_income = it["type"] in ("income", "Gelir", "payment")
                right = MDLabel(
                    text=("+" if is_income else "−") + _fmt(abs(it["amount"])),
                    font_style="Caption",
                    bold=True,
                    halign="right",
                    size_hint_x=None,
                    width=dp(100),
                    theme_text_color="Custom",
                    text_color=ftheme.accent(style, "green" if is_income else "red"),
                )
                row.add_widget(left)
                row.add_widget(right)
                body.add_widget(row)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(body)

        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(380))
        content.add_widget(scroll)

        self.statement_dialog = MDDialog(
            title=_t("Kart Ekstresi"),
            type="custom",
            content_cls=content,
            buttons=[ftheme.secondary_button(
                _t("KAPAT"), self.theme_cls,
                on_release=lambda x: self.statement_dialog.dismiss(),
            )],
        )
        self.statement_dialog.open()

    def open_delete_card_dialog(self, account_id):
        """Aktif taksitleri arka planda sayıp kart silme onayını açar."""
        import threading
        import weakref
        from kivy.clock import Clock
        from kivymd.uix.dialog import MDDialog

        card = AccountService.get_account(account_id)
        if not card or card["account_type"] != CREDIT_CARD:
            toast(_t("Kredi kartı bulunamadı."))
            return

        owner_ref = weakref.ref(self)

        def show_dialog(active_plan_count, error=None):
            owner = owner_ref()
            if owner is None:
                return
            if error is not None:
                toast(_t(f"Taksit planları kontrol edilemedi: {_t(str(error))}"))
                return

            old_dialog = getattr(owner, "delete_card_dialog", None)
            if old_dialog is not None:
                old_dialog.dismiss()

            if active_plan_count:
                message = _t(
                    "Dikkat: Bu karta ait devam eden "
                    f"[b]{active_plan_count} adet aktif taksit planı[/b] "
                    "bulunmaktadır. "
                    "Kartı sildiğinizde bu taksit planları ve tüm geçmiş "
                    "işlemler de kalıcı olarak silinecektir. Onaylıyor musunuz?"
                )
            else:
                message = _t(
                    f"{card['name']} kartı, karta bağlı tüm geçmiş işlemler ve "
                    "otomatik ödemeler kalıcı olarak silinecektir. "
                    "Onaylıyor musunuz?"
                )

            dialog_ref = {}

            def confirm(*args):
                try:
                    AccountService.delete_credit_card(account_id)
                except Exception as exc:
                    toast(_t(f"Kart silinemedi: {_t(str(exc))}"))
                    return
                # Kartın ekrandan kalkmasını diyalog kapanış animasyonunun
                # sonuna bağlama; silme onayında state değişimi anlıktır.
                dialog_ref["dialog"].dismiss(animation=False)
                import services.asset_service as asset_service
                deleted_debt = float(card.get("debt") or 0)
                asset_service.invalidate_asset_data_cache(
                    deleted_account_id=account_id,
                    deleted_card_debt=deleted_debt,
                )

                # Confirm callback Kivy thread'indedir; state'i callback
                # dönmeden değiştir, ardından Clock ile lifecycle-sonrası aynı
                # idempotent güncellemeyi garanti et.
                owner.render_accounts(removed_account_id=account_id)

                def verify_immediate_state(dt):
                    current = owner_ref()
                    if current is not None:
                        current.render_accounts(removed_account_id=account_id)

                Clock.schedule_once(verify_immediate_state, 0)
                toast(_t("Kredi kartı silindi."))

            body = MDLabel(
                text=message,
                markup=True,
                font_style="Body1",
                theme_text_color="Primary",
                size_hint_y=None,
                height=dp(112),
            )
            body.bind(
                width=lambda label, width: setattr(
                    label, "text_size", (width, None)
                )
            )

            dialog = MDDialog(
                title=_t("Kredi Kartını Sil"),
                type="custom",
                content_cls=body,
                buttons=[
                    ftheme.secondary_button(
                        _t("VAZGEÇ"), owner.theme_cls,
                        on_release=lambda x: dialog_ref["dialog"].dismiss(),
                    ),
                    ftheme.danger_button(
                        _t("SİL"), owner.theme_cls,
                        on_release=confirm,
                    ),
                ],
            )
            dialog_ref["dialog"] = dialog
            owner.delete_card_dialog = dialog

            def clear_reference(*args):
                current = owner_ref()
                if current is not None and getattr(
                        current, "delete_card_dialog", None) is dialog:
                    current.delete_card_dialog = None

            dialog.bind(on_dismiss=clear_reference)
            dialog.open()

        def check_active_plans():
            try:
                count = AccountService.get_active_installment_plan_count(account_id)
            except Exception as exc:
                Clock.schedule_once(
                    lambda dt, captured_exc=exc: show_dialog(0, captured_exc), 0
                )
                return
            Clock.schedule_once(lambda dt: show_dialog(count), 0)

        threading.Thread(target=check_active_plans, daemon=True).start()

    def open_card_settings(self, caller, account_id):
        """Karta özgü, nadir kullanılan işlemleri üç nokta menüsünde gösterir."""
        from kivymd.uix.menu import MDDropdownMenu

        old_menu = getattr(self, "card_settings_menu", None)
        if old_menu is not None:
            try:
                old_menu.dismiss()
            except Exception:
                pass

        # Callback'ler self.card_settings_menu üzerinden gitmemeli: kullanıcı
        # kapanış animasyonu sürerken başka bir kartın menüsünü açarsa bu alan
        # artık YENİ menüyü gösterir. Her callback kendi menü örneğini kapatır.
        menu_ref = {}

        def delete_card(*args):
            menu_ref["menu"].dismiss()
            # Menü kapanış animasyonu ile onay diyaloğunun üst üste binmesini
            # önlemek için diyaloğu bir sonraki frame'de aç.
            from kivy.clock import Clock
            Clock.schedule_once(
                lambda dt: self.open_delete_card_dialog(account_id), 0
            )

        def upcoming_payments(*args):
            menu_ref["menu"].dismiss()
            from kivy.clock import Clock
            Clock.schedule_once(
                lambda dt: self.open_upcoming_installments(account_id), 0
            )

        menu = MDDropdownMenu(
            caller=caller,
            width_mult=3,
            items=[{
                "text": _t("Gelecek Ödemeler"),
                "viewclass": "OneLineListItem",
                "on_release": upcoming_payments,
            }, {
                "text": _t("Kartı Sil"),
                "viewclass": "OneLineListItem",
                "on_release": delete_card,
            }],
        )
        menu_ref["menu"] = menu
        self.card_settings_menu = menu

        def clear_menu_reference(*args):
            if getattr(self, "card_settings_menu", None) is menu:
                self.card_settings_menu = None

        menu.bind(on_dismiss=clear_menu_reference)
        menu.open()

    def open_upcoming_installments(self, account_id):
        """Kartın devam eden taksit planlarını ('Gelecek Ödemeler') listeler.

        Her satır: harcama adı, kalan/toplam taksit, aylık tutar (₺X/ay) ve
        toplam kalan borç. `open_card_statement` ile aynı diyalog deseni.
        """
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.list import MDList
        from services.transaction_service import TransactionService

        try:
            plans = TransactionService.get_installment_plans(account_id)
        except Exception as e:
            toast(_t(f"Taksit planları okunamadı: {_t(str(e))}"))
            return

        body = MDList()
        if not plans:
            empty = MDLabel(
                text=_t("Bu kartta henüz taksitli işlem bulunmuyor"),
                font_style="Caption",
                theme_text_color="Secondary",
                halign="center",
                size_hint_y=None,
                height=dp(40),
            )
            empty.bind(size=empty.setter("text_size"))
            body.add_widget(empty)
        else:
            style = self.theme_cls.theme_style
            for plan in plans:
                item = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=dp(56),
                    spacing=dp(2), padding=(dp(8), dp(4), dp(8), dp(4)),
                )
                top = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                  height=dp(24), spacing=dp(6))
                name_lbl = MDLabel(
                    text=plan["description"],
                    font_style="Subtitle2",
                    bold=True,
                    shorten=True,
                    shorten_from="right",
                )
                monthly_lbl = MDLabel(
                    text=_t(f"{_fmt(plan['monthly_amount'])} / ay"),
                    font_style="Subtitle2",
                    bold=True,
                    halign="right",
                    size_hint_x=None,
                    width=dp(120),
                    theme_text_color="Custom",
                    text_color=ftheme.accent(style, "blue"),
                )
                top.add_widget(name_lbl)
                top.add_widget(monthly_lbl)

                bottom = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                     height=dp(20), spacing=dp(6))
                # 'Kalan/Toplam Taksit': 3/6 = 3 taksit ödendi, 3 taksit kaldı.
                progress_lbl = MDLabel(
                    text=_t(f"{plan['paid_installments']}/{plan['total_installments']}"
                            f" Taksit Ödendi"),
                    font_style="Caption",
                    theme_text_color="Secondary",
                )
                remaining_lbl = MDLabel(
                    text=_t(f"Kalan: {_fmt(plan['remaining_amount'])}"),
                    font_style="Caption",
                    halign="right",
                    theme_text_color="Custom",
                    text_color=ftheme.accent(style, "red"),
                )
                bottom.add_widget(progress_lbl)
                bottom.add_widget(remaining_lbl)

                item.add_widget(top)
                item.add_widget(bottom)
                body.add_widget(item)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(body)
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(320))
        content.add_widget(scroll)

        old_dialog = getattr(self, "installments_dialog", None)
        if old_dialog is not None:
            try:
                old_dialog.dismiss()
            except Exception:
                pass

        dialog = MDDialog(
            title=_t("Gelecek Ödemeler"),
            type="custom",
            content_cls=content,
            buttons=[MDFlatButton(
                text=_t("KAPAT"),
                on_release=lambda x: dialog.dismiss(),
            )],
        )
        self.installments_dialog = dialog

        def clear_dialog_reference(*args):
            if getattr(self, "installments_dialog", None) is dialog:
                self.installments_dialog = None

        dialog.bind(on_dismiss=clear_dialog_reference)
        dialog.open()

    # ─── İş mantığı (tamamlandı — değiştirmeyin) ──────────────────────────────
    def commit_new_account(self, name, account_type, initial_balance=0.0,
                           credit_limit=0.0, statement_date=None,
                           card_number_full=None, expiry_date=None, cvc_code=None):
        """Formdan gelen veriyi doğrular, hesabı kaydeder ve ekranı tazeler.

        Başarılıysa True, doğrulama hatası varsa (toast göstererek) False döner.
        Diyaloğun kendisi burada kapatılır ki her çağıran ayrı ayrı dismiss
        etmek zorunda kalmasın.
        """
        try:
            AccountService.create_account(
                name=name,
                account_type=account_type,
                initial_balance=initial_balance,
                credit_limit=credit_limit,
                statement_date=statement_date,
                card_number_full=card_number_full,
                expiry_date=expiry_date,
                cvc_code=cvc_code
            )
        except ValueError as exc:
            toast(_t(str(exc)))
            return False

        label = ACCOUNT_TYPE_LABELS.get(account_type, "Hesap")
        toast(_t(f"✔ {label} eklendi: {str(name).strip()}"))

        if getattr(self, "account_dialog", None):
            try:
                self.account_dialog.dismiss()
            except Exception:
                pass

        self.render_accounts()
        # Net servet kartı işlem verisinden besleniyor; yeni hesap eklemek onu
        # değiştirmez ama açılış bakiyesi girildiyse özet satırı tazelenmeli.
        try:
            self.update_metrics_and_goals()
        except Exception:
            pass
        return True

    def on_accounts_tab_enter(self, *args):
        """KV'deki Kartlarım sekmesinin `on_enter` hedefi.

        `on_tab_press` animasyon başlarken tetiklenip kare atlatıyordu; `on_enter`
        geçiş bitince gelir. render_accounts zaten kendi içinde iskelet spinner +
        Clock ertelemesi + arka plan fetch + tek karelik toplu çizim yapar, o
        yüzden burada ek gecikme katmanı yok — sadece animasyon-sonrası tetikleyicidir.
        """
        self.render_accounts()

    def render_accounts(self, *args, removed_account_id=None):
        """Hesap verisini arka planda okumak yerine RAM'den çizer (Instant Render)."""
        from services.asset_service import _asset_data_cache

        if not (self.root and "accounts_container" in self.root.ids and "cards_container" in self.root.ids):  # type: ignore
            return

        container_cards = self.root.ids.cards_container
        container_accounts = self.root.ids.accounts_container

        if (removed_account_id is not None and _asset_data_cache
                and _asset_data_cache.get("ready")):
            removed_account_id = int(removed_account_id)
            for container in (container_cards, container_accounts):
                for child in list(container.children):
                    if getattr(child, "_archlence_account_id", None) == removed_account_id:
                        # Premium kartın canvas teardown'u pahalıdır. Görsel ve
                        # etkileşimsel state'i hemen kapat, fiziksel sökümü
                        # diyalog kapandıktan sonraki sakin frame'e ertele.
                        child.opacity = 0
                        child.disabled = True

                        def detach_deleted_widget(dt, widget=child,
                                                  parent=container):
                            if widget in parent.children:
                                parent.remove_widget(widget)
                            widget._archlence_detach_event = None

                        from kivy.clock import Clock
                        if getattr(child, "_archlence_detach_event", None) is None:
                            child._archlence_detach_event = Clock.schedule_once(
                                detach_deleted_widget, 0.35
                            )
            self._update_account_summary(_asset_data_cache["summary"])
            return

        if not _asset_data_cache or not _asset_data_cache.get("ready"):
            # Cache invalidation sonrasında silinmiş kart eski widget ağacında
            # bir frame daha kalmasın. İlk açılışta bu döngüler zaten boştur.
            for container in (container_cards, container_accounts):
                for child in list(container.children):
                    if getattr(child, "_archlence_account_id", None) is not None:
                        container.remove_widget(child)

            from kivymd.uix.boxlayout import MDBoxLayout
            from kivymd.uix.label import MDLabel
            from kivymd.uix.spinner import MDSpinner
            from kivy.metrics import dp
            from kivy.clock import Clock
            
            loading = MDBoxLayout(
                orientation="vertical", size_hint_y=None, height=dp(72), spacing=dp(6)
            )
            spinner = MDSpinner(
                size_hint=(None, None), size=(dp(32), dp(32)), pos_hint={"center_x": .5}, active=True
            )
            loading.add_widget(spinner)
            loading.add_widget(MDLabel(
                text=_t("Önbellek hazırlanıyor…"), font_style="Caption", theme_text_color="Secondary", halign="center"
            ))
            if not any(getattr(child, "_archlence_loading", False)
                       for child in container_accounts.children):
                loading._archlence_loading = True
                container_accounts.add_widget(loading)
            
            if getattr(self, "_accounts_cache_poll_event", None) is None:
                def poll_again(dt):
                    self._accounts_cache_poll_event = None
                    if self.root:
                        self.render_accounts()
                self._accounts_cache_poll_event = Clock.schedule_once(
                    poll_again, 0.5
                )
            return

        pending_poll = getattr(self, "_accounts_cache_poll_event", None)
        if pending_poll is not None:
            pending_poll.cancel()
            self._accounts_cache_poll_event = None

        summary = _asset_data_cache.get("summary") or {}
        accounts_raw = _asset_data_cache.get("accounts")
        accounts = accounts_raw if isinstance(accounts_raw, list) else []
        recent_raw = _asset_data_cache.get("recent")
        recent = recent_raw if isinstance(recent_raw, dict) else {}

        # Keep the existing widget tree. Rebuilding KivyMD cards is much more
        # expensive than updating their String/Numeric properties.
        existing = {
            getattr(child, "_archlence_account_id", None): child
            for child in list(container_cards.children) + list(container_accounts.children)
            if getattr(child, "_archlence_account_id", None) is not None
        }
        for child in list(container_accounts.children):
            if getattr(child, "_archlence_loading", False):
                container_accounts.remove_widget(child)

        self._update_account_summary(summary)
        
        if (self._active_assets_bento is None
                or self._active_assets_bento.parent is None):
            self._active_assets_bento = ActiveAssetsBentoWidget()
            container_accounts.add_widget(self._active_assets_bento)
        self._apply_active_assets_result(_asset_data_cache.get("active_assets_result"))

        if getattr(self, "_active_assets_refresh_event", None) is None:
            from kivy.clock import Clock
            self._active_assets_refresh_event = Clock.schedule_interval(self._silent_background_refresh, 60.0)

        if not accounts:
            for widget in existing.values():
                if widget.parent is not None:
                    widget.parent.remove_widget(widget)
            from kivymd.uix.label import MDLabel
            from kivy.metrics import dp
            lbl = MDLabel(
                text=_t("Henüz hesap eklenmedi — yukarıdaki butondan ekleyebilirsin."),
                font_style="Caption", italic=True, theme_text_color="Secondary",
                halign="center", size_hint_y=None, height=dp(40),
            )
            lbl.bind(size=lbl.setter("text_size"))
            container_accounts.add_widget(lbl)
            return

        self._account_render_generation = getattr(self, "_account_render_generation", 0) + 1
        generation = self._account_render_generation
        wanted_ids = {acc["id"] for acc in accounts}
        pending_new = []
        for acc in accounts:
            current = existing.get(acc["id"])
            if current is None:
                pending_new.append(acc)
                continue
            widget = self._render_account_widget(
                acc, container_cards, container_accounts,
                recent.get(acc["id"], []), current,
            )
            widget._archlence_account_id = acc["id"]

        for account_id, widget in existing.items():
            if account_id not in wanted_ids and widget.parent is not None:
                widget.parent.remove_widget(widget)

        def add_next(index=0):
            if generation != self._account_render_generation:
                return
            if index >= len(pending_new):
                return
            acc = pending_new[index]
            widget = self._render_account_widget(
                acc, container_cards, container_accounts,
                recent.get(acc["id"], []), None,
            )
            widget._archlence_account_id = acc["id"]
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: add_next(index + 1), 0)

        add_next()

    def _render_account_widget(self, acc, container_cards, container_accounts,
                               recent_items, existing=None):
        """Tek hesap/kart widget'ını oluşturur; yalnızca ana thread'de çağrılır."""
        is_credit_card = acc["account_type"] == CREDIT_CARD
        has_card = acc.get("has_card_number", False)

        if is_read_only_asset_account(acc):
            widget = existing if isinstance(existing, PremiumAssetMirrorWidget) else None
            if widget is None:
                widget = PremiumAssetMirrorWidget()
                container_cards.add_widget(widget)
            widget.account_name = acc["name"]
            widget.balance = _fmt(acc["balance"])
            return widget

        if is_credit_card:
            limit_val = acc.get("credit_limit") or 0.0
            debt_val = acc.get("debt") or 0.0

            if debt_val == 0.0:
                ratio = 100.0
            elif limit_val > 0.0:
                ratio = ((limit_val - debt_val) / limit_val) * 100.0
            else:
                ratio = 0.0
            ratio = max(0.0, min(100.0, ratio))

            card = existing if isinstance(existing, PremiumCreditCardWidget) else None
            if card is None:
                card = PremiumCreditCardWidget(account_id=acc["id"])
                container_cards.add_widget(card)
            card.debt_ratio = ratio
            card.card_name = _t(acc["name"])
            card.masked_number = acc.get("masked_number", "**** **** **** 0000")
            card.network_logo = acc.get("network_logo", "")
            card.available_limit = _fmt(acc["available_limit"])
            card.current_debt = _fmt(acc["debt"])
            signature = repr(recent_items)
            if getattr(card, "_archlence_recent_signature", None) != signature:
                self._fill_card_recent(card, acc["id"], recent_items)
                card._archlence_recent_signature = signature
            return card
        elif has_card:
            card = existing if isinstance(existing, PremiumDebitCardWidget) else None
            if card is None:
                card = PremiumDebitCardWidget()
                container_cards.add_widget(card)
            card.card_name = _t(acc["name"])
            card.masked_number = acc.get("masked_number", "**** **** **** 0000")
            card.network_logo = acc.get("network_logo", "")
            card.balance = _fmt(acc["balance"])
            signature = repr(recent_items)
            if getattr(card, "_archlence_recent_signature", None) != signature:
                self._fill_card_recent(card, acc["id"], recent_items)
                card._archlence_recent_signature = signature
            return card
        else:
            widget = existing if isinstance(existing, BentoAccountWidget) else None
            if widget is None:
                widget = BentoAccountWidget()
                container_accounts.add_widget(widget)
            widget.account_name = _t(acc["name"])
            widget.account_type_label = _t(acc["type_label"])
            widget.balance = _fmt(acc["balance"])
            return widget

    def _apply_active_assets_result(self, result):
        if not result:
            return
        current = getattr(self, "_active_assets_bento", None)
        if current is None:
            return
        total = result.get("total")
        asset_count = int(result.get("asset_count") or 0)
        priced_count = int(result.get("priced_count") or 0)
        cached_count = int(result.get("cached_count") or 0)

        if total is None:
            current.status_text = _t("Canlı fiyatlara ulaşılamadı")
            return

        # Açık bir hata sinyali (ağ/işlem istisnası) sessizce ₺0,00 olarak
        # yutulmasın; kullanıcı fiyatların GELMEDİĞİNİ görmeli. Soğuk önbellekle
        # gelen geçici 0 (priced_count 0 ama hata yok) yanlış alarm olmasın diye
        # yalnız gerçek error alanında bu mesaj gösterilir.
        if result.get("error"):
            current.balance = _fmt(total)
            current.status_text = _t("Fiyatlar alınamadı")
            return

        current.balance = _fmt(total)
        if cached_count:
            current.status_text = _t(f"{priced_count}/{asset_count} varlık • Son bilinen fiyat")
        elif priced_count < asset_count:
            current.status_text = _t(f"{priced_count}/{asset_count} varlık fiyatlandı")
        else:
            current.status_text = _t(f"{asset_count} TL dışı varlık • Canlı değer")

    def _silent_background_refresh(self, dt):
        """UI'yi dondurmadan sadece arkadaki önbelleği günceller (Data Warm-up)."""
        from services.asset_service import start_data_warmup
        
        def on_update():
            from services.asset_service import _asset_data_cache
            if not _asset_data_cache or not _asset_data_cache.get("ready"):
                return
            res = _asset_data_cache.get("active_assets_result")
            self._apply_active_assets_result(res)
            
            try:
                self._update_account_summary(_asset_data_cache["summary"])
            except Exception:
                pass
                
            # Grafiğin data özelliğini sessizce güncelle (varsa)
            if hasattr(self, 'active_assets_chart') and hasattr(self.active_assets_chart, 'data'):
                try:
                    self.active_assets_chart.data = _asset_data_cache.get("some_chart_data")
                except Exception:
                    pass
                    
        start_data_warmup(on_update)

    def _update_account_summary(self, summary):
        """Nakit / kart borcu / net servet etiketlerini doldurur (varsa)."""
        ids = self.root.ids
        pairs = (
            ("accounts_cash_label", _fmt(summary["cash"])),
            ("accounts_debt_label", _fmt(summary["card_debt"])),
            ("accounts_net_label", _fmt(summary["net"])),
        )
        for widget_id, text in pairs:
            if widget_id in ids:
                ids[widget_id].text = text
