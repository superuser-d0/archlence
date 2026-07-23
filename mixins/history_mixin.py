"""Faz 2 zaman makinesi arayüzü: "Bakiye Geçmişi" diyaloğu.

Hesaplama yok — tamamı services/history_service.py'de. Bu mixin yalnızca
servisi çağırır ve sonucu MDDialog içinde gösterir (migration_mixin'deki
`show_data_privacy_dialog` diyalog kalıbı, debt_mixin'deki thread+Clock
kalıbı).

Defter okuması geçmişe gidildikçe uzayabildiği için iş arka planda yapılır,
widget dokunuşu Clock ile ana thread'e alınır.
"""
import threading
from datetime import datetime, timedelta

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from ui.i18n import tr as _t
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
import ui.theme as ftheme


def _fmt(value):
    """Tutarı Türkçe biçimde yazar (main.py::_fmt_tr ile aynı kural)."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Defterdeki teknik kaynak adlarının insan-okunur karşılıkları.
_SOURCE_LABELS = {
    "transaction": "Gelir/gider işlemleri",
    "savings_deposit": "Birikime aktarım",
    "savings_withdraw": "Birikimden iade",
    "savings_goal_deleted": "Hedef silme iadesi",
    "savings_goal_created": "Hedef açılışı",
    "account_opened": "Hesap açılışı",
    "admin_factory_reset": "Sistem sıfırlama",
    "delete_all_data": "Tüm veri silme",
}


class HistoryMixin:
    """'Bakiye Geçmişi' diyaloğunu açan ve dolduran mixin."""

    _history_dialog = None

    def show_balance_history_dialog(self, days_back=30):
        """Son N günün bakiye değişimini defterden çıkarıp gösterir."""
        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(260),
            padding=[dp(8), dp(8), dp(8), dp(8)],
            spacing=dp(8),
        )
        loading = MDLabel(
            text=_t("Defter okunuyor..."),
            theme_text_color="Secondary",
            halign="center",
        )
        content.add_widget(loading)

        self._history_dialog = MDDialog(
            title=_t(f"Bakiye Geçmişi (son {days_back} gün)"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("KAPAT"),
                    theme_text_color="Custom",
                    text_color=ftheme.accent(self.theme_cls.theme_style, "muted"),
                    on_release=lambda x: self._history_dialog.dismiss(),
                )
            ],
        )
        self._history_dialog.open()

        def work():
            try:
                from services.history_service import diff_between
                today = datetime.now().strftime("%Y-%m-%d")
                past = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                result = diff_between(past, today)
            except Exception as e:
                print("Bakiye geçmişi okunamadı:", e)
                Clock.schedule_once(
                    lambda dt: self._render_history_error(content), 0)
                return
            Clock.schedule_once(lambda dt: self._render_history(content, result), 0)

        # Dialog açılış animasyonunun ilk karelerini sorgu/decrypt işiyle
        # yarıştırma; yükleme metni görünürken işi animasyon bitince başlat.
        Clock.schedule_once(
            lambda dt: threading.Thread(target=work, daemon=True).start(), 0.4
        )

    def _render_history_error(self, container):
        container.clear_widgets()
        lbl = MDLabel(
            text=_t("Geçmiş okunamadı."),
            theme_text_color="Secondary",
            halign="center",
        )
        container.add_widget(lbl)

    def _render_history(self, container, result):
        """diff_between çıktısını diyaloğa basar."""
        try:
            container.clear_widgets()
            style = self.theme_cls.theme_style
            change = result["balance_change"]

            if change is None:
                # Defter istenen tarihten sonra başlamış: karşılaştırma noktası
                # yok. "₺0 → ₺X" göstermek kullanıcıya o tarihte parası yokmuş
                # gibi okunurdu; bunun yerine durumu açıkça söylüyoruz.
                headline = MDLabel(
                    text=_fmt(result["balance_to"]),
                    font_style="H5",
                    bold=True,
                    theme_text_color="Primary",
                    size_hint_y=None,
                    height=dp(40),
                )
                container.add_widget(headline)
                note = MDLabel(
                    text=_t(f"Bakiye defteri {result.get('ledger_start') or '—'} "
                            f"tarihinde başlıyor; öncesi için kayıt yok.\n"
                            f"Aşağıdaki hareketler defterin başlangıcından bugüne."),
                    font_style="Caption",
                    theme_text_color="Secondary",
                    size_hint_y=None,
                    height=dp(46),
                )
                note.bind(size=note.setter("text_size"))
                container.add_widget(note)
            else:
                accent = "green" if change >= 0 else "red"
                sign = "+" if change >= 0 else ""
                headline = MDLabel(
                    text=f"{sign}{_fmt(change)}",
                    font_style="H5",
                    bold=True,
                    theme_text_color="Custom",
                    text_color=ftheme.accent(style, accent),
                    size_hint_y=None,
                    height=dp(40),
                )
                container.add_widget(headline)

                span = MDLabel(
                    text=f"{result['from']}  →  {result['to']}\n"
                         f"{_fmt(result['balance_from'])} → {_fmt(result['balance_to'])}",
                    font_style="Caption",
                    theme_text_color="Secondary",
                    size_hint_y=None,
                    height=dp(38),
                )
                span.bind(size=span.setter("text_size"))
                container.add_widget(span)

            if result["savings_change"]:
                savings = MDLabel(
                    text=_t(f"Birikim hedeflerinde: {_fmt(result['savings_change'])} değişim"),
                    font_style="Caption",
                    theme_text_color="Secondary",
                    size_hint_y=None,
                    height=dp(22),
                )
                savings.bind(size=savings.setter("text_size"))
                container.add_widget(savings)

            by_source = result.get("by_source") or {}
            if not by_source:
                empty = MDLabel(
                    text=_t("Bu aralıkta bakiye hareketi yok."),
                    theme_text_color="Secondary",
                    font_style="Body2",
                )
                empty.bind(size=empty.setter("text_size"))
                container.add_widget(empty)
                return

            # En çok hareket ettiren kaynaktan aza doğru.
            ordered = sorted(by_source.items(), key=lambda kv: abs(kv[1]["delta"]),
                             reverse=True)
            for source, info in ordered[:5]:
                row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                                  height=dp(24), spacing=dp(8))
                row.add_widget(MDLabel(
                    text=_t(f"{_SOURCE_LABELS.get(source, source)} ({info['count']})"),
                    font_style="Caption",
                    theme_text_color="Secondary",
                ))
                row.add_widget(MDLabel(
                    text=_fmt(info["delta"]),
                    font_style="Caption",
                    bold=True,
                    halign="right",
                    theme_text_color="Custom",
                    text_color=ftheme.accent(
                        style, "green" if info["delta"] >= 0 else "red"),
                ))
                container.add_widget(row)
        except Exception as e:
            print("Bakiye geçmişi çizilemedi:", e)
