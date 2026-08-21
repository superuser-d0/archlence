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
from utils.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
import ui.theme as ftheme
from ui.i18n import tr as _t, trf as _tf


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


_MONTH_NAMES = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
_WEEKDAY_NAMES = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
]


def _english_ordinal(day):
    """Return the standard English ordinal for a day of the month."""
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _renewal_description(payment):
    """Build a natural English renewal description for a subscription."""
    import datetime

    frequency = payment.get("frequency")
    raw_date = str(payment.get("next_due_date") or "")
    try:
        due = datetime.date.fromisoformat(raw_date[:10])
    except ValueError:
        return f"{_t(_frequency_label(frequency))}  ·  {_t('Sonraki ödeme:')} {raw_date}"

    day = payment.get("recurrence_day") or due.day
    month_name = _t(_MONTH_NAMES[due.month - 1])

    if frequency == "monthly":
        return f"Renews on the {_english_ordinal(day)} of each month"
    if frequency == "yearly":
        return f"Renews every year on {month_name} {_english_ordinal(day)}"
    if frequency == "weekly":
        weekday = _t(_WEEKDAY_NAMES[due.weekday()])
        return f"Renews every {weekday}"
    freq_label = _t(_frequency_label(frequency))
    return f"{freq_label}  ·  Next: {month_name} {day}"


def _fmt(value):
    """Tutarı Türkçe biçimde yazar (main.py::_fmt_tr ile aynı kural)."""
    return f"₺{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def recurring_candidate_title(candidate) -> str:
    """Abonelik adayı kartının başlık satırı.

    Ad KULLANICI VERİSİ (çevrilmez), sıklık KONTROLLÜ ETİKET (çevrilir).
    Saf fonksiyon: testler metni ÜRETEN kodun kendisini çağırır; üretim
    ifadesini kopyalayan bir test, üretim değiştiğinde sessizce yalan
    söylemeye başlardı.
    """
    return _tf("{name}  ·  {frequency}",
               name=candidate["name"],
               frequency=_t(_frequency_label(candidate["frequency"])))


def recurring_candidate_detail(candidate, format_amount) -> str:
    """Abonelik adayı kartının ayrıntı satırı.

    Tutar biçimlendirmesi ÇAĞIRANDAN geliyor (`format_amount`); bu yardımcı
    para biçimlendirme politikasına karışmıyor.
    """
    return _tf(
        "{amount} × {occurrences} kez  →  ayda {amount_1}\n"
        "Kategori: {category}  ·  Son: {last_seen}",
        amount=format_amount(candidate["average_amount"]),
        occurrences=candidate["occurrences"],
        amount_1=format_amount(candidate["monthly_cost"]),
        category=_t(candidate["category"]),
        last_seen=candidate["last_seen"],
    )


class InsightsMixin:
    """Sağlık skoru + abonelik radarı + anomali uyarılarını yöneten mixin.

    Giriş noktası `refresh_insights()`; anasayfa yenilenirken çağrılır ve üç
    bölümü tek arka plan turunda hesaplar.
    """


    _recurring_candidates = []


    def refresh_insights(self, *args):
        """Üç içgörüyü arka planda hesaplar, sonuçları arayüze basar."""
        self._insights_generation = getattr(
            self, "_insights_generation", 0
        ) + 1
        generation = self._insights_generation

        def work():
            payload = {}


            try:
                from services.insights_service import compute_financial_health_score
                payload["health"] = compute_financial_health_score()
            except Exception as e:
                from utils.logging_config import get_logger
                get_logger().exception("Sağlık skoru hesaplanamadı")
                payload["health_error"] = str(e)
            try:
                from services.insights_service import get_health_history
                payload["health_history"] = get_health_history(limit=30)
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Sağlık skoru geçmişi okunamadı")
                payload["health_history"] = []
            try:
                from services.insights_service import detect_recurring_candidates
                payload["candidates"] = detect_recurring_candidates()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik radarı çalışmadı")
            try:
                from database.db import get_active_recurring_payments
                payload["active_subscriptions"] = get_active_recurring_payments()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Aktif abonelikler okunamadı")
                payload["active_subscriptions"] = []
            try:
                from services.insights_service import detect_anomalies
                payload["anomalies"] = detect_anomalies()
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Anomali tespiti çalışmadı")

            def apply_if_current(_dt):
                if generation == getattr(self, "_insights_generation", 0):
                    self._apply_insights(payload)

            Clock.schedule_once(apply_if_current, 0)

        threading.Thread(target=work, daemon=True).start()

    def _apply_insights(self, payload):
        # These cards are expensive KivyMD trees. Never build them behind a
        # different tab while that tab is animating; retain only the newest
        # payload and retry when Home is actually visible.
        try:
            nav = self.root.ids.bottom_nav


            tab_manager = nav.ids.tab_manager
            current_tab = getattr(tab_manager, "current", None)
        except (AttributeError, KeyError):


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
        if "candidates" in payload or "active_subscriptions" in payload:
            Clock.schedule_once(
                lambda dt: self.render_subscription_overview(
                    payload.get("active_subscriptions", []),
                    payload.get("candidates", []),
                ),
                0,
            )
        if "anomalies" in payload:
            Clock.schedule_once(
                lambda dt: self.render_anomalies(payload["anomalies"]), 0.05
            )


    def render_health_score(self, result):
        """Skoru, etiketini ve bileşen dökümünü anasayfa kartına yazar."""
        try:
            if result.get("insufficient_data"):
                self.render_health_insufficient_data()
                return

            from services.insights_service import score_label

            ids = self.root.ids
            score = result.get("score", 0.0)
            breakdown = result.get("breakdown", {})
            accent = _score_accent(score)
            style = self.theme_cls.theme_style

            ids.health_score_value.text = f"{score:.0f}"
            ids.health_score_value.text_color = ftheme.accent(style, accent)
            ids.health_score_label.text = _t(score_label(score))


            savings = breakdown.get("savings_rate", 0.0) * 100
            debt = breakdown.get("debt_ratio", 0.0) * 100
            volatility = breakdown.get("expense_volatility", 0.0) * 100
            ids.health_breakdown_text.text = _tf(
                "Tasarruf oranı %{savings}  ·  Borç/gelir %{debt}  ·  Gider oynaklığı %{volatility}",
                savings=f"{savings:.0f}",
                debt=f"{debt:.0f}",
                volatility=f"{volatility:.0f}",
            )

            ids.health_score_bar.value = max(0.0, min(100.0, score))
            ids.health_score_bar.color = ftheme.accent(style, accent)
            ids.health_score_bar.opacity = 1
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Sağlık skoru çizilemedi")
            self.render_health_error()

    def render_health_insufficient_data(self):
        """İşlem bulunmamasını hesaplama hatasından ayrı ve dürüst gösterir."""
        try:
            ids = self.root.ids
            ids.health_score_value.text = "--"
            ids.health_score_value.text_color = ftheme.accent(
                self.theme_cls.theme_style, "muted"
            )
            ids.health_score_label.text = _t("Yeterli veri yok")
            ids.health_breakdown_text.text = _t(
                "Skor hesaplamak için henüz yeterli veri yok. "
                "Birkaç işlem ekleyince burada görünecek."
            )
            ids.health_score_bar.value = 0
            ids.health_score_bar.opacity = 0
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Sağlık skoru veri-yok durumu çizilemedi")

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
            ids.health_score_bar.opacity = 1
        except Exception:
            from utils.logging_config import get_logger
            get_logger().exception("Sağlık skoru hata durumu çizilemedi")


    def render_subscription_overview(self, active_subscriptions, candidates):
        """Aktif kayıtları önde, radar adaylarını onların altında gösterir."""
        subs = active_subscriptions or []
        self._active_subscriptions = [s for s in subs if s.get("transaction_type") != "income"]
        self._active_incomes = [s for s in subs if s.get("transaction_type") == "income"]
        self.render_recurring_candidates(candidates)
        self.render_active_incomes()

    def _subscription_row_data(self, payment):
        """Bir kaydı `SubscriptionRow`'un beklediği RecycleView sözlüğüne çevirir.

        Widget kurmaz — RecycleView satırları geri dönüştürdüğü için burada
        yalnızca VERİ hazırlanır; çizimi satır bileşeni yapar.
        """
        from services.brand_icon_service import resolve_cached_brand_icon_path

        name = payment.get("name", "")
        return {
            "name": name,
            "amount_text": _fmt(payment["amount"]),
            "renewal_text": _renewal_description(payment),
            "icon_source": resolve_cached_brand_icon_path(name) or "",
            "is_income": payment.get("transaction_type") == "income",
            "payment": payment,
        }

    def render_active_incomes(self):
        try:
            recycler = self.root.ids.active_incomes_rv
            container = self.root.ids.active_incomes_container
        except (AttributeError, KeyError):


            return

        container.clear_widgets()
        incomes = getattr(self, "_active_incomes", [])
        recycler.data = [self._subscription_row_data(p) for p in incomes]

        if not incomes:
            container.add_widget(self._empty_label("Aktif geliriniz bulunmuyor."))

    def render_recurring_candidates(self, candidates):
        """Aktif abonelikler ve varsa yeni istatistiksel adayları birlikte basar.

        Aktif abonelikler RecycleView'e (veri), radar adayları ve etiketler
        alttaki kutuya (widget) gider.
        """
        try:
            recycler = self.root.ids.active_subscriptions_rv
            container = self.root.ids.recurring_candidates_container
        except (AttributeError, KeyError):

            return

        container.clear_widgets()
        self._recurring_candidates = list(candidates or [])

        recycler.data = [
            self._subscription_row_data(payment)
            for payment in getattr(self, "_active_subscriptions", [])
        ]

        if not self._recurring_candidates and not getattr(
                self, "_active_subscriptions", []):
            container.add_widget(self._empty_label(
                "Aktif aboneliğiniz bulunmuyor."))
            return
        if not self._recurring_candidates:
            from services.brand_icon_service import (
                classify_brand,
                resolve_cached_brand_icon_path,
            )
            missing_active = {
                payment["name"]
                for payment in getattr(self, "_active_subscriptions", [])
                if classify_brand(payment.get("name", ""))[0]
                and not resolve_cached_brand_icon_path(payment.get("name", ""))
            }
            if missing_active:
                self._prefetch_candidate_brand_icons(missing_active)
            return


        total = sum(c["monthly_cost"] for c in self._recurring_candidates)
        summary = MDLabel(
            text=_tf(
                "Aylık toplam {amount} tutarında {count} olası abonelik bulundu.",
                amount=_fmt(total),
                count=len(self._recurring_candidates),
            ),
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint_y=None,
            height="32dp",
        )
        summary.bind(size=summary.setter("text_size"))
        container.add_widget(summary)

        for cand in self._recurring_candidates:
            container.add_widget(self._build_candidate_card(cand))

        from services.brand_icon_service import (
            classify_brand,
            resolve_cached_brand_icon_path,
        )
        missing_brands = {
            cand["name"]
            for cand in self._recurring_candidates
            if classify_brand(cand.get("name", ""))[0]
            and not resolve_cached_brand_icon_path(cand.get("name", ""))
        }
        missing_brands.update({
            payment["name"]
            for payment in getattr(self, "_active_subscriptions", [])
            if classify_brand(payment.get("name", ""))[0]
            and not resolve_cached_brand_icon_path(payment.get("name", ""))
        })
        if missing_brands:
            self._prefetch_candidate_brand_icons(missing_brands)

    def _build_candidate_card(self, cand):
        card = ftheme.apply_card_theme(
            MDCard(orientation="vertical", padding="12dp", spacing="6dp",
                   size_hint_y=None, height="112dp", radius=[16]),
            self.theme_cls, tint="amber")

        title_row = MDBoxLayout(
            orientation="horizontal", spacing="8dp",
            size_hint_y=None, height="24dp",
        )
        from services.brand_icon_service import resolve_cached_brand_icon_path
        brand_icon = resolve_cached_brand_icon_path(cand.get("name", ""))
        if brand_icon:
            from kivymd.uix.fitimage import FitImage
            from kivy.metrics import dp
            title_row.add_widget(FitImage(
                source=brand_icon,
                radius=[dp(7)] * 4,
                size_hint=(None, None),
                size=(dp(24), dp(24)),
            ))

        title = MDLabel(
            text=recurring_candidate_title(cand),
            font_style="Subtitle2", bold=True,
            size_hint_y=None, height="24dp")
        title_row.add_widget(title)
        card.add_widget(title_row)

        detail = MDLabel(
            text=recurring_candidate_detail(cand, _fmt),
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

    def _prefetch_candidate_brand_icons(self, brand_names):
        """Radar marka ikonlarını indirir; başarı varsa mevcut adayları yeniler."""
        from services.brand_icon_service import fetch_and_cache_brand_icon

        def worker():
            any_success = False
            for name in brand_names:
                if fetch_and_cache_brand_icon(name):
                    any_success = True
            if any_success:


                Clock.schedule_once(
                    lambda dt: self.render_subscription_overview(
                        list(getattr(self, "_active_subscriptions", []))
                        + list(getattr(self, "_active_incomes", [])),
                        self._recurring_candidates,
                    ),
                    0,
                )

        threading.Thread(target=worker, daemon=True).start()

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


                    auto_deduct=0,
                )
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Abonelik eklenemedi")
                Clock.schedule_once(lambda dt: toast(_t("Abonelik eklenemedi.")), 0)
                return

            Clock.schedule_once(lambda dt: toast(_tf("{name} takibe alındı.", name=cand['name'])), 0)
            Clock.schedule_once(lambda dt: self.refresh_insights(), 0)

        threading.Thread(target=work, daemon=True).start()

    def dismiss_recurring_candidate(self, cand):
        """Adayı kalıcı olarak reddeder; radar bir daha önermez."""
        def work():
            try:
                from services.insights_service import dismiss_recurring_candidate
                dismiss_recurring_candidate(cand["key"])
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Aday reddedilemedi")
                return
            Clock.schedule_once(lambda dt: self.refresh_insights(), 0)

        threading.Thread(target=work, daemon=True).start()

    # ─── 3. Anomalies ────────────────────────────────────────────────────────

    def render_anomalies(self, anomalies):
        """Olağandışı harcamaları uyarı kartı olarak basar (en fazla 5)."""
        try:
            container = self.root.ids.anomalies_container
        except (AttributeError, KeyError):

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
            text=_tf(
                "{category} · {amount}\nBu kategorideki ortalamanın {amount_1} üzerinde ({date})",
                category=


        _t(anomaly['category']),
                amount=_fmt(anomaly['amount']),
                amount_1=_fmt(anomaly['deviation']),
                date=anomaly['date'],
            ),
            font_style="Caption",
            theme_text_color="Secondary",
        )
        text.bind(size=text.setter("text_size"))
        card.add_widget(text)
        card.add_widget(MDFlatButton(
            text=_t("GÖRDÜM"),
            theme_text_color="Custom",
            text_color=ftheme.accent(self.theme_cls.theme_style, "muted"),
            on_release=lambda _button, item=anomaly: self.dismiss_anomaly(item),
        ))
        return card

    def dismiss_anomaly(self, anomaly):
        """Anomali kartını kaynak transaction kimliğiyle kalıcı gizler."""
        def work():
            try:
                from services.insights_service import dismiss_anomaly
                dismiss_anomaly(anomaly["id"])
            except Exception:
                from utils.logging_config import get_logger
                get_logger().exception("Anomali gizlenemedi")
                return
            Clock.schedule_once(lambda dt: self.refresh_insights(), 0)

        threading.Thread(target=work, daemon=True).start()

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
