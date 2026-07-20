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
from kivy.uix.widget import Widget
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

import ui.theme as ftheme
from services.account_service import (
    ACCOUNT_TYPE_LABELS,
    CHECKING,
    CREDIT_CARD,
    AccountService
)
from ui.components import PremiumCreditCardWidget, BentoAccountWidget


def _fmt(value):
    """Tutarı Türkçe biçimde (₺1.234,56) yazar — main.py'deki _fmt ile aynı kural."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class AccountMixin:
    # Diyaloğu kuran kod bu alana MDDialog örneğini atar; commit başarılı olunca
    # buradan dismiss edilir.
    account_dialog = None

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
        type_checking = MDSegmentedControlItem(text="Nakit / Vadesiz")
        type_credit = MDSegmentedControlItem(text="Kredi Kartı")
        type_control.add_widget(type_checking)
        type_control.add_widget(type_credit)

        def create_modern_tf(hint, filter=None, password=False):
            return MDTextField(
                hint_text=hint,
                input_filter=filter,
                mode="fill",
                radius=[dp(12), dp(12), dp(12), dp(12)],
                size_hint_y=None,
                password=password
            )

        self.acc_name_field = create_modern_tf("Hesap / Kart Adı")
        self.acc_initial_balance_field = create_modern_tf("Başlangıç Bakiyesi (₺)", "float")
        self.acc_debt_field = create_modern_tf("Mevcut Borç (₺)", "float")
        self.acc_limit_field = create_modern_tf("Toplam Limit (₺)", "float")
        self.acc_statement_field = create_modern_tf("Hesap Kesim Günü (1-31, opsiyonel)", "int")
        self.acc_card_number_field = create_modern_tf("Kart Numarası (Örn: 1234 5678 1234 5678)")
        self.acc_expiry_field = create_modern_tf("Son Kullanma Tarihi (AA/YY)")
        self.acc_cvc_field = create_modern_tf("CVC (Arkada yer alan 3 hane)", filter="int", password=True)

        self.selected_account_type = "Nakit / Vadesiz"

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
            if account_type_label == "Kredi Kartı":
                dynamic_container.add_widget(self.acc_card_number_field)
                dynamic_container.add_widget(self.acc_expiry_field)
                dynamic_container.add_widget(self.acc_cvc_field)
                dynamic_container.add_widget(self.acc_debt_field)
                dynamic_container.add_widget(self.acc_limit_field)
                dynamic_container.add_widget(self.acc_statement_field)
            else:
                dynamic_container.add_widget(self.acc_initial_balance_field)
                dynamic_container.add_widget(Widget())

        fill_dynamic(self.selected_account_type)

        def on_type_change(segment, item):
            self.selected_account_type = item.text
            fill_dynamic(item.text)

        type_control.bind(on_active=on_type_change)

        def do_save(instance):
            is_credit = (self.selected_account_type == "Kredi Kartı")
            acc_type = "credit_card" if is_credit else "checking"
            
            card_number_full = None
            expiry_date = None
            cvc_code = None

            if is_credit:
                initial_balance = float(self.acc_debt_field.text or 0)
                credit_limit = float(self.acc_limit_field.text or 0)
                card_number_full = self.acc_card_number_field.text.strip()
                expiry_date = self.acc_expiry_field.text.strip()
                cvc_code = self.acc_cvc_field.text.strip()
            else:
                initial_balance = float(self.acc_initial_balance_field.text or 0)
                credit_limit = 0.0
                
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
            text="VAZGEÇ",
            on_release=do_cancel,
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls, 'muted'),
        )
        
        btn_save = MDRaisedButton(
            text="KAYDET",
            on_release=do_save,
            md_bg_color=self.theme_cls.primary_color,
            elevation=0,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1)
        )

        self.account_dialog = MDDialog(
            title="Hesap / Kart Ekle",
            type="custom",
            content_cls=inner,
            buttons=[btn_cancel, btn_save],
        )
        self.account_dialog.open()

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
            toast(str(exc))
            return False

        label = ACCOUNT_TYPE_LABELS.get(account_type, "Hesap")
        toast(f"✔ {label} eklendi: {str(name).strip()}")

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

    def render_accounts(self, *args):
        """Hesap/kart kartlarını `accounts_container`'a çizer ve özet etiketlerini
        günceller. Konteyner henüz kv'de yoksa sessizce çıkar — böylece arayüz
        parçası eklenmeden önce de backend testleri çağırabilir."""
        if not (self.root and "accounts_container" in self.root.ids and "cards_container" in self.root.ids):
            return

        summary = AccountService.get_net_worth()
        self._update_account_summary(summary)

        container_cards = self.root.ids.cards_container
        container_accounts = self.root.ids.accounts_container
        
        container_cards.clear_widgets()
        container_accounts.clear_widgets()

        accounts = AccountService.get_accounts()
        if not accounts:
            lbl = MDLabel(
                text="Henüz hesap eklenmedi — yukarıdaki butondan ekleyebilirsin.",
                font_style="Caption",
                italic=True,
                theme_text_color="Secondary",
                halign="center",
                size_hint_y=None,
                height=dp(40),
            )
            lbl.bind(size=lbl.setter("text_size"))
            container_accounts.add_widget(lbl)
            return

        for acc in accounts:
            is_card = acc["account_type"] == CREDIT_CARD
            if is_card:
                card = PremiumCreditCardWidget(
                    card_name=acc["name"],
                    masked_number=acc.get("masked_number", "**** **** **** 0000"),
                    available_limit=_fmt(acc["available_limit"]),
                    current_debt=_fmt(acc["debt"])
                )
                container_cards.add_widget(card)
            else:
                card = BentoAccountWidget(
                    account_name=acc["name"],
                    account_type_label=acc["type_label"],
                    balance=_fmt(acc["balance"])
                )
                container_accounts.add_widget(card)

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
