"""Finora "Premium Banking" tasarım sistemi — renk token'ları.

Yeni görsel dilin tek kaynağı: Indigo ağırlıklı, yüksek kontrastlı palet.
KivyMD 1.x'te özel hex marka rengi doğrudan verilemediği için (palet adı
bekler) Indigo paletinin ilgili tonları ve Light temanın zemin token'ları
kivymd.color_definitions.colors sözlüğü üzerinden ezilir; ThemeManager
AliasProperty'leri bu sözlüğü erişim anında okuduğundan build() sırasında
çağrılması yeterlidir.
"""

from kivy.utils import get_color_from_hex

# ── Renk token'ları (hex, '#'siz — KivyMD colors sözlüğü öyle bekler) ──────
FINORA_PRIMARY_HEX = "5444E5"    # Ana accent: Indigo/Çivit
FINORA_SECONDARY_HEX = "3B2FC3"  # Koyu indigo
FINORA_BG_HEX = "F9F9FF"         # Açık tema canvas: slate beyaz
FINORA_SURFACE_HEX = "FFFFFF"    # Kart yüzeyleri: saf beyaz
FINORA_TEXT_HEX = "151C27"       # Birincil metin: lacivert-siyah

# rgba karşılıkları (Python tarafında grafik/canvas çizimleri için)
FINORA_PRIMARY = get_color_from_hex(FINORA_PRIMARY_HEX)
FINORA_SECONDARY = get_color_from_hex(FINORA_SECONDARY_HEX)
FINORA_TEXT = get_color_from_hex(FINORA_TEXT_HEX)


def apply_finora_theme(theme_cls):
    """Paleti KivyMD'ye uygular. build() içinde, kv yüklenmeden önce çağrılır."""
    from kivymd.color_definitions import colors
    from kivymd.theming import ThemeManager

    # Indigo paletinin ana tonlarını marka renkleriyle ez; primary_hue "500"
    # olduğundan primary_color = 5444E5, primary_dark (700) = 3B2FC3 olur.
    colors["Indigo"]["500"] = FINORA_PRIMARY_HEX
    colors["Indigo"]["700"] = FINORA_SECONDARY_HEX
    colors["Indigo"]["A700"] = FINORA_SECONDARY_HEX

    # Açık tema zeminleri: bg_normal→Background, bg_light→CardsDialogs,
    # bg_dark→AppBar (kv'deki kök ekran bg_normal okuyor).
    colors["Light"]["Background"] = FINORA_BG_HEX
    colors["Light"]["CardsDialogs"] = FINORA_SURFACE_HEX
    colors["Light"]["AppBar"] = FINORA_SURFACE_HEX

    # Birincil metin rengi: KivyMD 1.x'te token yok, _get_text_color içine
    # gömülü (Light→siyah 0.87) ve text_color AliasProperty'si fonksiyon
    # NESNESİNİ sınıf oluşturulurken yakalar — metodu sonradan değiştirmek
    # property'ye işlemez. Bu yüzden orijinal fonksiyonun __code__'u yerinde
    # değiştirilir: property'nin tuttuğu nesne aynı kalır, davranış değişir.
    # (Yeni gövde yalnızca get_color_from_hex kullanır; o isim kivymd.theming
    # modül globals'ında zaten var, closure'sız olduğu için takas güvenli.)
    if not getattr(ThemeManager, "_finora_text_patched", False):
        def _finora_get_text_color(self, opposite=False):
            theme_style = self._get_theme_style(opposite)
            if theme_style == "Light":
                color = get_color_from_hex("151C27")
            else:
                color = get_color_from_hex("FFFFFF")
            return color
        ThemeManager._get_text_color.__code__ = _finora_get_text_color.__code__
        ThemeManager._finora_text_patched = True

    theme_cls.primary_palette = "Indigo"
    theme_cls.accent_palette = "Indigo"
    theme_cls.accent_hue = "700"  # Secondary = koyu indigo
