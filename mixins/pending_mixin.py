"""Bekleyen (ileri tarihli) işlemler paneli; veri işi transaction_service'te.

İleri tarihli bir gelir/gider `status='pending'` yazılır ve vadesi gelene kadar
bakiyeye DOKUNMAZ (bkz. TransactionService.settle_due_transactions). Kullanıcı
o kayıtları göremezse "girdim ama bakiyem değişmedi" hissi oluşur; bu panel
bekleyenleri görünür kılar, iptal ve erteleme imkânı verir.

Ana sayfadaki özet kartı yalnız bekleyen varken görünür; tüm liste ve satır
başına eylemler diyalogda durur.
"""

import threading
from datetime import date, datetime

from kivy.clock import Clock
from kivy.metrics import dp
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDList

import ui.theme as ftheme
from ui.i18n import tr as _t, trf as _tf


def _fmt(value):
    """Tutarı Türkçe biçimde yazar (projedeki _fmt kuralıyla aynı)."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _days_until(iso_date):
    """Planlanan tarihe kalan gün; okunamayan tarihte None."""
    try:
        return (date.fromisoformat(str(iso_date)[:10]) - date.today()).days
    except ValueError:
        return None


def pending_row_text(item):
    """Bir bekleyen işlem satırının etiket metnini üretir.

    Widget'tan ayrı saf fonksiyon: KivyMD widget'ları çalışan bir MDApp
    olmadan kurulamıyor, oysa "hangi metin gösterilecek" saf bir kural ve
    kendi başına test edilebilmeli.

    Tutar işaretlidir (+/-) çünkü kullanıcı için önemli olan bakiyeye ne
    olacağı; ayrıca kalan süre insan diliyle yazılır (bugün/yarın/N gün sonra).
    """
    is_income = item["type"] in ("income", "Gelir")
    signed_amount = f"{'+' if is_income else '-'}{_fmt(item['amount'])}"

    remaining = _days_until(item["execution_date"])
    if remaining is None:
        timing = str(item["execution_date"])
    elif remaining <= 0:
        timing = _t("bugün işlenecek")
    elif remaining == 1:
        timing = _t("yarın işlenecek")
    else:
        timing = _tf("{remaining} gün sonra", remaining=remaining)

    return _tf(
        "{description}\n{signed_amount}  ·  Planlanan: {execution_date}  ·  {timing}",
        description=item['description'],
        signed_amount=signed_amount,
        execution_date=item['execution_date'],
        timing=timing,
    )


class PendingMixin:
    """Ana sayfa özet kartı + 'Bekleyen İşlemler' yönetim diyaloğu."""

    _pending_dialog = None

    # ─── Ana sayfa özet kartı ────────────────────────────────────────────────

    def load_pending_transactions(self, *args):
        """Bekleyenleri arka planda okur ve özet kartını günceller."""
        def work():
            try:
                from services.transaction_service import TransactionService
                pending = TransactionService.get_pending_transactions()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bekleyen işlemler okunamadı")
                return
            Clock.schedule_once(
                lambda dt: self.render_pending_summary(pending), 0)

        threading.Thread(target=work, daemon=True).start()

    def render_pending_summary(self, pending):
        """Kartı yalnız bekleyen varken açar; yoksa tamamen gizler."""
        self._pending_cache = list(pending or [])
        try:
            card = self.root.ids.pending_tx_card
            summary = self.root.ids.pending_tx_summary
        except (AttributeError, KeyError):
            # Kök widget henüz kurulmadıysa AttributeError, id yoksa KeyError.
            return

        if not self._pending_cache:
            card.height = 0
            card.opacity = 0
            card.disabled = True
            summary.text = ""
            return

        income = sum(
            item["amount"] for item in self._pending_cache
            if item["type"] in ("income", "Gelir")
        )
        expense = sum(
            item["amount"] for item in self._pending_cache
            if item["type"] not in ("income", "Gelir")
        )
        nearest = min(
            (item["execution_date"] for item in self._pending_cache
             if item["execution_date"]),
            default="",
        )

        lines = [_tf("{count} işlem bakiyenize henüz yansımadı.", count=len(self._pending_cache))]
        if income:
            lines.append(_tf("Beklenen gelir: {amount}", amount=_fmt(income)))
        if expense:
            lines.append(_tf("Beklenen gider: {amount}", amount=_fmt(expense)))
        if nearest:
            lines.append(_tf("En yakın tarih: {nearest}", nearest=nearest))
        summary.text = "  ·  ".join(lines)

        card.height = dp(180)
        card.opacity = 1
        card.disabled = False

    # ─── Yönetim diyaloğu ────────────────────────────────────────────────────

    def open_pending_transactions(self, *args):
        """Bekleyen işlemleri satır başına iptal/ertele eylemleriyle listeler."""
        def work():
            try:
                from services.transaction_service import TransactionService
                pending = TransactionService.get_pending_transactions()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bekleyen işlemler okunamadı")
                Clock.schedule_once(
                    lambda dt: toast(_t("Bekleyen işlemler okunamadı.")), 0)
                return
            Clock.schedule_once(lambda dt: self._show_pending_dialog(pending), 0)

        threading.Thread(target=work, daemon=True).start()

    def _show_pending_dialog(self, pending):
        body = MDList()
        if not pending:
            empty = MDLabel(
                text=_t("Bekleyen işlem bulunmuyor."),
                font_style="Caption",
                theme_text_color="Secondary",
                halign="center",
                size_hint_y=None,
                height=dp(40),
            )
            empty.bind(size=empty.setter("text_size"))
            body.add_widget(empty)
        else:
            for item in pending:
                body.add_widget(self._build_pending_row(item))

        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(body)
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(340))
        content.add_widget(scroll)

        self._dismiss_pending_dialog()
        dialog = MDDialog(
            title=_t("Bekleyen İşlemler"),
            type="custom",
            content_cls=content,
            buttons=[ftheme.secondary_button(
                _t("KAPAT"), self.theme_cls,
                on_release=lambda _b: self._dismiss_pending_dialog(),
            )],
        )
        self._pending_dialog = dialog
        dialog.open()

    def _build_pending_row(self, item):
        """Tek satır: ad/tutar/planlanan tarih + ERTELE ve İPTAL."""
        row = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(62),
            spacing=dp(8), padding=[dp(8), dp(4), dp(8), dp(4)],
        )

        label = MDLabel(
            text=pending_row_text(item),
            font_style="Caption",
        )
        label.bind(size=label.setter("text_size"))
        row.add_widget(label)

        row.add_widget(MDFlatButton(
            text=_t("ERTELE"),
            theme_text_color="Custom",
            text_color=self.theme_cls.primary_color,
            on_release=lambda _b, tx=item: self.open_pending_reschedule(tx),
        ))
        row.add_widget(MDFlatButton(
            text=_t("İPTAL"),
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "red"),
            on_release=lambda _b, tx=item: self.cancel_pending_transaction(tx),
        ))
        return row

    # ─── Eylemler ────────────────────────────────────────────────────────────

    def cancel_pending_transaction(self, item):
        """Bekleyen işlemi siler; bakiyeye hiç dokunmamıştı, düzeltme gerekmez."""
        def work():
            try:
                from services.transaction_service import TransactionService
                removed = TransactionService.cancel_pending_transaction(item["id"])
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bekleyen işlem iptal edilemedi")
                Clock.schedule_once(
                    lambda dt: toast(_t("Bekleyen işlem iptal edilemedi.")), 0)
                return

            message = (
                _tf("{description} iptal edildi.", description=item['description']) if removed
                else _t("Bu işlem artık bekleyen durumda değil.")
            )
            Clock.schedule_once(lambda dt: toast(message), 0)
            Clock.schedule_once(lambda dt: self._refresh_pending_views(), 0)

        threading.Thread(target=work, daemon=True).start()

    def open_pending_reschedule(self, item):
        """Yeni tarih seçtirip işlemi yeniden planlar."""
        try:
            initial = datetime.strptime(
                str(item["execution_date"])[:10], "%Y-%m-%d").date()
        except ValueError:
            initial = date.today()

        def on_save(_picker, selected_date, _range):
            self._apply_pending_reschedule(item, selected_date.isoformat())

        # HistoryMixin'deki seçici, Python 3.14'te kaldırılan ast.Str API'si için
        # gereken yamayı ve TR/EN başlıkları zaten kuruyor; ikinci bir kopya
        # çıkarmak o yamanın tek bir yerde durmasını bozardı.
        self._open_date_picker(initial, on_save)

    def _apply_pending_reschedule(self, item, new_date):
        def work():
            try:
                from services.transaction_service import TransactionService
                updated = TransactionService.reschedule_pending_transaction(
                    item["id"], new_date)
                # Tarih bugüne/geçmişe çekildiyse işlem hemen bakiyeye geçer;
                # uzlaştırmayı burada tetiklemek "tarihi bugüne aldım ama
                # bakiyem değişmedi" durumunu önler.
                settled = TransactionService.settle_due_transactions()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bekleyen işlem ertelenemedi")
                Clock.schedule_once(
                    lambda dt: toast(_t("Bekleyen işlem ertelenemedi.")), 0)
                return

            if not updated:
                Clock.schedule_once(
                    lambda dt: toast(
                        _t("Bu işlem artık bekleyen durumda değil.")), 0)
            elif settled:
                Clock.schedule_once(
                    lambda dt: toast(
                        _tf("{description} bakiyenize işlendi.", description=item['description'])), 0)
            else:
                Clock.schedule_once(
                    lambda dt: toast(_tf("Yeni tarih: {new_date}", new_date=new_date)), 0)
            Clock.schedule_once(lambda dt: self._refresh_pending_views(), 0)

        threading.Thread(target=work, daemon=True).start()

    # ─── Ortak ───────────────────────────────────────────────────────────────

    def _dismiss_pending_dialog(self):
        if self._pending_dialog is not None:
            try:
                self._pending_dialog.dismiss()
            except AttributeError:
                pass
            self._pending_dialog = None

    def _refresh_pending_views(self):
        """Bekleyen değiştiğinde onu gösteren tüm yüzeyleri tazeler.

        Diyalog açıksa yeniden kurulur; ayrıca bakiye/metrik/projeksiyon
        yüzeyleri de tazelenir çünkü erteleme işlemi bakiyeye geçirmiş olabilir.
        """
        dialog_was_open = self._pending_dialog is not None
        if dialog_was_open:
            self._dismiss_pending_dialog()
            self.open_pending_transactions()

        self.load_pending_transactions()

        for method_name in (
            "safe_refresh_charts",       # bakiye, gelir/gider, projeksiyon
            "load_recent_transactions",  # işlenen kayıt listeye düşsün
            "render_accounts",           # hesap kartlarındaki bakiye
            "refresh_insights",          # sağlık skoru / radar
        ):
            method = getattr(self, method_name, None)
            if method is None:
                continue
            try:
                method()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception(f"{method_name} tazelenemedi")
