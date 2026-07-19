"""Finora tema sistemi — Standart (KivyMD varsayılan) + Premium Banking (Indigo).

Tema artık KALICI DEĞİL: uygulama varsayılan olarak Standart (Teal) açılır,
kullanıcı Ayarlar'dan Premium'a geçebilir. Bu modül iki yönlü geçişi yönetir:
premium token'larını uygular ve standarda dönerken KivyMD'nin dokunulmamış
Light/Indigo token'larını birebir geri yükler.
"""

from kivy.utils import get_color_from_hex

# ── Premium Banking renk token'ları ────────────────────────────────────────
FINORA_PRIMARY_HEX = "5444E5"    # Ana accent: Indigo/Çivit
FINORA_SECONDARY_HEX = "3B2FC3"  # Koyu indigo
FINORA_BG_HEX = "F9F9FF"         # Açık tema canvas: slate beyaz
FINORA_SURFACE_HEX = "FFFFFF"    # Kart yüzeyleri: saf beyaz
FINORA_TEXT_HEX = "151C27"       # Birincil metin: lacivert-siyah

# rgba karşılıkları (Python tarafında grafik/canvas çizimleri için)
FINORA_PRIMARY = get_color_from_hex(FINORA_PRIMARY_HEX)
FINORA_SECONDARY = get_color_from_hex(FINORA_SECONDARY_HEX)
FINORA_TEXT = get_color_from_hex(FINORA_TEXT_HEX)

# KivyMD'nin dokunulmamış Light/Indigo token'ları; ilk apply çağrısında
# yakalanır, standarda dönüşte geri yüklenir (premium mutasyonu kalıcı olmasın).
_STANDARD_LIGHT = None
_STANDARD_INDIGO = None


def _ensure_captured():
    global _STANDARD_LIGHT, _STANDARD_INDIGO
    from kivymd.color_definitions import colors
    if _STANDARD_LIGHT is None:
        _STANDARD_LIGHT = dict(colors["Light"])
    if _STANDARD_INDIGO is None:
        _STANDARD_INDIGO = dict(colors["Indigo"])


def _patch_text_color_once():
    """Birincil metin rengini TEMA-DUYARLI yapar.

    KivyMD 1.x'te metin rengi _get_text_color'a gömülü (Light→siyah %87) ve
    text_color AliasProperty'si fonksiyon NESNESİNİ sınıf kurulurken yakalıyor;
    metodu sonradan set etmek property'ye işlemez. Bu yüzden __code__ takası
    yapılır — property aynı nesneyi tutar, davranış değişir. Yeni gövde çalışma
    anında aktif temayı MDApp üzerinden okur: premium'da lacivert-siyah
    (#151C27), standartta KivyMD varsayılanı. Gövde yalnızca get_color_from_hex
    (kivymd.theming globali) ve builtin'leri kullanır, closure yoktur — takas
    güvenli.
    """
    from kivymd.theming import ThemeManager
    if getattr(ThemeManager, "_finora_text_patched", False):
        return

    def _finora_get_text_color(self, opposite=False):
        theme_style = self._get_theme_style(opposite)
        if theme_style == "Light":
            from kivymd.app import MDApp
            _app = MDApp.get_running_app()
            if _app is not None and getattr(_app, "theme_name", "standard") == "premium":
                return get_color_from_hex("151C27")
            color = get_color_from_hex("000000")
            color[3] = 0.87
            return color
        color = get_color_from_hex("FFFFFF")
        return color

    ThemeManager._get_text_color.__code__ = _finora_get_text_color.__code__
    ThemeManager._finora_text_patched = True


def _refresh(theme_cls):
    """colors sözlüğü mutasyonundan sonra tema-bağlı AliasProperty'leri
    (primary_color, bg_normal, text_color...) yeniden hesaplatır — flash yok."""
    theme_cls.property("primary_palette").dispatch(theme_cls)
    theme_cls.property("theme_style").dispatch(theme_cls)


def apply_premium_theme(theme_cls):
    """Premium Banking: Indigo paleti + slate zemin + beyaz yüzey."""
    from kivymd.color_definitions import colors
    _ensure_captured()
    _patch_text_color_once()

    # Indigo paletinin ana tonlarını marka renkleriyle ez (primary_hue "500").
    colors["Indigo"]["500"] = FINORA_PRIMARY_HEX
    colors["Indigo"]["700"] = FINORA_SECONDARY_HEX
    colors["Indigo"]["A700"] = FINORA_SECONDARY_HEX
    # Açık tema zeminleri.
    colors["Light"]["Background"] = FINORA_BG_HEX
    colors["Light"]["CardsDialogs"] = FINORA_SURFACE_HEX
    colors["Light"]["AppBar"] = FINORA_SURFACE_HEX

    theme_cls.theme_style = "Light"
    theme_cls.primary_palette = "Indigo"
    theme_cls.accent_palette = "Indigo"
    theme_cls.accent_hue = "700"
    _refresh(theme_cls)


def apply_standard_theme(theme_cls):
    """Standart, stabil KivyMD teması (orijinal Teal palet + varsayılan zemin)."""
    from kivymd.color_definitions import colors
    _ensure_captured()
    _patch_text_color_once()

    # Premium mutasyonlarını geri al — KivyMD'nin dokunulmamış token'ları.
    colors["Light"].update(_STANDARD_LIGHT)
    colors["Indigo"].update(_STANDARD_INDIGO)

    theme_cls.theme_style = "Light"
    theme_cls.primary_palette = "Teal"
    theme_cls.accent_palette = "Amber"  # KivyMD varsayılan accent
    theme_cls.accent_hue = "500"
    _refresh(theme_cls)
