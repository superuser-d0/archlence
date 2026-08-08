"""Abonelik yönetimi arayüzü; hesaplama/yazma işleri recurring_service'te.

Aboneliklerin tek kayıt yeri `recurring_payments` (bkz. services/recurring_service).
Bu mixin iki giriş noktasından da AYNI akışı sunar:
  * Ana sayfadaki "Aktif Aboneliklerim" kartındaki iptal/düzenle butonları,
  * Bütçe planlayıcısındaki "Abonelikleri Yönet" düğmesi.

Böylece iptal/iade/zam mantığı tek yerde durur; iki ayrı diyalog kopyası
zamanla birbirinden ayrışmaz.
"""

import threading

from kivy.clock import Clock
from kivy.metrics import dp
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDList

import ui.theme as ftheme
from ui.i18n import tr as _t
from utils.formatters import attach_amount_mask, read_amount, set_amount


def _fmt(value):
    """Tutarı Türkçe biçimde yazar (projedeki _fmt kuralıyla aynı)."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class SubscriptionMixin:
    """Abonelik listesi, iptal (iki seçenekli), iade sorusu ve zam düzenleme."""

    # ─── Liste diyaloğu ──────────────────────────────────────────────────────

    def open_subscription_management(self, *args):
        """Aktif abonelikleri logolarıyla listeler; her satırda düzenle/iptal."""
        # Bütçe planlayıcısından çağrıldığında onun diyaloğunu kapat.
        planner_dialog = getattr(self, "bp_dialog", None)
        if planner_dialog is not None:
            try:
                planner_dialog.dismiss()
            except AttributeError:
                pass

        def work():
            try:
                from database.db import get_active_recurring_payments
                payments = get_active_recurring_payments()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelikler okunamadı")
                Clock.schedule_once(
                    lambda dt: toast(_t("Abonelikler okunamadı.")), 0)
                return
            Clock.schedule_once(
                lambda dt: self._show_subscription_list(payments), 0)

        threading.Thread(target=work, daemon=True).start()

    def _show_subscription_list(self, payments):
        body = MDList()
        if not payments:
            empty = MDLabel(
                text=_t("Aktif aboneliğiniz bulunmuyor."),
                font_style="Caption",
                theme_text_color="Secondary",
                halign="center",
                size_hint_y=None,
                height=dp(40),
            )
            empty.bind(size=empty.setter("text_size"))
            body.add_widget(empty)
        else:
            for payment in payments:
                body.add_widget(self._build_subscription_row(payment))

        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(body)
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(340))
        content.add_widget(scroll)

        self._dismiss_dialog("subscription_dialog")
        dialog = MDDialog(
            title=_t("Aboneliklerim"),
            type="custom",
            content_cls=content,
            buttons=[ftheme.secondary_button(
                _t("KAPAT"), self.theme_cls,
                on_release=lambda _b: self._dismiss_dialog("subscription_dialog"),
            )],
        )
        self.subscription_dialog = dialog
        dialog.open()

    def _build_subscription_row(self, payment):
        """Tek abonelik satırı: logo + ad/tutar + düzenle + iptal."""
        row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(56),
            spacing=dp(8), padding=[dp(8), dp(4), dp(8), dp(4)],
        )

        from services.brand_icon_service import resolve_cached_brand_icon_path
        icon_path = resolve_cached_brand_icon_path(payment.get("name", ""))
        if icon_path:
            from kivymd.uix.fitimage import FitImage
            row.add_widget(FitImage(
                source=icon_path,
                # Yalnızca küçültmeyi düzeltir; ayrıntı için bkz.
                # mixins/insights_mixin.py'deki aynı çağrı.
                mipmap=True,
                radius=[dp(7)] * 4,
                size_hint=(None, None),
                size=(dp(28), dp(28)),
                pos_hint={"center_y": 0.5},
            ))

        label = MDLabel(
            text=_t(f"{payment['name']}\n{_fmt(payment['amount'])}  ·  "
                    f"Sonraki: {payment['next_due_date']}"),
            font_style="Caption",
        )
        label.bind(size=label.setter("text_size"))
        row.add_widget(label)

        row.add_widget(MDFlatButton(
            text=_t("DÜZENLE"),
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
            on_release=lambda _b, p=payment: self.open_subscription_price_dialog(p),
        ))
        row.add_widget(MDFlatButton(
            text="✕",
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "red"),
            on_release=lambda _b, p=payment: self.open_subscription_cancel_dialog(p),
        ))
        return row

    # ─── Zam / fiyat düzenleme (spec 5.2) ────────────────────────────────────

    def open_subscription_price_dialog(self, payment):
        """Abonelik ücretini silip yeniden kurmadan güncellemeyi sağlar."""
        # Maskeleme kendi input_filter'ını kurar; mevcut ücret set_amount ile
        # yazılır çünkü ham "149.99" metni maskede "14.999" olurdu.
        amount_field = attach_amount_mask(ftheme.make_text_field(
            _t("Yeni Aylık Ücret (₺)"), self.theme_cls,
        ))
        set_amount(amount_field, payment["amount"])
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(80))
        content.add_widget(amount_field)

        def save(_button):
            try:
                new_amount = read_amount(amount_field)
            except (ValueError, TypeError):
                toast(_t("Geçerli bir tutar girin!"))
                return
            self._dismiss_dialog("subscription_price_dialog")
            self._apply_price_update(payment, new_amount)

        self._dismiss_dialog("subscription_price_dialog")
        dialog = MDDialog(
            title=_t(f"{payment['name']} — Ücreti Güncelle"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    _t("İPTAL"), self.theme_cls,
                    on_release=lambda _b: self._dismiss_dialog(
                        "subscription_price_dialog"),
                ),
                ftheme.primary_button(
                    _t("KAYDET"), self.theme_cls, on_release=save),
            ],
        )
        self.subscription_price_dialog = dialog
        dialog.open()

    def _apply_price_update(self, payment, new_amount):
        def work():
            try:
                from services.recurring_service import update_subscription_amount
                update_subscription_amount(payment["id"], new_amount)
            except ValueError as exc:
                # Python except bloğundan çıkarken `exc` adını temizler.
                # Gecikmeli lambda doğrudan exc'yi kapatırsa Kivy ana thread'i
                # callback'i çalıştırdığında NameError oluşur.
                message = str(exc)
                Clock.schedule_once(
                    lambda dt, value=message: toast(_t(value)), 0,
                )
                return
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik ücreti güncellenemedi")
                Clock.schedule_once(
                    lambda dt: toast(_t("Abonelik ücreti güncellenemedi.")), 0)
                return
            Clock.schedule_once(
                lambda dt: toast(_t(f"{payment['name']} ücreti güncellendi.")), 0)
            Clock.schedule_once(lambda dt: self._refresh_subscription_views(), 0)

        threading.Thread(target=work, daemon=True).start()

    # ─── İptal: iki seçenek + iade sorusu (spec 3.2) ─────────────────────────

    def open_subscription_cancel_dialog(self, payment):
        """'Sadece bu ay' ile 'bu ay ve sonrası' arasında seçim yaptırır."""
        message = MDLabel(
            text=_t(f"{payment['name']} aboneliğini nasıl kaldırmak istersiniz?"),
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(60),
            valign="middle",
        )
        message.bind(size=message.setter("text_size"))
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(64))
        content.add_widget(message)

        def only_this_month(_button):
            self._dismiss_dialog("subscription_cancel_dialog")
            self._ask_refund(payment, permanent=False)

        def permanently(_button):
            self._dismiss_dialog("subscription_cancel_dialog")
            self._ask_refund(payment, permanent=True)

        self._dismiss_dialog("subscription_cancel_dialog")
        dialog = MDDialog(
            title=_t("Aboneliği Kaldır"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    _t("VAZGEÇ"), self.theme_cls,
                    on_release=lambda _b: self._dismiss_dialog(
                        "subscription_cancel_dialog"),
                ),
                MDFlatButton(
                    text=_t("SADECE BU AY"), on_release=only_this_month),
                MDRaisedButton(
                    text=_t("KALICI OLARAK"),
                    md_bg_color=ftheme.accent(self.theme_cls.theme_style, "red"),
                    on_release=permanently,
                ),
            ],
        )
        self.subscription_cancel_dialog = dialog
        dialog.open()

    def _ask_refund(self, payment, permanent):
        """Bu ay tahsilat yapıldıysa iade teklif eder; yapılmadıysa doğrudan uygular.

        İade sorusunu yalnız gerçekten kesilmiş bir ücret varken sormak önemli:
        aksi halde kullanıcıya var olmayan bir parayı geri alma seçeneği
        sunulur ve 'evet' demesi bakiyeyi haksız yere şişirirdi.
        """
        def work():
            try:
                from services.recurring_service import find_current_period_charge
                charge = find_current_period_charge(payment["id"])
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik tahsilatı kontrol edilemedi")
                charge = None

            if not charge:
                Clock.schedule_once(
                    lambda dt: self._apply_cancel(payment, permanent, False), 0)
                return
            Clock.schedule_once(
                lambda dt: self._show_refund_prompt(payment, permanent, charge), 0)

        threading.Thread(target=work, daemon=True).start()

    def _show_refund_prompt(self, payment, permanent, charge):
        message = MDLabel(
            text=_t(
                f"Bu ay {payment['name']} için {_fmt(charge['amount'])} kesilmiş. "
                "Bu tutarı bakiyenize geri eklemek ister misiniz?"
            ),
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(72),
            valign="middle",
        )
        message.bind(size=message.setter("text_size"))
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(76))
        content.add_widget(message)

        def without_refund(_button):
            self._dismiss_dialog("subscription_refund_dialog")
            self._apply_cancel(payment, permanent, False)

        def with_refund(_button):
            self._dismiss_dialog("subscription_refund_dialog")
            self._apply_cancel(payment, permanent, True)

        self._dismiss_dialog("subscription_refund_dialog")
        dialog = MDDialog(
            title=_t("Ücret İadesi"),
            type="custom",
            content_cls=content,
            buttons=[
                ftheme.secondary_button(
                    _t("HAYIR, GEREK YOK"), self.theme_cls,
                    on_release=without_refund),
                ftheme.primary_button(
                    _t("EVET, İADE ET"), self.theme_cls, on_release=with_refund),
            ],
        )
        self.subscription_refund_dialog = dialog
        dialog.open()

    def _apply_cancel(self, payment, permanent, refund):
        """Seçilen iptal türünü ve varsa iadeyi uygular."""
        def work():
            refunded = 0.0
            try:
                from services.recurring_service import (
                    cancel_subscription, refund_current_period_charge,
                    skip_next_occurrence,
                )
                if refund:
                    refunded = refund_current_period_charge(payment["id"])
                if permanent:
                    cancel_subscription(payment["id"])
                else:
                    skip_next_occurrence(payment["id"])
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik kaldırılamadı")
                Clock.schedule_once(
                    lambda dt: toast(_t("Abonelik kaldırılamadı.")), 0)
                return

            if permanent:
                message = _t(f"{payment['name']} aboneliği durduruldu.")
            else:
                message = _t(f"{payment['name']} bu ay için atlandı.")
            if refunded:
                message += _t(f" {_fmt(refunded)} bakiyenize eklendi.")

            Clock.schedule_once(lambda dt: toast(message), 0)
            Clock.schedule_once(lambda dt: self._refresh_subscription_views(), 0)

        threading.Thread(target=work, daemon=True).start()

    # ─── Ortak ───────────────────────────────────────────────────────────────

    def _dismiss_dialog(self, attribute_name):
        dialog = getattr(self, attribute_name, None)
        if dialog is not None:
            try:
                dialog.dismiss()
            except AttributeError:
                # `attribute_name` çağrı yerinden gelen serbest bir ad; alan
                # diyalog dışında bir şey tutuyorsa tek beklenen hata bu.
                pass
            setattr(self, attribute_name, None)

    def _refresh_subscription_views(self):
        """Abonelik değiştiğinde onu gösteren tüm yüzeyleri tazeler."""
        # Açık liste diyaloğu varsa yeniden kur; kapalıysa bir şey yapma.
        if getattr(self, "subscription_dialog", None) is not None:
            self._dismiss_dialog("subscription_dialog")
            self.open_subscription_management()

        for method_name in (
            "refresh_insights",          # ana sayfa abonelik kartı + radar
            "load_upcoming_recurring",   # yaklaşan ödemeler
            "load_recent_transactions",  # iade işlemi listeye düşsün
            "safe_refresh_charts",       # bakiye/grafikler
            "render_accounts",           # hesap bakiyesi kartları
        ):
            method = getattr(self, method_name, None)
            if method is None:
                continue
            try:
                method()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception(f"{method_name} tazelenemedi")
