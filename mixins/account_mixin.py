"""Hesaplarım / Kartlarım sekmesi mixin'i.

İş mantığı (doğrulama, kayıt, kart listesinin çizimi, net servet özeti) burada
tamamlanmıştır. Eksik olan tek parça `open_add_account_dialog` — hesap/kart ekleme
diyaloğunun KivyMD widget'ları. Diyaloğu kuran taraf, alanları okuyup tek bir
çağrıyla `commit_new_account(...)` fonksiyonuna vermelidir; doğrulama, hata
mesajı ve ekran tazeleme o fonksiyonun içindedir.

Diyalog üslubu için örnek: mixins/savings_mixin.py::add_funds_to_goal
(MDDialog type="custom" + content_cls=MDBoxLayout + MDRaisedButton'lar).
"""
from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from services.account_service import (
    ACCOUNT_TYPE_LABELS,
    CHECKING,
    CREDIT_CARD,
    AccountService,
)


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

        STUB — widget'ları ANTIGRAVITY_TASKS_ROUND3.md'ye göre kurulacak.
        Diyalog şu alanları toplamalı ve KAYDET'e basılınca aynen şu çağrıyı
        yapmalıdır (alan adları değiştirilmemeli):

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
        toast("Hesap/kart ekleme formu henüz bağlanmadı.")

    # ─── İş mantığı (tamamlandı — değiştirmeyin) ──────────────────────────────
    def commit_new_account(self, name, account_type, initial_balance=0.0,
                           credit_limit=0.0, statement_date=None):
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
        if not (self.root and "accounts_container" in self.root.ids):
            return

        summary = AccountService.get_net_worth()
        self._update_account_summary(summary)

        container = self.root.ids.accounts_container
        container.clear_widgets()

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
            container.add_widget(lbl)
            return

        for acc in accounts:
            container.add_widget(self._build_account_card(acc))

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

    def _build_account_card(self, acc):
        """Tek bir hesap/kart için özet kartı üretir.

        Kredi kartında borç ve kullanılabilir limit gösterilir (ham negatif
        bakiye ASLA gösterilmez); vadesizde düz bakiye gösterilir.
        """
        is_card = acc["account_type"] == CREDIT_CARD

        card = MDCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(104) if is_card else dp(84),
            padding=dp(16),
            spacing=dp(4),
            style="outlined",
            elevation=0,
            line_color=(0.8, 0.8, 0.8, 0.3),
            radius=[dp(20)] * 4,
            md_bg_color=(0.98, 0.92, 0.92, 1) if is_card else (0.90, 0.95, 0.92, 1),
        )

        title = MDLabel(
            text=f"{acc['name']}  ·  {acc['type_label']}",
            bold=True,
            font_style="Subtitle2",
            size_hint_y=None,
            height=dp(24),
        )
        card.add_widget(title)

        if is_card:
            detail = MDLabel(
                text=f"Güncel borç: {_fmt(acc['debt'])}",
                theme_text_color="Custom",
                text_color=(0.78, 0.1, 0.1, 1),
                bold=True,
                font_style="Body2",
                size_hint_y=None,
                height=dp(24),
            )
            card.add_widget(detail)

            limit_text = (
                f"Kullanılabilir limit: {_fmt(acc['available_limit'])} "
                f"/ {_fmt(acc['credit_limit'])}"
            )
            if acc["statement_date"]:
                limit_text += f"  ·  Kesim: her ayın {acc['statement_date']}'i"
            card.add_widget(MDLabel(
                text=limit_text,
                font_style="Caption",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(20),
            ))
        else:
            card.add_widget(MDLabel(
                text=f"Bakiye: {_fmt(acc['balance'])}",
                theme_text_color="Custom",
                text_color=(0.06, 0.55, 0.18, 1) if acc["balance"] >= 0 else (0.78, 0.1, 0.1, 1),
                bold=True,
                font_style="Body2",
                size_hint_y=None,
                height=dp(24),
            ))

        return card
