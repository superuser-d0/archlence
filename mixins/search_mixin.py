"""Ana sayfa arama çubuğunun davranışı.

Bu çubuk uzun süre hiçbir işleyiciye bağlı DEĞİLDİ ve kullanıcı tarafından
"hiçbir şekilde çalışmıyor" diye bildirildi; tek kapısı yalnızca nasıl
göründüğünü ölçüyordu. Bu dosya ona bir davranış veriyor.

SONUÇLAR MODAL DEĞİL, SATIR İÇİ. `MDDropdownMenu` denemeye değmezdi: KivyMD
1.2'de menü bir `ModalView` üzerine kuruluyor ve açılınca dokunuş/odak
yakalıyor. Her tuş vuruşunda menüyü yeniden açmak, kullanıcının ikinci
karakteri yazamaması demekti. Sonuçlar bu yüzden başlığın hemen altındaki
normal bir kutuya çiziliyor — odak `TextInput`'ta kalıyor.
"""

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.list import TwoLineListItem

from ui.i18n import tr as _t
from services.search_service import ACCOUNT, search

#: Panelde aynı anda görünecek en fazla satır. Daha uzunu başlığın altını
#: kaplayıp sayfayı ittiriyor; kullanıcı yazmaya devam ederek daraltır.
MAX_VISIBLE_RESULTS = 5

#: `TwoLineListItem`'ın KivyMD 1.2'deki varsayılan yüksekliği.
_ROW_HEIGHT = 72

#: Yazmayı bitirene kadar bekle. budget_mixin/asset_mixin ile aynı değer;
#: her tuşta DB'ye gitmek o iki kutuda ölçülmüş bir kasma sebebiydi.
_DEBOUNCE_SECONDS = 0.3


class SearchMixin:

    def focus_home_search(self):
        """Büyüteç düğmesi — alanı odaklar.

        Kullanıcının "arama butonu çalışmıyor" derken tıkladığı şey buydu:
        eskiden `MDIcon`'du, yani `ButtonBehavior` mirası olmayan salt çizim.
        Artık `MDIconButton` ve en azından imleci alana koyuyor.
        """
        field = self.root.ids.get("home_search_input") if self.root else None
        if field is not None:
            field.focus = True

    def on_home_search_text(self, _field, value):
        """Her tuş vuruşunda çağrılır; asıl aramayı geciktirir."""
        pending = getattr(self, "_home_search_event", None)
        if pending is not None:
            pending.cancel()
        self._home_search_event = None

        # Alan temizlendiyse BEKLEME: panel hemen kapansın, yoksa 300ms
        # boyunca eski sonuçlar boş kutunun altında asılı kalıyor.
        if not str(value or "").strip():
            self.clear_home_search_results()
            return

        event = None

        def _run_if_current(_dt):
            # Jenerasyon kontrolü: bu olay hâlâ EN SON planlanan mı? Kullanıcı
            # beklerken yazmaya devam ettiyse eski sorgu sonuçları yeniyi
            # ezmemeli.
            if getattr(self, "_home_search_event", None) is event:
                self._home_search_event = None
                self.run_home_search(value)

        event = Clock.schedule_once(_run_if_current, _DEBOUNCE_SECONDS)
        self._home_search_event = event

    def run_home_search(self, query):
        """Aramayı koşturur ve paneli doldurur."""
        panel = self.root.ids.get("home_search_results") if self.root else None
        if panel is None:
            return
        results = search(query)
        panel.clear_widgets()

        if not results:
            item = TwoLineListItem(
                text=_t("Sonuç bulunamadı"),
                secondary_text=_t("Hesap ve kategori adlarında arandı"),
            )
            # Bulunamadı satırı bir HEDEF DEĞİL; tıklanınca hiçbir yere
            # gitmemeli. `_no_ripple_effect` KivyMD'nin dalga animasyonunu da
            # kapatıyor, böylece tıklanabilir görünmüyor.
            item._no_ripple_effect = True
            panel.add_widget(item)
            panel.height = dp(_ROW_HEIGHT)
            return

        for result in results[:MAX_VISIBLE_RESULTS]:
            panel.add_widget(self._build_result_row(result))
        panel.height = dp(_ROW_HEIGHT) * min(
            len(results), MAX_VISIBLE_RESULTS
        )

    def _build_result_row(self, result):
        is_account = result.get("kind") == ACCOUNT
        item = TwoLineListItem(
            text=str(result.get("name") or ""),
            secondary_text=(
                _t("Hesap") if is_account else _t("Kategori")
            ),
        )
        # `result=result` ŞART: döngü değişkenini yakalamak, tüm satırların
        # son sonuca gitmesi demekti (Python'da klasik geç-bağlama tuzağı).
        item.bind(
            on_release=lambda _item, result=result:
                self.open_search_result(result)
        )
        return item

    def open_search_result(self, result):
        """Sonuca tıklanınca ilgili sekmeye götürür ve paneli kapatır."""
        nav = self.root.ids.get("bottom_nav") if self.root else None
        if nav is None:
            return
        if result.get("kind") == ACCOUNT:
            nav.switch_tab("accounts_tab")
        else:
            nav.switch_tab("settings_tab")
            # Kategori listesi tür başına yükleniyor; sonucun kendi türünü
            # açmazsak kullanıcı gelir kategorisi arayıp gider listesine
            # düşerdi.
            category_type = result.get("detail") or "expense"
            self.load_categories(category_type)
        self.clear_home_search_results()

    def clear_home_search_results(self):
        """Paneli kapatır ve arama alanını temizler.

        Yükseklik 0 ve widget'lar silinmiş olmalı: yalnız yüksekliği
        sıfırlamak satırları görünmez ama HÂLÂ TIKLANABİLİR bırakıyordu
        (aynı sınıf hata bu turda boş kartlarda da düzeltilmişti).
        """
        pending = getattr(self, "_home_search_event", None)
        if pending is not None:
            pending.cancel()
        self._home_search_event = None
        panel = self.root.ids.get("home_search_results") if self.root else None
        if panel is not None:
            panel.clear_widgets()
            panel.height = 0
