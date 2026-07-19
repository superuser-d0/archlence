import os
import re
from kivy.clock import Clock
from kivymd.toast import toast
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget
from kivymd.uix.label import MDLabel


from data.bist100 import BIST100_STOCKS

# ─── Varlık / Hisse Simgeleri ─────────────────────────────────────────────────
# Varlık türü → Material Design ikon adı
ASSET_TYPE_ICONS = {
    "Hisse": "chart-line",
    "Altın": "gold",
    "Tahvil": "certificate",
    "Döviz": "currency-usd",
    "Kripto": "bitcoin",
    "Diğer": "wallet-outline",
}

# Altın ikonuna özel vurgu rengi (portföy kartı ve diyaloglarda kullanılır)
GOLD_ICON_COLOR = (0.85, 0.65, 0.13, 1)

# BIST hissesi → sektör ikonu (eşleşmeyenler "chart-line" alır)
_SECTOR_ICON_GROUPS = {
    "bank": ["AKBNK", "ALBRK", "GARAN", "HALKB", "ISCTR", "SKBNK", "TSKB", "VAKBN", "YKBNK"],
    "finance": ["ISFIN", "ISMEN", "TURSG"],
    "currency-usd": ["USDTR"],
    "lightning-bolt": ["AKSEN", "AYDEM", "BIOEN", "CONSE", "EUPWR", "IPEKE", "ODAS", "ZOREN", "ASTOR", "GESAN", "KONTR", "EUREN"],
    "solar-power": ["ALFAS", "SMRTG"],
    "wind-turbine": ["GWIND"],
    "gas-cylinder": ["AYGAZ"],
    "fuel": ["TUPRS", "PETKM"],
    "factory": ["AKCNS", "BUCIM", "CIMSA", "GOLTS", "KONYA", "NUHCM", "OYAKC", "LMKDC", "KARTN", "PARSN", "SASA", "SISE"],
    "anvil": ["EREGL", "ISDMR", "KRDMD", "BRSAN", "KCAER", "KOZAL", "PRKME"],
    "gold": ["KOZAA"],
    "cart": ["BIMAS", "MGROS", "SOKM", "TKNSA", "INDES"],
    "food-apple": ["CCOLA", "KAYSE", "TATGD", "TUKAS", "ULKER", "YYLGD"],
    "airplane": ["PGSUS", "THYAO", "TAVHL"],
    "car": ["DOAS", "FROTO", "KARSN", "OTKAR", "TOASO", "TTRAK", "EGEEN"],
    "domain": ["ALARK", "BERA", "DOHOL", "KCHOL", "SAHOL", "POLHO"],
    "cellphone": ["TCELL", "TTKOM", "NETAS"],
    "laptop": ["LOGO", "REEDR", "SMGE"],
    "tshirt-crew": ["MAVI", "KORDS"],
    "hospital-box": ["MPARK"],
    "pill": ["ECILC", "SELEC"],
    "soccer": ["FENER", "TLMAN", "BRYAT"],
    "office-building": ["AKFGY", "ISGYO", "TRGYO", "PKENT"],
    "flask": ["ALKIM", "GUBRF"],
    "television": ["ARCLK", "VESBE", "VESTL"],
    "shield-star": ["ASELS"],
    "pencil": ["ADEL"],
    "texture-box": ["QUAGR"],
    "package-variant": ["PRKAB"],
}
STOCK_SECTOR_ICONS = {
    code: icon for icon, codes in _SECTOR_ICON_GROUPS.items() for code in codes
}


def get_stock_icon(code):
    """BIST hisse kodu için sektör ikonunu döndürür."""
    return STOCK_SECTOR_ICONS.get(code.upper(), "chart-line")


# Gerçek şirket logoları (assets/stock_logos/{KOD}.png); yoksa sektör ikonuna düşülür
STOCK_LOGO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "stock_logos"
)


def get_stock_logo(code):
    """Hisse için indirilen logo dosyasının yolunu döndürür; yoksa None."""
    path = os.path.join(STOCK_LOGO_DIR, f"{code.upper()}.png")
    return path if os.path.exists(path) else None


def format_price_tl(price):
    """1234.5 → '1.234,50 ₺' (Türkçe biçim)."""
    return f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"


def _parse_price_str(s):
    """'400,00' (Türkçe) veya '1,500,000.0000' (eski/İngilizce) gibi bir sayı
    metnini float'a çevirir. Son geçen '.' veya ',' ondalık ayracı kabul edilir."""
    s = s.strip()
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot > last_comma:
        return float(s.replace(",", ""))
    if last_comma > last_dot:
        return float(s.replace(".", "").replace(",", "."))
    return float(s)


_KZ_SUFFIX_RE = re.compile(r'\s*[|(]\s*K/Z:\s*([+-])\s*₺?\s*([\d.,]+)\s*₺?\)?\s*$')
_LEGACY_HISTORY_BODY_RE = re.compile(
    r'^(?P<name>.*?)\s*\((?P<code>[^)]+)\)\s*—\s*'
    r'(?P<qty>[\d.,]+)\s*adet\s*@\s*(?P<price>[\d.,]+)\s*₺\s*$'
)


def _extract_and_strip_kz(text):
    """Açıklama metninin sonundaki K/Z bilgisini (eski '| K/Z: ...' veya yeni
    '(K/Z: ...)' biçimlerinden) ayıklayıp metinden temizler; K/Z yoksa
    (text, None) döner. Ana açıklama artık K/Z ile bölünmüyor, K/Z ayrı bir
    metrik olarak gösterilebiliyor."""
    if not text:
        return text, None
    m = _KZ_SUFFIX_RE.search(text)
    if not m:
        return text, None
    stripped = text[:m.start()].rstrip()
    try:
        kz_amount = _parse_price_str(m.group(2))
    except ValueError:
        return stripped, None
    return stripped, f"K/Z: {m.group(1)}{format_price_tl(kz_amount)}"


def format_history_description(description, category, is_buy):
    """Varlık Geçmişi listesinde gösterilecek açıklamayı profesyonel, akıcı bir
    Türkçe cümleye dönüştürür ve varsa K/Z'yi ayrı döner (ana metinden çıkarılır,
    çağıran taraf bunu ayrı bir metrik olarak — altta/sağda — gösterebilir).

    Yeni kayıtlar zaten bu şablonla ("... alındı/satıldı — N adet, birim fiyat
    X ₺") yazıldığı için burada sadece K/Z ayıklanır. Eski kayıtlardaki teknik
    gösterim ("N adet @ X ₺") da aynı şablona çevrilir. Tanınmayan bir metin
    varsa (K/Z ayıklanmış hâliyle) olduğu gibi döner — asla hata fırlatmaz."""
    raw = description or category
    body, kz_text = _extract_and_strip_kz(raw)

    if body and " adet @ " in body:
        m = _LEGACY_HISTORY_BODY_RE.match(body)
        if m:
            try:
                qty = _parse_price_str(m.group("qty"))
                price = _parse_price_str(m.group("price"))
                verb = "alındı" if is_buy else "satıldı"
                code = m.group("code").replace(".IS", "")
                body = f"{m.group('name').strip()} ({code}) {verb} — {qty:g} adet, birim fiyat {format_price_tl(price)}"
            except ValueError:
                pass

    if body:
        import re
        body = re.sub(r'\s*\([^)]+\)', '', body)

    return body, kz_text


def get_asset_icon(asset_type, asset_code=""):
    """Varlık türü (Hisse ise sembolüne göre) için ikon adını döndürür."""
    if asset_type == "Hisse" and asset_code:
        return get_stock_icon(asset_code)
    return ASSET_TYPE_ICONS.get(asset_type, "wallet-outline")


_HISTORY_CODE_RE = re.compile(r'\(([^)]+)\)')


def _extract_history_asset_code(description):
    """'Aselsan (ASELS.IS) — ...' gibi Varlık Geçmişi açıklama metninden
    parantez içindeki sembolü çıkarır; formata uymazsa None döner (bu durumda
    logo aranmaz, mevcut MDI ikon fallback'i kullanılır)."""
    if not description:
        return None
    m = _HISTORY_CODE_RE.search(description)
    return m.group(1) if m else None


def resolve_history_logo_source(description):
    """Varlık Geçmişi satırı için gösterilecek logo dosya yolunu döndürür
    (AĞ ÇAĞRISI YOK, sadece yerel disk kontrolü — UI thread'inden güvenle
    çağrılabilir). Önce BIST hissesi yerel logosunu, sonra Kripto/Döviz için
    önbelleğe alınmış uzak logoyu dener. Hiçbiri yoksa (None, code) döner —
    code doluysa arka planda indirme denemesi için kullanılabilir."""
    code = _extract_history_asset_code(description)
    if not code:
        return None, None

    bare_code = code.split(".")[0]  # "ASELS.IS" -> "ASELS"
    local_logo = get_stock_logo(bare_code)
    if local_logo:
        return local_logo, None  # bulundu, indirme gerekmiyor

    from services.logo_service import resolve_cached_logo_path
    cached = resolve_cached_logo_path(code)
    if cached:
        return cached, None

    return None, code  # bulunamadı; code doluysa arka planda denenebilir


# Tür seçim dropdown'ında ikon gösterebilen menü öğesi
from kivy.lang import Builder as _Builder
from kivy.factory import Factory as _Factory
from kivy.properties import StringProperty as _StringProperty
from kivymd.uix.list import OneLineIconListItem as _OneLineIconListItem

_Builder.load_string("""
<AssetTypeMenuItem>:
    IconLeftWidget:
        icon: root.icon
        theme_text_color: "Custom"
        text_color: (0.85, 0.65, 0.13, 1) if root.icon == "gold" else (0.08, 0.72, 0.42, 1)
""")


class AssetTypeMenuItem(_OneLineIconListItem):
    icon = _StringProperty("wallet-outline")


_Factory.register("AssetTypeMenuItem", cls=AssetTypeMenuItem)


class AssetMixin:
    def show_add_asset_dialog(self):
        """Varlık türü seçim diyaloğunu açar. Hisse için BIST100 picker'a yönlendirir."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.menu import MDDropdownMenu

        ASSET_TYPES = ["Hisse", "Altın", "Tahvil", "Döviz", "Kripto", "Diğer"]
        self._asset_selected_type = ASSET_TYPES[0]

        content = MDBoxLayout(
            orientation="vertical",
            spacing="14dp",
            size_hint_y=None,
            height="80dp",
            padding=["0dp", "8dp", "0dp", "0dp"]
        )

        from kivymd.uix.label import MDLabel
        hint_lbl = MDLabel(
            text="Portföyünüze eklemek istediğiniz varlık türünü seçin.",
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint_y=None,
            height="40dp",
        )

        type_btn = MDRaisedButton(
            text=f"Tür Seç: {self._asset_selected_type}",
            size_hint_x=1,
            md_bg_color=(0.08, 0.72, 0.42, 1),
        )

        menu_items = [
            {
                "viewclass": "AssetTypeMenuItem",
                "text": t,
                "icon": ASSET_TYPE_ICONS.get(t, "wallet-outline"),
                "on_release": lambda x=t, btn=type_btn: self._select_asset_type_main(x, btn),
            }
            for t in ASSET_TYPES
        ]
        self._asset_type_menu = MDDropdownMenu(
            caller=type_btn,
            items=menu_items,
            width_mult=3,
        )
        type_btn.bind(on_release=lambda x: self._asset_type_menu.open())

        content.add_widget(hint_lbl)
        content.add_widget(type_btn)

        self.asset_type_dialog = MDDialog(
            title="Yeni Varlık Ekle",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="İPTAL",
                    on_release=lambda x: self.asset_type_dialog.dismiss()
                ),
                MDRaisedButton(
                    text="DEVAM",
                    md_bg_color=(0.08, 0.72, 0.42, 1),
                    on_release=lambda x: self._on_asset_type_confirmed(),
                ),
            ],
        )
        self.asset_type_dialog.open()

    def _select_asset_type_main(self, asset_type, button):
        """Tür seçim diyaloğundaki dropdown için handler."""
        self._asset_selected_type = asset_type
        button.text = f"Tür Seç: {asset_type}"
        self._asset_type_menu.dismiss()

    def _on_asset_type_confirmed(self):
        """Tür seçildikten sonra: Hisse ise BIST100 picker, değilse normal form."""
        self.asset_type_dialog.dismiss()
        if self._asset_selected_type == "Hisse":
            Clock.schedule_once(lambda dt: self._show_bist100_picker(), 0.15)
        elif self._asset_selected_type == "Kripto":
            Clock.schedule_once(lambda dt: self._show_crypto_picker(), 0.15)
        else:
            Clock.schedule_once(lambda dt: self._show_other_asset_dialog(), 0.15)

    def _show_bist100_picker(self):
        """BIST 100 hisse listesini arama destekli MDDialog'da gösterir."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.scrollview import MDScrollView
        from kivymd.uix.list import MDList, TwoLineAvatarIconListItem, IconLeftWidget, ImageLeftWidget
        import time
        from services.asset_service import fetch_bist100_prices

        self._bist_selected_code = None
        self._bist_selected_name = None

        # Ana layout
        content = MDBoxLayout(
            orientation="vertical",
            spacing="8dp",
            size_hint_y=None,
            height="420dp",
            padding=["0dp", "4dp", "0dp", "0dp"],
        )

        # Arama kutusu
        search_field = MDTextField(
            hint_text="Ara: Hisse adı veya sembol...",
            size_hint_x=1,
            size_hint_y=None,
            height="48dp",
        )

        # Kaydırılabilir liste
        scroll = MDScrollView(size_hint=(1, 1))
        self._bist_list_widget = MDList()
        scroll.add_widget(self._bist_list_widget)

        content.add_widget(search_field)
        content.add_widget(scroll)

        def _build_list(query=""):
            self._bist_list_widget.clear_widgets()
            query_lower = query.strip().lower()
            prices = getattr(self, "_bist_prices", {})
            for code, name in BIST100_STOCKS:
                if query_lower and query_lower not in code.lower() and query_lower not in name.lower():
                    continue
                price = prices.get(code)
                price_text = f"   [color=#14B85F]{format_price_tl(price)}[/color]" if price else ""
                item = TwoLineAvatarIconListItem(
                    text=f"[b]{code}[/b]{price_text}",
                    secondary_text=name,
                )
                logo = get_stock_logo(code)
                if logo:
                    item.add_widget(ImageLeftWidget(source=logo))
                else:
                    item.add_widget(IconLeftWidget(
                        icon=get_stock_icon(code),
                        theme_text_color="Custom",
                        text_color=(0.08, 0.72, 0.42, 1),
                    ))
                # markup için
                try:
                    item.ids._lbl_primary.markup = True
                except Exception:
                    pass
                # Yeniden çizimde mevcut seçimi vurgulu tut
                if code == self._bist_selected_code:
                    try:
                        item.bg_color = (0.08, 0.72, 0.42, 0.15)
                    except Exception:
                        pass

                def _on_select(inst, c=code, n=name):
                    self._bist_selected_code = c
                    self._bist_selected_name = n
                    # Seçimi görsel olarak vurgula
                    for child in self._bist_list_widget.children:
                        try:
                            child.bg_color = (0, 0, 0, 0)
                        except Exception:
                            pass
                    try:
                        inst.bg_color = (0.08, 0.72, 0.42, 0.15)
                    except Exception:
                        pass

                item.bind(on_release=_on_select)
                self._bist_list_widget.add_widget(item)

        _build_list()

        self._bist_search_event = None

        def _on_search(instance, value):
            # Her tuş vuruşunda listeyi yeniden çizmek 100 kalemlik listede
            # arama kutusunun kasmasına yol açıyordu; kullanıcı yazmayı
            # bitirene kadar (300ms sessizlik) yeniden çizimi ertele.
            if self._bist_search_event:
                self._bist_search_event.cancel()
            self._bist_search_event = Clock.schedule_once(
                lambda dt: _build_list(value), 0.3
            )

        search_field.bind(text=_on_search)

        # ── Anlık fiyatları arka planda çek (5 dk önbellekli) ────────────────
        cache_age = time.time() - getattr(self, "_bist_price_time", 0)
        if cache_age > 300:
            def _on_prices(prices):
                if not prices:
                    return
                self._bist_prices = prices
                self._bist_price_time = time.time()

                def _refresh(dt):
                    try:
                        _build_list(search_field.text)
                    except Exception as e:
                        print("BIST liste yenileme hatası:", e)

                Clock.schedule_once(_refresh, 0)

            fetch_bist100_prices([c for c, _ in BIST100_STOCKS], _on_prices)

        def _confirm_stock(instance):
            if not self._bist_selected_code:
                toast("Lütfen bir hisse seçin!")
                return
            self._bist_dialog.dismiss()
            Clock.schedule_once(
                lambda dt: self._show_stock_price_dialog(
                    self._bist_selected_code,
                    self._bist_selected_name
                ), 0.15
            )

        self._bist_dialog = MDDialog(
            title="BIST 100 — Hisse Seç",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="GERİ",
                    on_release=lambda x: (self._bist_dialog.dismiss(),
                                          Clock.schedule_once(lambda dt: self.show_add_asset_dialog(), 0.15)),
                ),
                MDFlatButton(
                    text="SEÇ  ✓",
                    theme_text_color="Custom",
                    text_color=(0.08, 0.72, 0.42, 1),
                    on_release=_confirm_stock,
                ),
            ],
        )
        self._bist_dialog.open()

    def _show_stock_price_dialog(self, code, name):
        """Hisse seçildikten sonra alım fiyatı ve lot/miktar giriş diyaloğu."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel

        self._asset_selected_type = "Hisse"
        self._asset_name_input_val = name
        self._asset_code_input_val = code

        content = MDBoxLayout(
            orientation="vertical",
            spacing="12dp",
            size_hint_y=None,
            height="200dp",
            padding=["0dp", "8dp", "0dp", "0dp"],
        )

        info_lbl = MDLabel(
            text=f"[b]{code}[/b] — {name}",
            markup=True,
            font_style="Subtitle1",
            theme_text_color="Primary",
            size_hint_y=None,
            height="32dp",
        )

        self._asset_price_input = MDTextField(
            hint_text="Alım Fiyatı (₺ / adet)",
            input_filter="float",
            size_hint_x=1,
        )
        self._asset_qty_input = MDTextField(
            hint_text="Miktar / Lot (adet)",
            input_filter="float",
            size_hint_x=1,
        )

        content.add_widget(info_lbl)
        content.add_widget(self._asset_price_input)
        content.add_widget(self._asset_qty_input)

        def _go_back(instance):
            self._stock_price_dialog.dismiss()
            Clock.schedule_once(lambda dt: self._show_bist100_picker(), 0.15)

        self._stock_price_dialog = MDDialog(
            title="Alım Bilgileri",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="GERİ", on_release=_go_back),
                MDRaisedButton(
                    text="PORTFÖYE EKLE",
                    md_bg_color=(0.08, 0.72, 0.42, 1),
                    on_release=lambda x: self._save_stock_asset(),
                ),
            ],
        )
        self._stock_price_dialog.open()

    def _save_stock_asset(self):
        """BIST 100 hisse akışından gelen varlığı kaydeder."""
        price_text = self._asset_price_input.text.strip()
        qty_text   = self._asset_qty_input.text.strip()

        if not price_text or not qty_text:
            toast("Fiyat ve miktar zorunludur!")
            return
        try:
            purchase_price = float(price_text.replace(",", "."))
            quantity       = float(qty_text.replace(",", "."))
        except ValueError:
            toast("Geçersiz fiyat veya miktar!")
            return

        asset_name = self._asset_name_input_val
        asset_code = self._asset_code_input_val
        asset_type = "Hisse"

        self._stock_price_dialog.dismiss()

        import threading
        def _insert():
            try:
                from datetime import datetime
                from database.db import insert_asset, insert_asset_transaction, DEFAULT_ACCOUNT_ID
                purchase_date   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                invested_amount = purchase_price * quantity
                insert_asset(asset_name, asset_code, asset_type,
                             purchase_price, quantity, purchase_date)
                desc = (
                    f"{asset_name} ({asset_code}) alındı — "
                    f"{quantity:g} adet, birim fiyat {format_price_tl(purchase_price)}"
                )
                insert_asset_transaction(
                    account_id=DEFAULT_ACCOUNT_ID,
                    amount=invested_amount,
                    tx_type="expense",
                    category="Varlık Alımı",
                    description=desc,
                )
                Clock.schedule_once(lambda dt: toast("Hisse eklendi! Fiyatlar güncelleniyor…"), 0)
                Clock.schedule_once(lambda dt: self.load_active_assets(), 0)
                Clock.schedule_once(lambda dt: self.load_asset_history(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception as e:
                print("Stock insert error:", e)
                Clock.schedule_once(lambda dt: toast("Hisse eklenirken hata oluştu!"), 0)

        threading.Thread(target=_insert, daemon=True).start()

    def _show_crypto_picker(self):
        """Kripto para listesini arama destekli MDDialog'da gösterir."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.scrollview import MDScrollView
        from kivymd.uix.list import MDList, TwoLineAvatarIconListItem, IconLeftWidget, ImageLeftWidget
        from services.crypto_top100 import fetch_top_100_cryptos

        self._crypto_selected_code = None
        self._crypto_selected_name = None

        content = MDBoxLayout(
            orientation="vertical",
            spacing="8dp",
            size_hint_y=None,
            height="420dp",
            padding=["0dp", "4dp", "0dp", "0dp"],
        )

        search_field = MDTextField(
            hint_text="Ara: Kripto adı veya sembol...",
            size_hint_x=1,
            size_hint_y=None,
            height="48dp",
        )

        scroll = MDScrollView(size_hint=(1, 1))
        self._crypto_list_widget = MDList()
        scroll.add_widget(self._crypto_list_widget)

        content.add_widget(search_field)
        content.add_widget(scroll)

        def _build_list(query=""):
            self._crypto_list_widget.clear_widgets()
            query_lower = query.strip().lower()
            cryptos = getattr(self, "_crypto_list_data", [])
            for c in cryptos:
                code = c["symbol"]
                name = c["name"]
                price = c["price"]
                
                if query_lower and query_lower not in code.lower() and query_lower not in name.lower():
                    continue
                
                price_text = f"   [color=#14B85F]${price:,.2f}[/color]" if price else ""
                item = TwoLineAvatarIconListItem(
                    text=f"[b]{code}[/b]{price_text}",
                    secondary_text=name,
                )
                image_url = c.get("image")
                if image_url:
                    logo = ImageLeftWidget(source=image_url)
                    self._bind_fitimage_error(
                        logo, lambda *a, itm=item, im=logo: self._crypto_row_logo_fallback(itm, im)
                    )
                    item.add_widget(logo)
                else:
                    item.add_widget(IconLeftWidget(
                        icon="bitcoin",
                        theme_text_color="Custom",
                        text_color=(0.85, 0.65, 0.13, 1),
                    ))

                try:
                    item.ids._lbl_primary.markup = True
                except Exception:
                    pass
                
                if code == self._crypto_selected_code:
                    try:
                        item.bg_color = (0.08, 0.72, 0.42, 0.15)
                    except Exception:
                        pass

                def _on_select(inst, c_code=code, n_name=name):
                    self._crypto_selected_code = c_code
                    self._crypto_selected_name = n_name
                    for child in self._crypto_list_widget.children:
                        try:
                            child.bg_color = (0, 0, 0, 0)
                        except Exception:
                            pass
                    try:
                        inst.bg_color = (0.08, 0.72, 0.42, 0.15)
                    except Exception:
                        pass

                item.bind(on_release=_on_select)
                self._crypto_list_widget.add_widget(item)

        _build_list()

        self._crypto_search_event = None

        def _on_search(instance, value):
            # BIST picker'daki ile aynı sebep: 100 kalemi her tuş vuruşunda
            # yeniden çizmek yerine 300ms sessizlik sonrası tek seferde çiz.
            if self._crypto_search_event:
                self._crypto_search_event.cancel()
            self._crypto_search_event = Clock.schedule_once(
                lambda dt: _build_list(value), 0.3
            )

        search_field.bind(text=_on_search)

        def _on_cryptos_fetched(cryptos):
            self._crypto_list_data = cryptos
            def _refresh(dt):
                try:
                    _build_list(search_field.text)
                except Exception as e:
                    print("Kripto liste yenileme hatası:", e)
            Clock.schedule_once(_refresh, 0)

        # Arka planda CoinGecko API verisini çek
        fetch_top_100_cryptos(_on_cryptos_fetched)

        def _confirm_crypto(instance):
            if not self._crypto_selected_code:
                toast("Lütfen bir kripto para seçin!")
                return
            self._crypto_dialog.dismiss()
            # yfinance sembol uyumluluğu için -USD ekle (sadece yfinance isteğinde kullanılacak)
            yf_symbol = f"{self._crypto_selected_code}-USD"
            Clock.schedule_once(
                lambda dt: self._show_crypto_price_dialog(
                    yf_symbol,
                    self._crypto_selected_name
                ), 0.15
            )

        self._crypto_dialog = MDDialog(
            title="Top 100 Kripto — Seç",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="GERİ",
                    on_release=lambda x: (self._crypto_dialog.dismiss(),
                                          Clock.schedule_once(lambda dt: self.show_add_asset_dialog(), 0.15)),
                ),
                MDFlatButton(
                    text="SEÇ  ✓",
                    theme_text_color="Custom",
                    text_color=(0.08, 0.72, 0.42, 1),
                    on_release=_confirm_crypto,
                ),
            ],
        )
        self._crypto_dialog.open()

    def _crypto_row_logo_fallback(self, item, broken_image):
        """CoinGecko logo URL'i yüklenemezse (on_error) satırdaki görseli
        kaldırıp sabit 'bitcoin' ikonuna döner. ImageLeftWidget, BaseListItem
        tarafından item.ids._left_container içine eklendiği için doğrudan
        item.remove_widget() onu bulamaz — kaldırma da aynı container'dan
        yapılmalı."""
        from kivymd.uix.list import IconLeftWidget
        try:
            item.ids._left_container.remove_widget(broken_image)
            item.add_widget(IconLeftWidget(
                icon="bitcoin",
                theme_text_color="Custom",
                text_color=(0.85, 0.65, 0.13, 1),
            ))
        except Exception:
            pass

    def _show_crypto_price_dialog(self, code, name):
        """Kripto seçildikten sonra alım fiyatı ve miktar giriş diyaloğu."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel

        self._asset_selected_type = "Kripto"
        self._asset_name_input_val = name
        self._asset_code_input_val = code

        content = MDBoxLayout(
            orientation="vertical",
            spacing="12dp",
            size_hint_y=None,
            height="200dp",
            padding=["0dp", "8dp", "0dp", "0dp"],
        )

        info_lbl = MDLabel(
            text=f"[b]{code}[/b] — {name}",
            markup=True,
            font_style="Subtitle1",
            theme_text_color="Primary",
            size_hint_y=None,
            height="32dp",
        )

        self._asset_price_input = MDTextField(
            hint_text="Alım Fiyatı (₺ / adet)",
            input_filter="float",
            size_hint_x=1,
        )
        self._asset_qty_input = MDTextField(
            hint_text="Miktar (adet)",
            input_filter="float",
            size_hint_x=1,
        )

        content.add_widget(info_lbl)
        content.add_widget(self._asset_price_input)
        content.add_widget(self._asset_qty_input)

        def _go_back(instance):
            self._crypto_price_dialog.dismiss()
            Clock.schedule_once(lambda dt: self._show_crypto_picker(), 0.15)

        self._crypto_price_dialog = MDDialog(
            title="Alım Bilgileri",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="GERİ", on_release=_go_back),
                MDRaisedButton(
                    text="PORTFÖYE EKLE",
                    md_bg_color=(0.08, 0.72, 0.42, 1),
                    on_release=lambda x: self._save_crypto_asset(),
                ),
            ],
        )
        self._crypto_price_dialog.open()

    def _save_crypto_asset(self):
        """Kripto akışından gelen varlığı kaydeder."""
        price_text = self._asset_price_input.text.strip()
        qty_text   = self._asset_qty_input.text.strip()

        if not price_text or not qty_text:
            toast("Fiyat ve miktar zorunludur!")
            return
        try:
            purchase_price = float(price_text.replace(",", "."))
            quantity       = float(qty_text.replace(",", "."))
        except ValueError:
            toast("Geçersiz fiyat veya miktar!")
            return

        asset_name = self._asset_name_input_val
        asset_code = self._asset_code_input_val
        asset_type = "Kripto"

        self._crypto_price_dialog.dismiss()

        import threading
        def _insert():
            try:
                from datetime import datetime
                from database.db import insert_asset, insert_asset_transaction, DEFAULT_ACCOUNT_ID
                purchase_date   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                invested_amount = purchase_price * quantity
                insert_asset(asset_name, asset_code, asset_type,
                             purchase_price, quantity, purchase_date)
                desc = (
                    f"{asset_name} ({asset_code}) alındı — "
                    f"{quantity:g} adet, birim fiyat {format_price_tl(purchase_price)}"
                )
                insert_asset_transaction(
                    account_id=DEFAULT_ACCOUNT_ID,
                    amount=invested_amount,
                    tx_type="expense",
                    category="Varlık Alımı",
                    description=desc,
                )
                Clock.schedule_once(lambda dt: toast("Kripto eklendi! Fiyatlar güncelleniyor…"), 0)
                Clock.schedule_once(lambda dt: self.load_active_assets(), 0)
                Clock.schedule_once(lambda dt: self.load_asset_history(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception as e:
                print("Crypto insert error:", e)
                Clock.schedule_once(lambda dt: toast("Kripto eklenirken hata oluştu!"), 0)

        threading.Thread(target=_insert, daemon=True).start()

    def _show_other_asset_dialog(self):
        """Hisse dışı varlıklar için serbest form diyaloğu."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField

        is_gold = self._asset_selected_type == "Altın"
        quick_picks = self._get_quick_picks(self._asset_selected_type)
        extra_row_height = 44 if (is_gold or quick_picks) else 0
        content = MDBoxLayout(
            orientation="vertical",
            spacing="12dp",
            size_hint_y=None,
            height=f"{320 + extra_row_height}dp",
            padding=["0dp", "8dp", "0dp", "0dp"]
        )

        self._type_logo_slot = MDBoxLayout(
            size_hint_y=None,
            height="40dp",
        )
        self._type_logo_slot.add_widget(self._make_type_fallback_icon())
        content.add_widget(self._type_logo_slot)

        if is_gold:
            from kivymd.uix.menu import MDDropdownMenu

            gold_types = self._GOLD_TYPES
            gold_row = MDBoxLayout(
                orientation="horizontal", spacing="8dp",
                size_hint_y=None, height="36dp",
            )
            gold_btn = MDRaisedButton(
                text=f"Altın Türü: {gold_types[0][0]}",
                size_hint_x=1,
                md_bg_color=GOLD_ICON_COLOR,
            )

            def _select_gold_type(label, symbol, friendly_name):
                gold_btn.text = f"Altın Türü: {label}"
                self._asset_code_input.text = symbol
                self._asset_name_input.text = friendly_name
                self._gold_type_menu.dismiss()

            gold_menu_items = [
                {
                    "text": label,
                    "on_release": lambda l=label, s=symbol, n=friendly_name: _select_gold_type(l, s, n),
                }
                for label, symbol, friendly_name in gold_types
            ]
            self._gold_type_menu = MDDropdownMenu(caller=gold_btn, items=gold_menu_items, width_mult=3)
            gold_btn.bind(on_release=lambda x: self._gold_type_menu.open())

            gold_row.add_widget(gold_btn)
            content.add_widget(gold_row)
        elif quick_picks:
            quick_row = MDBoxLayout(
                orientation="horizontal", spacing="8dp",
                size_hint_y=None, height="36dp",
            )
            for label, symbol, friendly_name in quick_picks:
                chip = MDFlatButton(
                    text=label,
                    theme_text_color="Custom",
                    text_color=(0.08, 0.72, 0.42, 1),
                    size_hint_x=1,
                )
                chip.bind(on_release=lambda x, s=symbol, n=friendly_name: self._apply_quick_pick(s, n))
                quick_row.add_widget(chip)
            content.add_widget(quick_row)

        self._asset_code_input = MDTextField(
            hint_text=self._get_symbol_hint(self._asset_selected_type),
            helper_text=self._get_symbol_helper(self._asset_selected_type),
            helper_text_mode="persistent",
            size_hint_x=1,
        )
        self._asset_code_input.text = self._get_default_symbol(self._asset_selected_type)
        self._asset_code_input.bind(text=self._refresh_type_logo_preview)
        self._refresh_type_logo_preview()

        self._asset_name_input = MDTextField(
            hint_text="Varlık Adı (isteğe bağlı)",
            size_hint_x=1,
        )
        self._asset_price_input = MDTextField(
            hint_text="Alım Fiyatı (₺)",
            input_filter="float",
            size_hint_x=1,
        )
        self._asset_qty_input = MDTextField(
            hint_text="Miktar",
            input_filter="float",
            size_hint_x=1,
        )

        content.add_widget(self._asset_name_input)
        content.add_widget(self._asset_code_input)
        content.add_widget(self._asset_price_input)
        content.add_widget(self._asset_qty_input)

        self.asset_dialog = MDDialog(
            title=f"Yeni {self._asset_selected_type} Ekle",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="GERİ",
                    on_release=lambda x: (
                        self.asset_dialog.dismiss(),
                        Clock.schedule_once(lambda dt: self.show_add_asset_dialog(), 0.15)
                    ),
                ),
                MDRaisedButton(
                    text="EKLE",
                    md_bg_color=(0.08, 0.72, 0.42, 1),
                    on_release=lambda x: self._save_new_asset(),
                ),
            ],
        )
        self.asset_dialog.open()

    def _make_type_fallback_icon(self):
        """Döviz/Altın için uzak logo çözülene (veya hiç çözülemeyene) kadar
        gösterilen statik MDI ikon — mevcut renkli ikon fallback'i."""
        from kivymd.uix.label import MDIcon
        return MDIcon(
            icon=ASSET_TYPE_ICONS.get(self._asset_selected_type, "wallet-outline"),
            font_size="40sp",
            halign="center",
            theme_text_color="Custom",
            text_color=GOLD_ICON_COLOR if self._asset_selected_type == "Altın" else (0.08, 0.72, 0.42, 1),
        )

    def _refresh_type_logo_preview(self, *args):
        """Sembol alanı her değiştiğinde (elle yazma veya hızlı seçim çipi)
        çağrılır: kod Döviz/Altın olarak tanınıyorsa uzak logoyu önizler,
        tanınmıyorsa mevcut MDI ikonuna döner. Ağ isteği yoktur — sadece URL
        üretilir, indirmeyi widget'ın kendi async loader'ı yapar."""
        from services.logo_service import resolve_remote_logo_url
        code = self._asset_code_input.text.strip() if hasattr(self, "_asset_code_input") else ""
        url = resolve_remote_logo_url(code)
        if url:
            self._swap_type_logo(url)
        else:
            self._reset_type_logo_icon()

    def _swap_type_logo(self, url):
        """type_logo_slot içeriğini uzak logo görseline değiştirir; görsel
        yüklenemezse (on_error) otomatik olarak MDI ikon fallback'ine döner."""
        slot = getattr(self, "_type_logo_slot", None)
        if not slot:
            return
        from kivymd.uix.fitimage import FitImage
        from kivy.metrics import dp
        slot.clear_widgets()
        image = FitImage(
            source=url,
            radius=[dp(20)] * 4,
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={"center_x": .5},
        )
        self._bind_fitimage_error(image, lambda *a: self._reset_type_logo_icon())
        slot.add_widget(image)

    def _bind_fitimage_error(self, fit_image, on_error):
        """FitImage'ın iç AsyncImage'ı (_container.image) bir sonraki Clock
        frame'inde geç oluşturulduğu (bkz. FitImage._late_init) için, container
        henüz hazır değilse özelliğin kendisine bind edip hazır olunca bağlar.

        Kivy'nin Loader'ı uzak görsel indirmede 'on_error'ı ana thread'e
        Clock ile geçirmeden doğrudan arka plan indirme thread'inden
        dispatch eder (bkz. kivy/loader.py LoaderBase._load_urllib) — bu
        yüzden callback'i burada Clock.schedule_once ile ana thread'e
        erteliyoruz, yoksa widget ağacını değiştirmek 'Cannot change
        graphics instruction outside the main Kivy thread' hatası verir."""
        def _attach(instance, container):
            if container:
                container.image.bind(
                    on_error=lambda *a: Clock.schedule_once(lambda dt: on_error(*a))
                )
        if fit_image._container:
            _attach(fit_image, fit_image._container)
        else:
            fit_image.bind(_container=_attach)

    def _reset_type_logo_icon(self):
        slot = getattr(self, "_type_logo_slot", None)
        if not slot:
            return
        slot.clear_widgets()
        slot.add_widget(self._make_type_fallback_icon())

    # Tür başına hızlı seçim çipleri: (buton metni, yfinance sembolü, dostane isim)
    _QUICK_PICKS = {
        "Döviz":  [("Dolar", "USDTRY=X", "Amerikan Doları"), ("Euro", "EURTRY=X", "Euro")],
        "Kripto": [("Bitcoin", "BTC-USD", "Bitcoin"), ("Ethereum", "ETH-USD", "Ethereum")],
    }

    # Altın için fiziksel tür seçimi: (buton metni, dahili/yfinance sembolü, dostane isim).
    # Gram Altın gerçek bir yfinance sembolü (GC=F) kullanır; diğerleri gram
    # fiyatının piyasa çarpanıyla türetildiği dahili "GOLD-*" sembolleridir
    # (bkz. services/asset_service.py GOLD_TYPE_MULTIPLIERS).
    _GOLD_TYPES = [
        ("Gram Altın", "GC=F", "Gram Altın"),
        ("Ons Altın", "GOLD-ONS", "Ons Altın"),
        ("Çeyrek Altın", "GOLD-CEYREK", "Çeyrek Altın"),
        ("Yarım Altın", "GOLD-YARIM", "Yarım Altın"),
        ("Tam Altın", "GOLD-TAM", "Tam Altın"),
    ]

    def _get_quick_picks(self, asset_type):
        """Döviz/Kripto için tek dokunuşla sembol dolduran çip listesini döndürür."""
        return self._QUICK_PICKS.get(asset_type, [])

    def _apply_quick_pick(self, symbol, friendly_name):
        """Hızlı seçim çipine tıklanınca sembol ve (boşsa) varlık adı alanını doldurur."""
        self._asset_code_input.text = symbol
        if not self._asset_name_input.text.strip():
            self._asset_name_input.text = friendly_name

    def _get_symbol_hint(self, asset_type):
        hints = {
            "Altın": "Sembol (Otomatik: GC=F)",
            "Kripto": "Sembol (Örn: BTC-USD)",
            "Döviz": "Sembol (Örn: USDTRY=X)",
            "Tahvil": "Sembol",
        }
        return hints.get(asset_type, "Sembol")

    def _get_symbol_helper(self, asset_type):
        helpers = {
            "Altın": "Yukarıdan tür seçin veya elle girin (Gram: GC=F)",
            "Kripto": "Bitcoin: BTC-USD, Ethereum: ETH-USD",
            "Döviz": "Dolar: USDTRY=X, Euro: EURTRY=X",
            "Tahvil": "Yahoo Finance sembolü girin",
        }
        return helpers.get(asset_type, "Yahoo Finance sembolü girin")

    def _get_default_symbol(self, asset_type):
        defaults = {"Altın": "GC=F"}
        return defaults.get(asset_type, "")

    def _select_asset_type(self, asset_type, button, menu):
        """Eski uyumluluk — diğer varlık formu dropdown'ı için."""
        self._asset_selected_type = asset_type
        button.text = f"Tür: {asset_type}"
        menu.dismiss()

    def _save_new_asset(self):
        """Formu doğrular, DB'e şifreli yazar, listeyi yeniler."""
        import threading
        from database.db import insert_asset
        from kivymd.toast import toast

        asset_name  = self._asset_name_input.text.strip()
        asset_code  = self._asset_code_input.text.strip()
        asset_type  = self._asset_selected_type
        price_text  = self._asset_price_input.text.strip()
        qty_text    = self._asset_qty_input.text.strip()

        if not asset_code or not price_text or not qty_text:
            toast("Sembol, fiyat ve miktar zorunludur!")
            return

        try:
            purchase_price = float(price_text.replace(",", "."))
            quantity       = float(qty_text.replace(",", "."))
        except ValueError:
            toast("Geçersiz fiyat veya miktar!")
            return

        if not asset_name:
            asset_name = asset_code.upper()

        self.asset_dialog.dismiss()

        def _insert():
            try:
                from datetime import datetime
                from database.db import insert_asset, insert_asset_transaction, DEFAULT_ACCOUNT_ID
                purchase_date   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                invested_amount = purchase_price * quantity

                # 1. Varlığı portföye ekle
                insert_asset(asset_name, asset_code, asset_type,
                             purchase_price, quantity, purchase_date)

                # 2. Cüzdandan düş: expense + 'Varlık Alımı' kategorisi
                desc = (
                    f"{asset_name} ({asset_code.upper()}) alındı — "
                    f"{quantity:g} adet, birim fiyat {format_price_tl(purchase_price)}"
                )
                insert_asset_transaction(
                    account_id=DEFAULT_ACCOUNT_ID,
                    amount=invested_amount,
                    tx_type="expense",
                    category="Varlık Alımı",
                    description=desc,
                )

                Clock.schedule_once(
                    lambda dt: toast("Varlık eklendi! Fiyatlar güncelleniyor…"), 0)
                Clock.schedule_once(lambda dt: self.load_active_assets(), 0)
                Clock.schedule_once(lambda dt: self.load_asset_history(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception as e:
                print("Asset insert error:", e)
                Clock.schedule_once(
                    lambda dt: toast("Varlık eklenirken hata oluştu!"), 0)

        threading.Thread(target=_insert, daemon=True).start()

    def refresh_asset_prices(self):
        """Kullanıcının tetiklediği manuel fiyat yenileme işlemi.
        Arka planda load_active_assets() çağırarak yfinance'tan güncel fiyatları (₺ veya $) çeker.
        """
        from kivymd.toast import toast
        toast("Fiyatlar anlık olarak güncelleniyor...")
        self.load_active_assets()


    def load_active_assets(self, *args):
        """DB'den tüm varlıkları çeker, ardından yfinance üzerinden canlı
        fiyatları arka plan thread'inde alır ve UI'ı günceller.
        Fiyatlar Yahoo Finance (yfinance) üzerinden gelir, BIST için TRY, diğerleri için ilgili kurlardadır.
        5 dakikalık önbellek (cache) kullanılarak API limitlerine takılma önlenir.
        """
        import threading
        from database.db import get_all_assets
        from services.asset_service import fetch_portfolio_with_prices

        def _fetch_and_enrich():
            try:
                assets = get_all_assets()
                if not assets:
                    Clock.schedule_once(lambda dt: self.render_active_assets([]), 0)
                    return
                
                # Anında güncel olmayan veriyi bas (UI otomatik dolsun)
                Clock.schedule_once(lambda dt: self.render_active_assets(assets), 0)
                
                # Canlı fiyat çekme + K/Z hesaplama (kendi içinde thread açar)
                fetch_portfolio_with_prices(
                    assets,
                    callback=lambda enriched: Clock.schedule_once(
                        lambda dt: self.render_active_assets(enriched), 0
                    ),
                )
            except Exception as e:
                print("Asset load error:", e)

        threading.Thread(target=_fetch_and_enrich, daemon=True).start()

    def render_active_assets(self, assets):
        """Varlık kartlarını renk kodlu K/Z (Kâr/Zarar) bilgisiyle dashboard'a basar.
        Kâr/Zarar (K/Z) hesaplaması: (Güncel Fiyat - Alım Fiyatı) * Miktar. Para birimi ₺'dir.
        """
        try:
            container = self.root.ids.active_assets_container
        except Exception as e:
            print("render_active_assets: container bulunamadı:", e)
            return

        container.clear_widgets()

        if not assets:
            from kivymd.uix.boxlayout import MDBoxLayout
            from kivymd.uix.label import MDLabel, MDIcon
            from kivymd.uix.button import MDRoundFlatIconButton

            empty_layout = MDBoxLayout(
                orientation="vertical",
                spacing="12dp",
                padding=["0dp", "20dp", "0dp", "20dp"],
                size_hint_y=None,
                height="220dp",
            )
            
            icon = MDIcon(
                icon="wallet-plus-outline",
                font_size="64sp",
                theme_text_color="Hint",
                halign="center",
                pos_hint={"center_x": .5}
            )
            
            lbl = MDLabel(
                text="Portföyünüz şu an boş.\nİlk yatırımınızı ekleyerek değerini canlı takip edin!",
                theme_text_color="Secondary",
                font_style="Body2",
                halign="center",
                pos_hint={"center_x": .5},
                size_hint_y=None,
                height="40dp"
            )
            
            btn = MDRoundFlatIconButton(
                icon="plus",
                text="İLK VARLIĞINI EKLE",
                pos_hint={"center_x": .5},
                on_release=lambda x: self.show_add_asset_dialog(),
                text_color=(0.08, 0.72, 0.42, 1),
                icon_color=(0.08, 0.72, 0.42, 1),
                line_color=(0.08, 0.72, 0.42, 1)
            )
            
            empty_layout.add_widget(icon)
            empty_layout.add_widget(lbl)
            empty_layout.add_widget(btn)
            
            container.add_widget(empty_layout)
            self._assets_cache = []
            self.update_wealth_card([])
            return

        from kivymd.uix.card import MDCard
        from kivymd.uix.label import MDLabel, MDIcon
        from kivymd.uix.button import MDIconButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from services.asset_service import get_pnl_color

        for asset in assets:
            signal = asset.get("signal", "pending")
            pnl_color = get_pnl_color(signal)

            # Kart
            card = MDCard(
                orientation="vertical",
                padding="10dp",
                spacing="4dp",
                size_hint_y=None,
                height="100dp",
                elevation=0,
                line_color=(0.8, 0.8, 0.8, 0.3),
                radius=[10],
            )

            # Üst satır: İsim + Sil butonu
            top_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height="26dp",
                spacing="8dp",
            )
            asset_type = asset.get("asset_type", "")
            type_icon = MDIcon(
                icon=get_asset_icon(asset_type, asset.get("asset_code", "")),
                theme_text_color="Custom",
                text_color=GOLD_ICON_COLOR if asset_type == "Altın" else (0.08, 0.72, 0.42, 1),
                size_hint_x=None,
                width="26dp",
                pos_hint={"center_y": .5},
            )
            name_lbl = MDLabel(
                text=f"[b]{asset['asset_name']}[/b]  ({asset['asset_code']})",
                markup=True,
                font_style="Subtitle2",
                theme_text_color="Primary",
            )
            type_lbl = MDLabel(
                text=asset.get("asset_type", ""),
                font_style="Caption",
                theme_text_color="Secondary",
                halign="right",
            )
            del_btn = MDIconButton(
                icon="delete-outline",
                theme_text_color="Custom",
                text_color=(0.9, 0.2, 0.2, 1),
                icon_size="20dp",
                pos_hint={"center_y": .5},
            )
            del_btn.bind(on_release=lambda x, aid=asset["id"]: self._sell_asset(aid))
            top_row.add_widget(type_icon)
            top_row.add_widget(name_lbl)
            top_row.add_widget(type_lbl)
            top_row.add_widget(del_btn)

            # Orta satır: Alım fiyatı / Miktar
            mid_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height="22dp",
            )
            buy_lbl = MDLabel(
                text=f"Alım: {asset['purchase_price']:,.4f} ₺  ×  {asset['quantity']:g}",
                font_style="Caption",
                theme_text_color="Secondary",
            )
            if asset.get("current_price") is not None:
                cur_lbl = MDLabel(
                    text=f"Anlık: {asset['current_price']:,.4f} ₺",
                    font_style="Caption",
                    theme_text_color="Secondary",
                    halign="right",
                )
            elif signal == "error":
                cur_lbl = MDLabel(
                    text="Güncellenemedi",
                    font_style="Caption",
                    theme_text_color="Error",
                    halign="right",
                )
            else:
                cur_lbl = MDLabel(
                    text="Fiyat alınıyor…",
                    font_style="Caption",
                    theme_text_color="Hint",
                    halign="right",
                )
            mid_row.add_widget(buy_lbl)
            mid_row.add_widget(cur_lbl)

            # Alt satır: K/Z
            if asset.get("pnl_pct") is not None:
                sign = "+" if asset["pnl_pct"] >= 0 else ""
                pnl_text = (
                    f"{sign}{asset['pnl_pct']:.2f}%  |  "
                    f"{sign}{asset['pnl_amount']:,.2f} ₺  "
                    f"(Toplam: {asset['total_value']:,.2f} ₺)"
                )
            elif signal == "error":
                pnl_text = "Bağlantı Hatası!"
            else:
                pnl_text = "Canlı veri bekleniyor…"

            pnl_lbl = MDLabel(
                text=pnl_text,
                font_style="Caption",
                bold=True,
                theme_text_color="Custom",
                text_color=pnl_color,
                size_hint_y=None,
                height="22dp",
            )

            card.add_widget(top_row)
            card.add_widget(mid_row)
            card.add_widget(pnl_lbl)
            container.add_widget(card)

        # Kart yüksekliğini dinamik güncelle
        try:
            card_count = len(assets)
            parent_card = container.parent.parent  # ScrollView → MDCard
            new_height = max(280, 60 + card_count * 108)
            from kivy.metrics import dp as _dp
            parent_card.height = _dp(new_height)
        except Exception:
            pass

        # Zenginleştirilmiş listeyi önbellek olarak kaydet ve Toplam Varlık kartını güncelle
        self._assets_cache = assets
        self.update_wealth_card(assets)

    def _sell_asset(self, asset_id):
        """Sat diyaloğu açar — kullanıcı satış fiyatını girer,
        tahsilat income olarak kaydedilir, varlık portföyden çıkar."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel
        from database.db import get_asset_by_id

        asset = get_asset_by_id(asset_id)
        if not asset:
            return

        layout = MDBoxLayout(
            orientation="vertical",
            spacing="12dp",
            size_hint_y=None,
            height="160dp",
            padding=["0dp", "8dp", "0dp", "0dp"],
        )
        info_lbl = MDLabel(
            text=(
                f"{asset['asset_name']} ({asset['asset_code']})\n"
                f"Miktar: {asset['quantity']:g}  |  "
                f"Alım fiyatı: {asset['purchase_price']:,.4g} ₺"
            ),
            font_style="Body2",
            size_hint_y=None,
            height="60dp",
        )
        self._sell_price_input = MDTextField(
            hint_text="Satış fiyatı (₺ / adet)",
            input_filter="float",
            size_hint_x=1,
        )
        layout.add_widget(info_lbl)
        layout.add_widget(self._sell_price_input)

        def _confirm_sell(instance):
            price_text = self._sell_price_input.text.strip()
            try:
                # Handle comma gracefully if someone pastes it
                sell_price = float(price_text.replace(",", "."))
            except ValueError:
                from kivymd.toast import toast as _t
                _t("Geçerli bir fiyat girin!")
                return
            self._sell_dialog.dismiss()
            self._execute_sell(asset, sell_price)

        self._sell_dialog = MDDialog(
            title="Varlığı Sat",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(
                    text="İPTAL",
                    on_release=lambda x: self._sell_dialog.dismiss(),
                ),
                MDRaisedButton(
                    text="SAT",
                    md_bg_color=(0.9, 0.2, 0.2, 1),
                    on_release=_confirm_sell,
                ),
            ],
        )
        self._sell_dialog.open()

    def _execute_sell(self, asset, sell_price_per_unit):
        """Satış işlemini background thread'de gerçekleştirir."""
        import threading
        from database.db import delete_asset, insert_asset_transaction, DEFAULT_ACCOUNT_ID
        from kivymd.toast import toast

        def _do_sell():
            try:
                total_proceeds = sell_price_per_unit * asset["quantity"]
                cost_basis     = asset["purchase_price"] * asset["quantity"]
                pnl            = total_proceeds - cost_basis
                sign           = "+" if pnl >= 0 else "-"

                desc = (
                    f"{asset['asset_name']} ({asset['asset_code']}) satıldı — "
                    f"{asset['quantity']:g} adet, birim fiyat {format_price_tl(sell_price_per_unit)} "
                    f"(K/Z: {sign}{format_price_tl(abs(pnl))})"
                )

                # Cüzdana ekle: income + 'Varlık Satışı'
                insert_asset_transaction(
                    account_id=DEFAULT_ACCOUNT_ID,
                    amount=total_proceeds,
                    tx_type="income",
                    category="Varlık Satışı",
                    description=desc,
                )
                # Portföyden çıkar
                delete_asset(asset["id"])

                Clock.schedule_once(
                    lambda dt: toast(
                        f"Satış tamamlandı! {sign}₺{abs(pnl):,.2f} K/Z"
                    ), 0)
                Clock.schedule_once(lambda dt: self.load_active_assets(), 0)
                Clock.schedule_once(lambda dt: self.load_asset_history(), 0)
                Clock.schedule_once(lambda dt: self.load_recent_transactions(), 0)
                Clock.schedule_once(lambda dt: self.safe_refresh_charts(), 0)
            except Exception as e:
                print("Asset sell error:", e)
                Clock.schedule_once(
                    lambda dt: toast("Satış işlemi başarısız!"), 0)

        threading.Thread(target=_do_sell, daemon=True).start()

    # ─── Varlık Geçmişi (Ledger) ────────────────────────────────────────────
    def load_asset_history(self, *args):
        """Varlık alım/satış geçmişini arka planda çeker ve UI'a render eder.
        Geçmişteki tüm işlemlerin logudur.
        """
        import threading
        from database.db import get_asset_transaction_history

        def _fetch():
            try:
                history = get_asset_transaction_history()
                Clock.schedule_once(
                    lambda dt: self.render_asset_history(history), 0)
            except Exception as e:
                print("Asset history load error:", e)

        threading.Thread(target=_fetch, daemon=True).start()

    def render_asset_history(self, history):
        """Varlık geçmişi listesini RecycleView'ın data listesine tek seferde atar.

        Eskiden her satır için TwoLineIconListItem/IconLeftWidget/ImageLeftWidget
        nesneleri tek tek clear_widgets()+add_widget() ile inşa ediliyordu; bu
        yaklaşım tüm satırları anında widget ağacına çeviriyordu. RecycleView
        yalnızca görünür viewport kadar satırı gerçek widget'a çevirip
        kaydırıldıkça yeniden kullanır (bkz. ui/components.py::RecycleListRow).
        """
        try:
            rv = self.root.ids.asset_history_list
            empty_label = self.root.ids.asset_history_empty_label
        except Exception:
            return

        if not history:
            rv.data = []
            empty_label.height = "40dp"
            empty_label.opacity = 1
            return

        empty_label.height = 0
        empty_label.opacity = 0

        codes_to_prefetch = set()
        data = []

        for entry in history:
            is_buy = entry["category"] == "Varlık Alımı"
            icon_name  = "chart-line"  if is_buy else "cash-plus"
            icon_color = (0.08, 0.72, 0.42, 1) if is_buy else (0.18, 0.8, 0.25, 1)
            sign       = "-" if is_buy else "+"
            amount_clr = "#0277BD" if is_buy else "#2E7D32"

            desc, kz_text = format_history_description(
                entry["description"], entry["category"], is_buy
            )

            sec_parts = [entry["date"], f"[color={amount_clr}]{sign}₺{entry['amount']:,.2f}[/color]"]
            if kz_text:
                kz_color = "#2E7D32" if kz_text.startswith("K/Z: +") else "#C62828"
                sec_parts.append(f"[color={kz_color}]{kz_text}[/color]")
            sec = "   ".join(sec_parts)

            logo_path, pending_code = resolve_history_logo_source(entry["description"])
            if not logo_path and pending_code:
                codes_to_prefetch.add(pending_code)

            data.append({
                "text": desc,
                "secondary_text": sec,
                "icon_source": logo_path or "",
                "icon_name": icon_name,
                "icon_color": list(icon_color),
            })

        rv.data = data

        if codes_to_prefetch:
            self._prefetch_asset_logos(codes_to_prefetch, history)

        # Kart yüksekliğini dinamik güncelle (boşlukları yok et)
        try:
            item_count = len(history)
            parent_card = rv.parent  # RecycleView artık doğrudan MDCard'ın çocuğu
            from kivy.metrics import dp as _dp
            # Base height ~80dp (padding + header), each item ~73dp
            new_height = max(120, 80 + item_count * 73)
            # Eğer liste çok uzunsa maksimum 320dp'de kısıtla ki scroll aktif olsun
            new_height = min(320, new_height)
            parent_card.height = _dp(new_height)
        except Exception:
            pass

    def _prefetch_asset_logos(self, codes, history):
        """Yerelde bulunamayan Kripto/Döviz logolarını arka planda indirir.
        Ağ hatası (zaman aşımı, DNS, 404) tamamen sessiz yutulur — indirme
        başarısız olan kalemler mevcut MDI ikonlarıyla görünmeye devam eder.
        En az biri başarıyla indirilirse liste bir kez yeniden çizilir."""
        import threading
        from services.logo_service import fetch_and_cache_logo

        def _worker():
            any_success = False
            for code in codes:
                try:
                    if fetch_and_cache_logo(code):
                        any_success = True
                except Exception as e:
                    print("Logo indirme hatası:", code, e)
            if any_success:
                Clock.schedule_once(lambda dt: self.render_asset_history(history), 0)

        threading.Thread(target=_worker, daemon=True).start()

