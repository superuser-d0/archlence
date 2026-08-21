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
from services.search_service import ACCOUNT, CATEGORY, TRANSACTION, search


MAX_VISIBLE_RESULTS = 5


_ROW_HEIGHT = 72


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


        if not str(value or "").strip():
            self.clear_home_search_results()
            return

        event = None

        def _run_if_current(_dt):


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


                secondary_text=_t("Hesap, kategori ve son işlemlerde arandı"),
            )


            item._no_ripple_effect = True
            panel.add_widget(item)
            panel.height = dp(_ROW_HEIGHT)
            return

        for result in results[:MAX_VISIBLE_RESULTS]:
            panel.add_widget(self._build_result_row(result))
        panel.height = dp(_ROW_HEIGHT) * min(
            len(results), MAX_VISIBLE_RESULTS
        )


    _KIND_LABELS = {
        ACCOUNT: "Hesap",
        CATEGORY: "Kategori",
        TRANSACTION: "İşlem",
    }

    def _build_result_row(self, result):
        kind = result.get("kind")
        item = TwoLineListItem(
            text=str(result.get("name") or ""),
            secondary_text=_t(self._KIND_LABELS.get(kind, "Kategori")),
        )


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
        kind = result.get("kind")
        if kind == ACCOUNT:
            nav.switch_tab("accounts_tab")
        elif kind == TRANSACTION:


            nav.switch_tab("home_tab")
        else:
            nav.switch_tab("settings_tab")


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
