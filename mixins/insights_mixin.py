"""Faz 1 içgörü arayüzü: finansal sağlık skoru, abonelik radarı, anomaliler.

Hesaplamanın tamamı services/insights_service.py'de; bu mixin yalnızca onu
çağırıp sonucu arayüze basar. debt_mixin.py / recurring_mixin.py'deki
thread+Clock kalıbını izler: DB okuma + decrypt arka planda, widget dokunuşu
Clock.schedule_once ile ana thread'de.

Şifreli sütunlar yüzünden hesap SQL'de yapılamadığı için (bkz. insights_service
modül docstring'i) iş yükü Python'da; işlem sayısı arttıkça bu birkaç yüz ms
sürebilir, o yüzden açılışta senkron çağrılmaz.
"""
import threading

from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
import ui.theme as ftheme
from ui.i18n import tr as _t


# Sağlık skoru bandı -> ftheme anlamsal renk adı. Renk doğrudan yazılmaz ki
# karanlık/açık tema geçişinde token katmanı devrede kalsın.
def _score_accent(score):
    if score >= 60:
        return "green"
    if score >= 40:
        return "amber"
    return "red"


def _frequency_label(frequency):
    """Servisin döndürdüğü sıklık anahtarını Türkçeye çevirir."""
    return {
        "weekly": "haftalık",
        "biweekly": "iki haftada bir",
        "monthly": "aylık",
        "quarterly": "üç ayda bir",
        "yearly": "yıllık",
    }.get(frequency, frequency)


def _fmt(value):
    """Tutarı Türkçe biçimde yazar (main.py::_fmt_tr ile aynı kural)."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class InsightsMixin:
    """Sağlık skoru + abonelik radarı + anomali uyarılarını yöneten mixin.

    Giriş noktası `refresh_insights()`; anasayfa yenilenirken çağrılır ve üç
    bölümü tek arka plan turunda hesaplar.
    """

    # Radarın son turda bulduğu adaylar; "Aboneliğe Ekle" ve "Yoksay"
    # butonları bu listeden çalışır.
    _recurring_candidates = []

    # ─── Giriş noktası ───────────────────────────────────────────────────────

    def refresh_insights(self, *args):
        """Üç içgörüyü arka planda hesaplar, sonuçları arayüze basar."""
        def work():
            payload = {}
            # Üç hesap birbirinden bağımsız: biri patlarsa diğerleri yine
            # görünsün diye ayrı ayrı korunuyor.
            try:
                from services.insights_service import compute_financial_health_score
                payload["health"] = compute_financial_health_score()
            except Exception as e:
                print("Sağlık skoru hesaplanamadı:", e)
                payload["health_error"] = str(e)
            try:
                from services.insights_service import detect_recurring_candidates
                payload["candidates"] = detect_recurring_candidates()
            except Exception as e:
                print("Abonelik radarı çalışmadı:", e)
            try:
                from services.insights_service import detect_anomalies
                payload["anomalies"] = detect_anomalies()
            except Exception as e:
                print("Anomali tespiti çalışmadı:", e)

            Clock.schedule_once(lambda dt: self._apply_insights(payload), 0)

        threading.Thread(target=work, daemon=True).start()

    def _apply_insights(self, payload):
        # These cards are expensive KivyMD trees. Never build them behind a
        # different tab while that tab is animating; retain only the newest
        # payload and retry when Home is actually visible.
        try:
            nav = self.root.ids.bottom_nav
            # KivyMD 1.x, sekmeleri MDBottomNavigation'ın içindeki
            # ``ids.tab_manager`` ScreenManager'ında tutar. Bu sürümde
            # ``get_current_tab()`` yok; onu çağırmak AttributeError üretip
            # payload'ın sonsuza kadar ertelenmesine, kartın da
            # "Hesaplanıyor..." durumunda kalmasına yol açıyordu.
            tab_manager = nav.ids.tab_manager
            current_tab = getattr(tab_manager, "current", None)
        except Exception:
            current_tab = None
        if current_tab != "home_tab":
            self._pending_insights_payload = payload
            pending = getattr(self, "_pending_insights_event", None)
            if pending is not None:
                pending.cancel()
            self._pending_insights_event = Clock.schedule_once(
                lambda dt: self._apply_insights(
                    getattr(self, "_pending_insights_payload", payload)
                ), 0.5
            )
            return

        self._pending_insights_event = None
        if "health" in payload:
            self.render_health_score(payload["health"])
        elif "health_error" in payload:
            self.render_health_error()
        if "candidates" in payload:
            Clock.schedule_once(
                lambda dt: self.render_recurring_candidates(payload["candidates"]), 0
            )
        if "anomalies" in payload:
            Clock.schedule_once(
                lambda dt: self.render_anomalies(payload["anomalies"]), 0.05
            )

    # ─── 1. Finansal sağlık skoru ────────────────────────────────────────────

    def render_health_score(self, result):
        """Skoru, etiketini ve bileşen dökümünü anasayfa kartına yazar."""
        try:
            from services.insights_service import score_label

            ids = self.root.ids
            score = result.get("score", 0.0)
            breakdown = result.get("breakdown", {})
            accent = _score_accent(score)
            style = self.theme_cls.theme_style

            ids.health_score_value.text = f"{score:.0f}"
            ids.health_score_value.text_color = ftheme.accent(style, accent)
            ids.health_score_label.text = _t(score_label(score))

            # Bileşenler: kullanıcıya skorun NEDEN o olduğunu göster.
            savings = breakdown.get("savings_rate", 0.0) * 100
            debt = breakdown.get("debt_ratio", 0.0) * 100
            volatility = breakdown.get("expense_volatility", 0.0) * 100
            ids.health_breakdown_text.text = _t(
                f"Tasarruf oranı %{savings:.0f}  ·  "
                f"Borç/gelir %{debt:.0f}  ·  "
                f"Gider oynaklığı %{volatility:.0f}"
            )

            ids.health_score_bar.value = max(0.0, min(100.0, score))
            ids.health_score_bar.color = ftheme.accent(style, accent)
        except Exception as e:
            print("Sağlık skoru çizilemedi:", e)
            self.render_health_error()

    def render_health_error(self):
        """Hesap/çizim hatasında kartı kalıcı yükleniyor durumundan çıkarır."""
        try:
            ids = self.root.ids
            ids.health_score_value.text = "--"
            ids.health_score_value.text_color = ftheme.accent(
                self.theme_cls.theme_style, "red"
            )
            ids.health_score_label.text = _t("Hesaplanamadı")
            ids.health_breakdown_text.text = _t(
                "Finansal sağlık raporu şu anda oluşturulamadı. "
                "Ana sayfayı yenileyerek tekrar deneyebilirsin."
            )
            ids.health_score_bar.value = 0
            ids.health_score_bar.color = ftheme.accent(
                self.theme_cls.theme_style, "red"
            )
        except Exception as e:
            print("Sağlık skoru hata durumu çizilemedi:", e)

    # ─── 2. Abonelik radarı ("sessiz sızıntı") ───────────────────────────────

    def render_recurring_candidates(self, candidates):
        """Tespit edilen abonelik adaylarını kart listesi olarak basar."""
        try:
            container = self.root.ids.recurring_candidates_container
        except Exception:
            return

        container.clear_widgets()
        self._recurring_candidates = list(candidates or [])

        if not self._recurring_candidates:
            container.add_widget(self._empty_label(
                "Tespit edilen gizli abonelik yok."))
            return

        # Toplam sızıntıyı en üstte özetle — asıl mesaj bu.
        total = sum(c["monthly_cost"] for c in self._recurring_candidates)
        summary = MDLabel(
            text=_t(f"Aylık toplam {_fmt(total)} tutarında {len(self._recurring_candidates)} "
                    f"olası abonelik bulundu."),
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint_y=None,
            height="32dp",
        )
        summary.bind(size=summary.setter("text_size"))
        container.add_widget(summary)

        for cand in self._recurring_candidates:
            container.add_widget(self._build_candidate_card(cand))

    def _build_candidate_card(self, cand):
        card = ftheme.apply_card_theme(
            MDCard(orientation="vertical", padding="12dp", spacing="6dp",
                   size_hint_y=None, height="112dp", radius=[16]),
            self.theme_cls, tint="amber")

        title = MDLabel(
            text=_t(f"{cand['name']}  ·  {_frequency_label(cand['frequency'])}"),
            font_style="Subtitle2", bold=True,
            size_hint_y=None, height="24dp")
        card.add_widget(title)

        detail = MDLabel(
            text=_t(f"{_fmt(cand['average_amount'])} × {cand['occurrences']} kez  →  "
                    f"ayda {_fmt(cand['monthly_cost'])}\n"
                    f"Kategori: {cand['category']}  ·  Son: {cand['last_seen']}"),
            font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height="40dp")
        detail.bind(size=detail.setter("text_size"))
        card.add_widget(detail)

        actions = MDBoxLayout(orientation="horizontal", spacing="8dp",
                              size_hint_y=None, height="36dp")
        if cand.get("can_track", False):
            actions.add_widget(MDFlatButton(
                text=_t("ABONELİĞE EKLE"),
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x, c=cand: self.track_recurring_candidate(c)))
        else:
            # Tekrarlanan ödeme motoru yalnızca aylık/yıllık vade ilerletiyor;
            # bu sıklık takibe alınamaz (bkz. insights_service::can_track).
            note = MDLabel(
                text=_t("Bu sıklık otomatik takibe alınamıyor."),
                font_style="Caption",
                theme_text_color="Hint",
            )
            note.bind(size=note.setter("text_size"))
            actions.add_widget(note)
        actions.add_widget(MDFlatButton(
            text=_t("YOKSAY"),
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "muted"),
            on_release=lambda x, c=cand: self.dismiss_recurring_candidate(c)))
        card.add_widget(actions)
        return card

    def track_recurring_candidate(self, cand):
        """Adayı gerçek bir tekrarlanan ödeme kaydına dönüştürür.

        Kaydı doğrudan burada yazmak yerine mevcut db katmanını çağırırız;
        isim çakışması kontrolü (has_active_recurring_payment) orada.
        """
        def work():
            try:
                from database.db import (
                    has_active_recurring_payment, insert_recurring_payment,
                )
                if has_active_recurring_payment(cand["name"]):
                    Clock.schedule_once(
                        lambda dt: toast(_t("Bu abonelik zaten kayıtlı.")), 0)
                    return
                insert_recurring_payment(
                    name=cand["name"],
                    amount=cand["average_amount"],
                    category=cand["category"],
                    frequency=cand["frequency"],
                    next_due_date=cand["next_due_date"],
                    # Radardan gelen kayıt otomatik para düşmez: tespit bir
                    # tahmindir, kullanıcı onaylamadan hesaptan çekilmemeli.
                    auto_deduct=0,
                )
            except Exception as e:
                print("Abonelik eklenemedi:", e)
                Clock.schedule_once(lambda dt: toast(_t("Abonelik eklenemedi.")), 0)
                return

            Clock.schedule_once(lambda dt: toast(_t(f"{cand['name']} takibe alındı.")), 0)
            Clock.schedule_once(lambda dt: self.refresh_insights(), 0)

        threading.Thread(target=work, daemon=True).start()

    def dismiss_recurring_candidate(self, cand):
        """Adayı kalıcı olarak reddeder; radar bir daha önermez."""
        def work():
            try:
                from services.insights_service import dismiss_recurring_candidate
                dismiss_recurring_candidate(cand["key"])
            except Exception as e:
                print("Aday reddedilemedi:", e)
                return
            Clock.schedule_once(lambda dt: self.refresh_insights(), 0)

        threading.Thread(target=work, daemon=True).start()

    # ─── 3. Anomaliler ───────────────────────────────────────────────────────

    def render_anomalies(self, anomalies):
        """Olağandışı harcamaları uyarı kartı olarak basar (en fazla 5)."""
        try:
            container = self.root.ids.anomalies_container
        except Exception:
            return

        container.clear_widgets()

        if not anomalies:
            container.add_widget(self._empty_label(
                "Olağandışı harcama tespit edilmedi."))
            return

        for anomaly in anomalies[:5]:
            container.add_widget(self._build_anomaly_card(anomaly))

    def _build_anomaly_card(self, anomaly):
        card = ftheme.apply_card_theme(
            MDCard(orientation="horizontal", padding="12dp", spacing="10dp",
                   size_hint_y=None, height="76dp", radius=[16]),
            self.theme_cls, tint="red")

        icon = MDIconButton(
            icon="alert-decagram-outline",
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "red"),
            pos_hint={"center_y": 0.5},
        )
        card.add_widget(icon)

        text = MDLabel(
            text=_t(f"{_t(anomaly['category'])} · {_fmt(anomaly['amount'])}\n"
                    f"Bu kategorideki ortalamanın {_fmt(anomaly['deviation'])} üzerinde "
                    f"({anomaly['date']})"),
            font_style="Caption",
            theme_text_color="Secondary",
        )
        text.bind(size=text.setter("text_size"))
        card.add_widget(text)
        return card

    # ─── Ortak ───────────────────────────────────────────────────────────────

    def _empty_label(self, message):
        lbl = MDLabel(
            text=_t(message),
            theme_text_color="Secondary",
            font_style="Body2",
            halign="center",
            size_hint_y=None,
            height="40dp",
        )
        lbl.bind(size=lbl.setter("text_size"))
        return lbl
