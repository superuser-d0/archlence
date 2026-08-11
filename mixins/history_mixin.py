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
    "income": "Gelir işlemleri",
    "expense": "Gider işlemleri",
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
                    text=_t("ÖZEL ARALIK"),
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=lambda x: self.open_custom_history_range(content),
                ),
                MDFlatButton(
                    text=_t("TARİHTE ARA"),
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=lambda x: self.open_balance_at_picker(content),
                ),
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
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Bakiye geçmişi okunamadı")
                Clock.schedule_once(
                    lambda dt: self._render_history_error(content), 0)
                return
            Clock.schedule_once(lambda dt: self._render_history(content, result), 0)

        # Dialog açılış animasyonunun ilk karelerini sorgu/decrypt işiyle
        # yarıştırma; yükleme metni görünürken işi animasyon bitince başlat.
        Clock.schedule_once(
            lambda dt: threading.Thread(target=work, daemon=True).start(), 0.4
        )

    def _open_date_picker(self, initial_date, on_save, min_date=None):
        """KivyMD tarih seçicisini ortak callback sözleşmesiyle açar.

        `min_date` verilirse o tarihten ÖNCESİ seçilemez. Geçmiş dönem
        raporları (bu modülün kendi kullanımı) sınırsız kalır; sınırı yalnız
        işlem tarihi seçicisi kullanır (bkz. TransactionMixin).
        """
        # Picker modülü import sırasında Window sağlayıcısı ister; uygulamanın
        # headless import/test yolunu bozmamak için yalnız etkileşim anında yükle.
        # Kivy 2.3.1 parser'ı Python 3.14'te kaldırılan ast.Str API'sini hâlâ
        # kullanıyor; picker KV dosyaları ilk kez burada parse edildiği için
        # eski AST sözleşmesini dar kapsamlı olarak geri sağla.
        import ast
        if not hasattr(ast, "Str"):
            ast.Str = ast.Constant
        if not hasattr(ast.Constant, "s"):
            ast.Constant.s = property(lambda node: node.value)
        from kivymd.uix.pickers import MDDatePicker
        picker_kwargs = {}
        if min_date is not None:
            picker_kwargs["min_date"] = min_date
            # MDDatePicker, başlangıç tarihi min_date'in gerisindeyse açılışta
            # tutarsız duruma düşer; başlangıcı sınıra çekiyoruz.
            if initial_date < min_date:
                initial_date = min_date
        picker = MDDatePicker(
            year=initial_date.year,
            month=initial_date.month,
            day=initial_date.day,
            title=_t("TARİH SEÇ"),
            title_input=_t("TARİH GİR"),
            **picker_kwargs,
        )
        picker.ids.ok_button.text = _t("TAMAM")
        picker.ids.cancel_button.text = _t("İPTAL")
        picker.bind(on_save=on_save)
        picker.open()
        return picker

    def open_custom_history_range(self, container):
        """Başlangıç ve bitiş tarihlerini ardışık seçtirir."""
        today = datetime.now().date()
        suggested_start = today - timedelta(days=30)

        def start_selected(_picker, start_date, _date_range):
            def end_selected(_end_picker, end_date, _end_range):
                self._load_history_range(
                    container, start_date.isoformat(), end_date.isoformat()
                )

            self._open_date_picker(today, end_selected)

        self._open_date_picker(suggested_start, start_selected)

    def _load_history_range(self, container, from_date, to_date):
        """Keyfî tarih aralığını arka planda hesaplayıp mevcut renderer'a verir."""
        container.clear_widgets()
        container.add_widget(MDLabel(
            text=_t("Defter okunuyor..."),
            theme_text_color="Secondary",
            halign="center",
        ))
        if self._history_dialog is not None:
            self._history_dialog.title = _t(
                f"Bakiye Geçmişi ({from_date} → {to_date})"
            )

        def work():
            try:
                from services.history_service import diff_between
                result = diff_between(from_date, to_date)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Özel tarih aralığı okunamadı")
                Clock.schedule_once(
                    lambda dt: self._render_history_error(container), 0
                )
                return
            Clock.schedule_once(
                lambda dt: self._render_history(container, result), 0
            )

        threading.Thread(target=work, daemon=True).start()

    def open_balance_at_picker(self, container):
        """Tek bir günün kapanış bakiyesini seçtirir."""
        def selected(_picker, selected_date, _date_range):
            self._load_balance_at(container, selected_date.isoformat())

        self._open_date_picker(datetime.now().date(), selected)

    def _load_balance_at(self, container, selected_date):
        """Point-in-time sorgusunu arka planda çalıştırır."""
        container.clear_widgets()
        container.add_widget(MDLabel(
            text=_t("Defter okunuyor..."),
            theme_text_color="Secondary",
            halign="center",
        ))
        if self._history_dialog is not None:
            self._history_dialog.title = _t(f"{selected_date} Tarihindeki Bakiye")

        def work():
            try:
                from services.history_service import get_balance_at
                result = get_balance_at(selected_date)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Tarihteki bakiye okunamadı")
                Clock.schedule_once(
                    lambda dt: self._render_history_error(container), 0
                )
                return
            Clock.schedule_once(
                lambda dt: self._render_balance_at(container, result), 0
            )

        threading.Thread(target=work, daemon=True).start()

    def _render_balance_at(self, container, result):
        """get_balance_at çıktısını point-in-time görünümüne basar."""
        try:
            container.clear_widgets()
            if result["basis"] == "before_ledger":
                note = MDLabel(
                    text=_t(
                        f"Bakiye defteri {result.get('ledger_start') or '—'} "
                        f"tarihinde başlıyor; {result['date']} için kayıt yok."
                    ),
                    theme_text_color="Secondary",
                    halign="center",
                )
                note.bind(size=note.setter("text_size"))
                container.add_widget(note)
                return

            container.add_widget(MDLabel(
                text=_fmt(result["total_balance"]),
                font_style="H5",
                bold=True,
                theme_text_color="Primary",
                size_hint_y=None,
                height=dp(44),
            ))
            details = MDLabel(
                text=_t(
                    f"{result['date']} gün sonu\n"
                    f"Birikim hedefleri: {_fmt(result['savings_total'])}\n"
                    f"Kaynak: {'Günlük snapshot' if result['basis'] == 'snapshot' else 'Defter replay'}"
                ),
                font_style="Caption",
                theme_text_color="Secondary",
            )
            details.bind(size=details.setter("text_size"))
            container.add_widget(details)
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Tarihteki bakiye çizilemedi")

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
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Bakiye geçmişi çizilemedi")
