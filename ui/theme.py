"""Archlence tema sistemi — Standart (KivyMD varsayılan) + Premium Banking (Indigo).

Tema artık KALICI DEĞİL: uygulama varsayılan olarak Standart (Teal) açılır,
kullanıcı Ayarlar'dan Premium'a geçebilir. Bu modül iki yönlü geçişi yönetir:
premium token'larını uygular ve standarda dönerken KivyMD'nin dokunulmamış
Light/Indigo token'larını birebir geri yükler.
"""

from kivy.utils import get_color_from_hex

# ── Premium Banking renk token'ları ────────────────────────────────────────
ARCHLENCE_PRIMARY_HEX = "5444E5"    # Ana accent: Indigo/Çivit
ARCHLENCE_SECONDARY_HEX = "3B2FC3"  # Koyu indigo
ARCHLENCE_BG_HEX = "F9F9FF"         # Açık tema canvas: slate beyaz
ARCHLENCE_SURFACE_HEX = "FFFFFF"    # Kart yüzeyleri: saf beyaz
ARCHLENCE_TEXT_HEX = "151C27"       # Birincil metin: lacivert-siyah

# ── Karanlık tema yüzey merdiveni ──────────────────────────────────────────
# Material "dark surface elevation" mantığı: kartlar zeminden ÇİZGİYLE değil,
# bir tık açık dolguyla ayrışır. Neon kenarlık yerine bu merdiven kullanılır.
ARCHLENCE_DARK_BG_HEX = "121212"       # Canvas (en dip)
ARCHLENCE_DARK_SURFACE_HEX = "1E1E1E"  # Kart / diyalog yüzeyi (+1 basamak)
ARCHLENCE_DARK_ELEVATED_HEX = "262626" # İç içe kart / seçili durum (+2 basamak)

# rgba karşılıkları (Python tarafında grafik/canvas çizimleri için)
ARCHLENCE_PRIMARY = get_color_from_hex(ARCHLENCE_PRIMARY_HEX)
ARCHLENCE_SECONDARY = get_color_from_hex(ARCHLENCE_SECONDARY_HEX)
ARCHLENCE_TEXT = get_color_from_hex(ARCHLENCE_TEXT_HEX)

# Tema rol token'ları. Koyu kart yüzeyi Light Mode'da da bilinçli olarak kalır;
# gerçek bankacılık uygulamalarındaki fiziksel kart metaforunu korur.
ARCHLENCE_BANK_CARD_HEX = "171C25"
ARCHLENCE_BANK_CARD_TEXT_HEX = "F7F9FC"
ARCHLENCE_BANK_CARD_MUTED_HEX = "AEB7C6"

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


def apply_dark_surface_tokens():
    """KivyMD'nin varsayılan Dark token'larını Archlence yüzey merdiveniyle ezer.

    Varsayılan Dark paleti Background ve CardsDialogs için birbirine çok yakın
    griler verdiği için kartlar zeminden ayrışmıyordu; eski çözüm kartlara kalın
    `line_color` koymaktı ve karanlıkta neon gibi parlıyordu. Token'ları
    ayırınca ayrışma dolgudan gelir, çizgiye gerek kalmaz.

    Her tema uygulamasında idempotent olarak çağrılır (sözlük mutasyonu).
    """
    from kivymd.color_definitions import colors
    colors["Dark"]["Background"] = ARCHLENCE_DARK_BG_HEX
    colors["Dark"]["CardsDialogs"] = ARCHLENCE_DARK_SURFACE_HEX
    colors["Dark"]["AppBar"] = ARCHLENCE_DARK_SURFACE_HEX


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
    if getattr(ThemeManager, "_archlence_text_patched", False):
        return

    def _archlence_get_text_color(self, opposite=False):
        theme_style = self._get_theme_style(opposite)
        if theme_style == "Light":
            from kivymd.app import MDApp
            _app = MDApp.get_running_app()
            if _app is not None and getattr(_app, "theme_name", "standard") == "premium":
                c = get_color_from_hex("151C27")
                return tuple(c)
            color = get_color_from_hex("000000")
            color[3] = 0.87
            return tuple(color)
        color = get_color_from_hex("FFFFFF")
        return tuple(color)

    ThemeManager._get_text_color.__code__ = _archlence_get_text_color.__code__
    ThemeManager._archlence_text_patched = True


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
    colors["Indigo"]["500"] = ARCHLENCE_PRIMARY_HEX
    colors["Indigo"]["700"] = ARCHLENCE_SECONDARY_HEX
    colors["Indigo"]["A700"] = ARCHLENCE_SECONDARY_HEX
    # Açık tema zeminleri.
    colors["Light"]["Background"] = ARCHLENCE_BG_HEX
    colors["Light"]["CardsDialogs"] = ARCHLENCE_SURFACE_HEX
    colors["Light"]["AppBar"] = ARCHLENCE_SURFACE_HEX
    apply_dark_surface_tokens()

    # theme_style'a DOKUNULMAZ: kullanıcı karanlık moddayken palet değiştirince
    # ekranın beyaza patlamaması için aktif mod korunur.
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
    if _STANDARD_LIGHT is not None:
        colors["Light"].update(_STANDARD_LIGHT)
    if _STANDARD_INDIGO is not None:
        colors["Indigo"].update(_STANDARD_INDIGO)
    # Karanlık yüzey merdiveni marka değil okunabilirlik meselesi; standart
    # temada da geçerli kalır.
    apply_dark_surface_tokens()

    theme_cls.primary_palette = "Teal"
    theme_cls.accent_palette = "Amber"  # KivyMD varsayılan accent
    theme_cls.accent_hue = "500"
    _refresh(theme_cls)


# ── Paylaşılan bileşen stilleri ────────────────────────────────────────────
# Aşağıdaki yardımcılar hem KV'den (`#:import ftheme ui.theme`) hem Python
# mixin'lerinden çağrılır. KV tarafında bağlamanın tema değişiminde yeniden
# hesaplanması için fonksiyonlara `app.theme_cls.theme_style` STRING'i geçilir —
# `theme_cls` nesnesi geçilirse Kivy bağımlılığı theme_style üzerinde kuramaz ve
# tema değişince renk güncellenmez.

def _is_dark(style):
    """`theme_style` string'ini ya da bir ThemeManager'ı kabul eder."""
    if not isinstance(style, str):
        style = getattr(style, "theme_style", "Light")
    return style == "Dark"


def card_bg(style):
    """Kart/yüzey dolgusu — karanlıkta zeminden bir basamak açık (#1E1E1E)."""
    if _is_dark(style):
        return get_color_from_hex(ARCHLENCE_DARK_SURFACE_HEX)
    return [1, 1, 1, 1]


def elevated_bg(style):
    """İç içe kart ya da seçili durum yüzeyi (+2 basamak)."""
    if _is_dark(style):
        return get_color_from_hex(ARCHLENCE_DARK_ELEVATED_HEX)
    return get_color_from_hex("F1F1F6")


def card_line(style):
    """Kart kenarlığı. Karanlıkta TAMAMEN şeffaf: ayrışma dolgudan gelir.

    Eski `0.8, 0.8, 0.8, 0.3` değeri koyu zeminde neon bir hat gibi parlıyordu.
    Açık temada ise ince bir hairline hâlâ faydalı, orada korunur.
    """
    if _is_dark(style):
        return [0, 0, 0, 0]
    return [0, 0, 0, 0.08]


def muted_bg(style):
    """Segmented control / filtre çubuğu gibi pasif konteyner zeminleri."""
    if _is_dark(style):
        return get_color_from_hex(ARCHLENCE_DARK_ELEVATED_HEX)
    return [0.93, 0.93, 0.95, 1]


def bank_card_bg(style):
    """Premium kartın temadan bağımsız gece mavisi fiziksel kart yüzeyi."""
    return get_color_from_hex(ARCHLENCE_BANK_CARD_HEX)


def bank_card_text(style, muted=False):
    """Gece mavisi kart üzerinde WCAG dostu ana/ikincil metin."""
    return get_color_from_hex(
        ARCHLENCE_BANK_CARD_MUTED_HEX if muted else ARCHLENCE_BANK_CARD_TEXT_HEX
    )


def on_primary(style):
    """Primary/danger gibi koyu eylem yüzeylerinin üzerindeki metin."""
    return [1, 1, 1, 1]


def danger_bg(style):
    return list(accent(style, "red"))


def inactive_control_bg(style):
    return elevated_bg(style) if _is_dark(style) else get_color_from_hex("E9EAF0")


def inactive_control_text(style):
    return accent(style, "muted")


def field_style(style):
    """`MDTextField(**field_style(...))` ile geçirilebilen kontrast kiti.

    Karanlık temada hint/helper metinleri KivyMD varsayılanında siyaha yakın
    kalıp okunmaz hâle geliyordu; her iki tema için de açıkça veriliyor.
    """
    if _is_dark(style):
        hint = (0.78, 0.80, 0.86, 1)
        text = (0.95, 0.96, 0.98, 1)
        fill = (1, 1, 1, 0.08)
        line = (1, 1, 1, 0.24)
    else:
        hint = (0.35, 0.36, 0.41, 1)
        text = (0.11, 0.12, 0.15, 1)
        fill = (0, 0, 0, 0.05)
        line = (0, 0, 0, 0.20)
    return {
        "hint_text_color_normal": hint,
        "hint_text_color_focus": hint,
        "helper_text_color_normal": hint,
        "helper_text_color_focus": hint,
        "text_color_normal": text,
        "text_color_focus": text,
        "fill_color_normal": fill,
        "fill_color_focus": fill,
        "line_color_normal": line,
    }


def make_text_field(hint, theme_cls, filter=None, mode="fill", **kwargs):
    """Tema duyarlı, yuvarlatılmış standart Archlence giriş alanı."""
    from kivy.metrics import dp
    from kivymd.uix.textfield import MDTextField
    from typing import Any

    opts: dict[str, Any] = dict(field_style(theme_cls))
    opts.update(
        hint_text=hint,
        mode=mode,
        radius=[dp(12), dp(12), dp(12), dp(12)],
    )
    if filter is not None:
        opts["input_filter"] = filter
    opts.update(kwargs)
    return MDTextField(**opts)


def restyle_text_fields(root, theme_cls):
    """Açık widget ağacındaki tüm MDTextField'ları aktif temaya göre tazeler.

    Diyaloglar açıkken tema değiştirilebildiği için gerekli — alanlar
    kurulduklarında geçerli olan renkleri saklar, kendiliğinden güncellenmez.
    """
    from kivymd.uix.textfield import MDTextField

    opts = field_style(theme_cls)
    for widget in root.walk():
        if isinstance(widget, MDTextField):
            for key, value in opts.items():
                try:
                    setattr(widget, key, value)
                except Exception:
                    pass


def primary_button(text, theme_cls, **kwargs):
    """Ana eylem butonu — dolgu daima aktif temanın primary rengi.

    Marka rengi koda gömülmez; `theme_cls.primary_color` premium temada
    #5444E5, standart temada Teal döner.
    """
    from kivymd.uix.button import MDRaisedButton

    opts = dict(
        text=text,
        md_bg_color=theme_cls.primary_color,
        elevation=0,
        theme_text_color="Custom",
        text_color=(1, 1, 1, 1),
    )
    opts.update(kwargs)
    return MDRaisedButton(**opts)


def secondary_button(text, theme_cls, **kwargs):
    """İptal/kapat gibi ikincil eylemler — dolgusuz (flat), nötr metin."""
    from kivymd.uix.button import MDFlatButton

    opts = dict(
        text=text,
        theme_text_color="Custom",
        text_color=(0.62, 0.64, 0.70, 1) if _is_dark(theme_cls) else (0.45, 0.46, 0.52, 1),
    )
    opts.update(kwargs)
    return MDFlatButton(**opts)


def danger_button(text, theme_cls, **kwargs):
    """Yıkıcı eylemler (silme, sıfırlama) — kırmızı SEMANTİK olduğu için kalır,
    ama karanlık temada göz almayacak tona çekilir."""
    from kivymd.uix.button import MDRaisedButton

    red = (0.85, 0.33, 0.33, 1) if _is_dark(theme_cls) else (0.83, 0.18, 0.18, 1)
    opts = dict(
        text=text,
        md_bg_color=red,
        elevation=0,
        theme_text_color="Custom",
        text_color=(1, 1, 1, 1),
    )
    opts.update(kwargs)
    return MDRaisedButton(**opts)


# Anlam taşıyan (gelir/gider/nötr) özet kartlarının pastel dolguları. Açık
# temada pastel tonlar, karanlıkta aynı hue'nun koyu yüzey üzerine %10-12
# opaklıkta uygulanmış hâli — kart hâlâ "yeşil/kırmızı" okunur ama parlamaz.
_TINTS = {
    "green": ((0.85, 0.95, 0.88, 1), (0.16, 0.62, 0.36, 0.18)),
    "red":   ((0.98, 0.88, 0.88, 1), (0.80, 0.29, 0.29, 0.18)),
    "blue":  ((0.88, 0.94, 0.98, 1), (0.28, 0.52, 0.85, 0.18)),
    "amber": ((0.99, 0.95, 0.90, 1), (0.85, 0.62, 0.25, 0.18)),
}


def tint_bg(style, name):
    """Anlamsal renkli özet kartı dolgusu (`green`/`red`/`blue`/`amber`)."""
    light, dark = _TINTS.get(name, _TINTS["blue"])
    if not _is_dark(style):
        return list(light)
    # Koyu yüzeyin üzerine tint'i alfa ile karıştır — düz, opak bir sonuç ver.
    base = get_color_from_hex(ARCHLENCE_DARK_SURFACE_HEX)
    a = dark[3]
    return [base[i] * (1 - a) + dark[i] * a for i in range(3)] + [1]


# Anlamsal METİN/ikon renkleri. Açık temada koyu-doygun tonlar okunur, aynı
# tonlar koyu zeminde kontrastı çöküyor (özellikle koyu yeşil/kahve); karanlık
# için her hue'nun açık, düşük doygunluklu karşılığı verilir.
_ACCENTS = {
    "green":  ((0.06, 0.55, 0.18, 1), (0.45, 0.87, 0.56, 1)),
    "red":    ((0.78, 0.10, 0.10, 1), (0.98, 0.55, 0.55, 1)),
    "blue":   ((0.05, 0.47, 0.70, 1), (0.52, 0.76, 1.00, 1)),
    "amber":  ((0.72, 0.45, 0.06, 1), (1.00, 0.78, 0.35, 1)),
    "purple": ((0.45, 0.15, 0.62, 1), (0.80, 0.62, 0.98, 1)),
    "muted":  ((0.45, 0.46, 0.52, 1), (0.62, 0.64, 0.70, 1)),
}


def accent(style, name):
    """Anlamsal metin/ikon rengi (`green`/`red`/`blue`/`amber`/`purple`/`muted`)."""
    light, dark = _ACCENTS.get(name, _ACCENTS["muted"])
    return list(dark if _is_dark(style) else light)


def chart_axis(style):
    """Grafik eksenleri için yüzey üzerinde okunabilir nötr çizgi."""
    return [0.35, 0.36, 0.41, 0.70] if not _is_dark(style) else [0.76, 0.78, 0.84, 0.72]


def chart_grid(style):
    """Grafik ızgarası; eksenden daha geri planda kalan nötr çizgi."""
    return [0.35, 0.36, 0.41, 0.12] if not _is_dark(style) else [0.76, 0.78, 0.84, 0.16]


def chart_label(style):
    """Canvas dokusuna basılan grafik etiketlerinin metin rengi."""
    return [0.32, 0.33, 0.38, 1] if not _is_dark(style) else [0.78, 0.80, 0.86, 1]


def chart_empty(style):
    """Verisiz grafiklerin nötr dolgu/halka rengi."""
    return [0.80, 0.80, 0.80, 1] if not _is_dark(style) else [0.34, 0.35, 0.39, 1]


_FIELD_ROLES = ("hint", "text", "fill", "line")


def field_color(style, role):
    """`MDTextField` renk rolü: `hint` | `text` | `fill` | `line`.

    KV'deki global `<MDTextField>` kuralı bunu kullanır; böylece Python'da
    imperatif kurulan diyalog alanları da (kural her örneğe uygulanır) karanlık
    temada okunur hint/helper metnine sahip olur.
    """
    return list(field_style(style)[{
        "hint": "hint_text_color_normal",
        "text": "text_color_normal",
        "fill": "fill_color_normal",
        "line": "line_color_normal",
    }[role]])


def apply_card_theme(card, theme_cls, tint=None):
    """Python'da imperatif kurulan bir MDCard'ı Archlence yüzey diline bağlar.

    KV'deki kartlar tema değişiminde bağlamalar sayesinde kendiliğinden
    güncellenir; Python'da kurulanlar rengi bir kez hesaplar. Bu yüzden seçilen
    `tint` kartın üzerinde işaretlenir ve tema değiştiğinde
    `refresh_card_theme` ile yeniden uygulanır (kart başına bind kurup
    yeniden çizimlerde sızıntı bırakmamak için işaret + tarama yöntemi).
    """
    card._archlence_tint = tint
    refresh_card_theme(card, theme_cls)
    return card


def refresh_card_theme(card, theme_cls):
    """`apply_card_theme` ile işaretlenmiş bir kartın renklerini tazeler."""
    card.elevation = 0
    if hasattr(card, "shadow_softness"):
        card.shadow_softness = 0
    card.line_color = card_line(theme_cls)
    tint = getattr(card, "_archlence_tint", None)
    card.md_bg_color = tint_bg(theme_cls, tint) if tint else card_bg(theme_cls)
