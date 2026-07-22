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
            return ftheme.make_text_field(
                hint, self.theme_cls, filter=filter,
                size_hint_y=None,
                password=password,
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
            is_credit = (self.selected_account_type == "Kredi Kartı")
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
            text_color=ftheme.on_primary(self.theme_cls)
        )

        self.account_dialog = MDDialog(
            title="Hesap / Kart Ekle",
            type="custom",
            content_cls=inner,
            buttons=[btn_cancel, btn_save],
        )
        self.account_dialog.open()

    def _fill_card_recent(self, card, account_id):
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

        try:
            from services.transaction_service import TransactionService
            items = TransactionService.get_recent_for_account(account_id, limit=3)
        except Exception as e:
            print("Kart hareketleri okunamadı:", e)
            return

        if not items:
            empty = MDLabel(
                text="Bu kartta henüz hareket yok.",
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
            toast(f"Ekstre okunamadı: {e}")
            return

        body = MDList()
        if not items:
            empty = MDLabel(
                text="Bu kartta henüz hareket yok.",
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
            title="Kart Ekstresi",
            type="custom",
            content_cls=content,
            buttons=[ftheme.secondary_button(
                "KAPAT", self.theme_cls,
                on_release=lambda x: self.statement_dialog.dismiss(),
            )],
        )
        self.statement_dialog.open()

    def open_delete_card_dialog(self, account_id):
        """Kartı ve karta bağlı hareketleri silmeden önce açık onay ister."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        card = AccountService.get_account(account_id)
        if not card or card["account_type"] != CREDIT_CARD:
            toast("Kredi kartı bulunamadı.")
            return

        def confirm(*args):
            try:
                AccountService.delete_credit_card(account_id)
            except Exception as exc:
                toast(f"Kart silinemedi: {exc}")
                return
            self.delete_card_dialog.dismiss()
            self.render_accounts()
            if hasattr(self, "refresh_dashboard_data"):
                self.refresh_dashboard_data()
            toast("Kredi kartı silindi.")

        self.delete_card_dialog = MDDialog(
            title="Kredi Kartını Sil",
            text=(
                f"{card['name']} kartı, karta bağlı ekstre hareketleri ve "
                "otomatik ödeme bağlantıları silinecek. Bu işlem geri alınamaz."
            ),
            buttons=[
                ftheme.secondary_button(
                    "VAZGEÇ", self.theme_cls,
                    on_release=lambda x: self.delete_card_dialog.dismiss(),
                ),
                ftheme.danger_button(
                    "SİL", self.theme_cls,
                    on_release=confirm,
                ),
            ],
        )
        self.delete_card_dialog.open()

    def open_card_settings(self, caller, account_id):
        """Karta özgü, nadir kullanılan işlemleri üç nokta menüsünde gösterir."""
        from kivymd.uix.menu import MDDropdownMenu

        old_menu = getattr(self, "card_settings_menu", None)
        if old_menu is not None:
            try:
                old_menu.dismiss()
            except Exception:
                pass

        def delete_card(*args):
            self.card_settings_menu.dismiss()
            # Menü kapanış animasyonu ile onay diyaloğunun üst üste binmesini
            # önlemek için diyaloğu bir sonraki frame'de aç.
            from kivy.clock import Clock
            Clock.schedule_once(
                lambda dt: self.open_delete_card_dialog(account_id), 0
            )

        self.card_settings_menu = MDDropdownMenu(
            caller=caller,
            width_mult=3,
            items=[{
                "text": "Kartı Sil",
                "viewclass": "OneLineListItem",
                "on_release": delete_card,
            }],
        )
        self.card_settings_menu.open()

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
        if not (self.root and "accounts_container" in self.root.ids and "cards_container" in self.root.ids):  # type: ignore
            return

        summary = AccountService.get_net_worth()
        self._update_account_summary(summary)

        container_cards = self.root.ids.cards_container
        container_accounts = self.root.ids.accounts_container
        
        container_cards.clear_widgets()
        container_accounts.clear_widgets()

        # Bu satır herhangi bir statik hesap bakiyesinin kopyası değildir;
        # canlı varlık portföyü birazdan arka planda hesaplanır.
        self._active_assets_bento = ActiveAssetsBentoWidget()
        container_accounts.add_widget(self._active_assets_bento)
        self._refresh_active_assets_total()
        if self._active_assets_refresh_event is None:
            from kivy.clock import Clock
            self._active_assets_refresh_event = Clock.schedule_interval(
                self._refresh_active_assets_total, 60.0
            )

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
            is_credit_card = acc["account_type"] == CREDIT_CARD
            has_card = acc.get("has_card_number", False)

            if is_read_only_asset_account(acc):
                # Mirror kart yalnızca gösterge; buton/işlem davranışı içermez.
                container_cards.add_widget(PremiumAssetMirrorWidget(
                    account_name=acc["name"],
                    balance=_fmt(acc["balance"]),
                ))
                # Hesaplarım tarafında bunun yerine canlı portföy agregasyonu
                # gösterilir; aynı isimli ikinci/statik satır oluşturulmaz.
                continue

            if is_credit_card:
                # Matematiksel Borç Hesaplama ve Type Casting
                limit_val = acc.get("credit_limit") or 0.0
                debt_val = acc.get("debt") or 0.0
                
                # Progress bar'ın 'Kullanılabilir Limit' oranını göstermesini sağla.
                # Formül: yuzde = ((limit - guncel_borc) / limit) * 100
                if debt_val == 0.0:
                    # Eski migration kartlarında limit 0 kalmış olabilir. Borç
                    # tamamen kapanmışsa bar yine de dolu görünmelidir.
                    ratio = 100.0
                elif limit_val > 0.0:
                    ratio = ((limit_val - debt_val) / limit_val) * 100.0
                else:
                    ratio = 0.0
                
                # Değeri 0 ile 100 arasında sınırla
                ratio = max(0.0, min(100.0, ratio))

                card = PremiumCreditCardWidget(
                    account_id=acc["id"],
                    debt_ratio=ratio,
                    card_name=acc["name"],
                    masked_number=acc.get("masked_number", "**** **** **** 0000"),
                    network_logo=acc.get("network_logo", ""),
                    available_limit=_fmt(acc["available_limit"]),
                    current_debt=_fmt(acc["debt"])
                )
                container_cards.add_widget(card)
                self._fill_card_recent(card, acc["id"])
            elif has_card:
                card = PremiumDebitCardWidget(
                    card_name=acc["name"],
                    masked_number=acc.get("masked_number", "**** **** **** 0000"),
                    network_logo=acc.get("network_logo", ""),
                    balance=_fmt(acc["balance"])
                )
                container_cards.add_widget(card)
                self._fill_card_recent(card, acc["id"])
            else:
                card = BentoAccountWidget(
                    account_name=acc["name"],
                    account_type_label=acc["type_label"],
                    balance=_fmt(acc["balance"])
                )
                container_accounts.add_widget(card)

    def _refresh_active_assets_total(self, *args):
        """TL dışı portföy toplamını UI'yi bloklamadan yeniler."""
        if self._active_assets_refresh_busy:
            return
        self._active_assets_refresh_busy = True
        widget = self._active_assets_bento
        if widget is not None:
            widget.status_text = "Canlı fiyatlar güncelleniyor…"

        from kivy.clock import Clock
        from services.asset_service import fetch_active_non_try_total

        def _on_result(result):
            def _apply(dt):
                self._active_assets_refresh_busy = False
                current = self._active_assets_bento
                if current is None:
                    return
                total = result.get("total")
                asset_count = int(result.get("asset_count") or 0)
                priced_count = int(result.get("priced_count") or 0)
                cached_count = int(result.get("cached_count") or 0)
                if total is None:
                    current.status_text = "Canlı fiyatlara ulaşılamadı"
                    return
                if asset_count and not priced_count:
                    current.status_text = f"{asset_count} varlık • Fiyat bekleniyor"
                    return
                current.balance = _fmt(total)
                if cached_count:
                    current.status_text = f"{priced_count}/{asset_count} varlık • Son bilinen fiyat"
                elif priced_count < asset_count:
                    current.status_text = f"{priced_count}/{asset_count} varlık fiyatlandı"
                else:
                    current.status_text = f"{asset_count} TL dışı varlık • Canlı değer"

            Clock.schedule_once(_apply, 0)

        try:
            fetch_active_non_try_total(_on_result)
        except Exception:
            self._active_assets_refresh_busy = False
            if widget is not None:
                widget.status_text = "Canlı fiyatlara ulaşılamadı"

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
