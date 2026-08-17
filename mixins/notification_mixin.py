"""Başlıktaki zil — bekleyen işlemler ve yaklaşan ödemeler.

Zil uzun süre hiçbir işleyicisi olmayan bir `MDIconButton`'dı: dokununca dalga
animasyonu oynuyor, yani "çalıştı" hissi veriyor ve hiçbir şey yapmıyordu.
Arama çubuğuyla aynı kusur sınıfıydı ve o tarandığında ortaya çıktı.

VERİ YENİ DEĞİL. İki mevcut ve test edilmiş kaynağı topluyor:

  * `TransactionService.get_pending_transactions()` — vadesi gelmemiş,
    bakiyeye henüz işlenmemiş işlemler.
  * `database.db.get_active_recurring_payments()` — aktif düzenli ödemeler;
    burada ana sayfadaki "Yaklaşan Ödemeler" kartıyla AYNI kural uygulanıyor
    (vadesine 7 gün veya daha az kalanlar, gecikmişler dahil). Aynı veriyi iki
    farklı eşikle göstermek, kullanıcıya iki farklı gerçek anlatmak olurdu.

Panel arama sonuçlarıyla aynı desende: modal değil, satır içi. `MDDropdownMenu`
KivyMD 1.2'de `ModalView` üzerine kurulu ve odak yakalıyor.
"""

import datetime
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.list import OneLineListItem, TwoLineListItem

from ui.i18n import tr as _t

#: "Yaklaşan Ödemeler" kartının eşiği (mixins/recurring_mixin.py) ile AYNI.
UPCOMING_WINDOW_DAYS = 7

#: Panelde gösterilecek en fazla satır; gerisi için ilgili ekran var.
MAX_VISIBLE_NOTIFICATIONS = 6

_ROW_HEIGHT = 72


class NotificationMixin:

    def toggle_notifications(self):
        """Zil düğmesi — paneli açar, açıksa kapatır."""
        panel = self.root.ids.get("home_notifications") if self.root else None
        if panel is None:
            return
        if panel.children:
            self.clear_notifications()
            return
        # Arama paneli açıksa kapat: ikisi üst üste başlığın altını kaplar.
        self.clear_home_search_results()
        self._load_notifications()

    def _load_notifications(self):
        """Veriyi ARKA PLANDA toplar.

        `get_pending_transactions` her satırın tutarını ve açıklamasını
        çözüyor; ana thread'de yapmak zil basıldığında donma üretirdi. Desen
        `recurring_mixin.load_upcoming_recurring` ile birebir aynı, jenerasyon
        koruması dahil: hızlıca iki kez basılırsa eski sonuç yeniyi ezmesin.
        """
        self._notification_generation = (
            getattr(self, "_notification_generation", 0) + 1
        )
        generation = self._notification_generation

        def _apply(items, failed):
            if generation != getattr(self, "_notification_generation", 0):
                return
            self._render_notifications(items, failed)

        def _fetch():
            items, failed = [], False
            try:
                items = collect_notifications()
            # EXCEPTION-AUDIT: bilinçli geniş. Bu bir arka plan thread'i;
            # buradan sızan bir istisna sessizce thread'i öldürür ve panel
            # sonsuza kadar boş kalır. Yutmuyoruz — loglayıp kullanıcıya
            # "yüklenemedi" gösteriyoruz.
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bildirimler toplanamadı")
                failed = True
            Clock.schedule_once(
                lambda _dt: _apply(items, failed), 0,
            )

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_notifications(self, items, failed=False):
        panel = self.root.ids.get("home_notifications") if self.root else None
        if panel is None:
            return
        panel.clear_widgets()

        if failed:
            row = OneLineListItem(text=_t("Bildirimler yüklenemedi"))
            row._no_ripple_effect = True
            panel.add_widget(row)
            panel.height = dp(_ROW_HEIGHT)
            return

        if not items:
            row = OneLineListItem(text=_t("Bekleyen bildirim yok"))
            row._no_ripple_effect = True
            panel.add_widget(row)
            panel.height = dp(_ROW_HEIGHT)
            return

        for item in items[:MAX_VISIBLE_NOTIFICATIONS]:
            row = TwoLineListItem(
                text=item["title"],
                secondary_text=item["subtitle"],
            )
            row.bind(
                on_release=lambda _row, kind=item["kind"]:
                    self._open_notification(kind)
            )
            panel.add_widget(row)
        panel.height = dp(_ROW_HEIGHT) * min(
            len(items), MAX_VISIBLE_NOTIFICATIONS
        )

    def _open_notification(self, kind):
        nav = self.root.ids.get("bottom_nav") if self.root else None
        self.clear_notifications()
        if nav is None:
            return
        # İkisi de ana sayfada kendi kartına sahip; zil bir kısayol, ayrı bir
        # ekran değil. Sekme zaten ana sayfaysa bu bir no-op.
        nav.switch_tab("home_tab")

    def clear_notifications(self):
        panel = self.root.ids.get("home_notifications") if self.root else None
        if panel is not None:
            panel.clear_widgets()
            panel.height = 0


def collect_notifications(today=None):
    """Bildirim satırlarını toplar — UI'dan BAĞIMSIZ, bu yüzden test edilebilir.

    `today` enjekte edilebilir: "7 gün içinde" kuralını sabit bir tarihe karşı
    sınamak, testin çalıştığı güne göre değişmemesi için şart.
    """
    from services.transaction_service import TransactionService
    from database.db import get_active_recurring_payments

    today = today or datetime.date.today()
    items = []

    for pending in TransactionService.get_pending_transactions():
        items.append({
            "kind": "pending",
            "title": str(pending.get("description") or _t("Bekleyen işlem")),
            "subtitle": _t("Bekleyen işlem"),
            "date": pending.get("execution_date"),
        })

    for payment in get_active_recurring_payments():
        raw_due = payment.get("next_due_date")
        if not raw_due:
            continue
        try:
            due = datetime.date.fromisoformat(str(raw_due))
        except (TypeError, ValueError):
            # Bozuk bir tarih tüm zili düşürmemeli; o satır atlanır.
            continue
        days_left = (due - today).days
        if days_left > UPCOMING_WINDOW_DAYS:
            continue
        if days_left < 0:
            status = _t("Gecikti")
        elif days_left == 0:
            status = _t("Bugün")
        else:
            status = _t("Yaklaşan ödeme")
        items.append({
            "kind": "recurring",
            "title": str(payment.get("name") or _t("Yaklaşan ödeme")),
            "subtitle": status,
            "date": str(raw_due),
        })

    # Gecikmiş ve bugünkü olanlar üstte: sıralama tarihe göre, tarihi
    # olmayanlar en sona.
    items.sort(key=lambda entry: (entry.get("date") is None,
                                  str(entry.get("date") or "")))
    return items
