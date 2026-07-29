"""İşlem ve abonelik adları için best-effort marka ikonu servisi.

Tanınan bir marka adı metinden çıkarılır, PNG logo ayrı bir yerel dizinde
önbelleklenir. Ağ/HTTP/içerik hataları hiçbir zaman çağırana taşınmaz; arayüz
mevcut MDI ikonuyla çalışmaya devam eder.
"""

import os
import re
import unicodedata

from utils.app_paths import cache_dir

# docs/ROADMAP.md Faz 1 madde 4. Paketlenmiş bir Windows kurulumunda
# uygulamanın kendi kurulum dizini genelde salt-okunur. Bu bir ÖNBELLEK —
# indirilen logo yeniden indirilebilir — bu yüzden eski BASE_DIR
# konumundan bir MİGRATİON yok, gerekmiyor da: en kötü ihtimalle bir sonraki
# `fetch_and_cache_brand_icon` çağrısı logoyu yeniden indirir.
BRAND_ICON_CACHE_DIR = os.path.join(cache_dir(), "brand_icon_cache")

# Uzun/özgül takma adlar önce sınanır. Değer: (cache anahtarı, marka domaini).
_BRANDS = (
    (("amazon prime", "prime video"), "prime-video", "primevideo.com"),
    (("youtube premium", "youtube music", "youtube"), "youtube", "youtube.com"),
    (("apple music", "apple tv", "icloud", "apple"), "apple", "apple.com"),
    (("disney plus", "disney+"), "disney-plus", "disneyplus.com"),
    (("netflix",), "netflix", "netflix.com"),
    (("spotify",), "spotify", "spotify.com"),
    (("max", "hbo max"), "max", "max.com"),
    (("blutv", "blu tv"), "blutv", "blutv.com"),
    (("exxen",), "exxen", "exxen.com"),
    (("gain",), "gain", "gain.tv"),
    (("mubi",), "mubi", "mubi.com"),
    (("deezer",), "deezer", "deezer.com"),
    (("tod tv", "tod"), "tod", "todtv.com.tr"),
    (("tabii",), "tabii", "tabii.com"),

    # ── Video/yayın (ek) ────────────────────────────────────────────────
    (("twitch",), "twitch", "twitch.tv"),
    (("paramount plus", "paramount+"), "paramount-plus", "paramountplus.com"),
    (("peacock",), "peacock", "peacocktv.com"),
    (("crunchyroll",), "crunchyroll", "crunchyroll.com"),

    # ── Müzik ───────────────────────────────────────────────────────────
    (("tidal",), "tidal", "tidal.com"),
    (("soundcloud", "soundcloud go"), "soundcloud", "soundcloud.com"),

    # ── Kitap / sesli kitap ─────────────────────────────────────────────
    (("storytel",), "storytel", "storytel.com"),
    (("audible",), "audible", "audible.com"),
    (("kindle unlimited",), "kindle-unlimited", "amazon.com"),
    (("blinkist",), "blinkist", "blinkist.com"),

    # ── Oyun ────────────────────────────────────────────────────────────
    (("playstation plus", "ps plus", "psn"), "playstation-plus", "playstation.com"),
    (("xbox game pass", "game pass", "xbox"), "xbox-game-pass", "xbox.com"),
    (("nintendo switch online", "nintendo online"), "nintendo-online", "nintendo.com"),
    (("ea play",), "ea-play", "ea.com"),
    (("ubisoft+", "ubisoft plus"), "ubisoft-plus", "ubisoft.com"),

    # ── Bulut depolama ──────────────────────────────────────────────────
    (("google one", "google drive"), "google-one", "one.google.com"),
    (("dropbox",), "dropbox", "dropbox.com"),

    # ── Üretkenlik / yapay zekâ ─────────────────────────────────────────
    (("microsoft 365", "office 365"), "microsoft-365", "microsoft.com"),
    (("adobe creative cloud", "adobe cc", "creative cloud"), "adobe-cc", "adobe.com"),
    (("canva",), "canva", "canva.com"),
    (("notion",), "notion", "notion.so"),
    (("chatgpt", "chat gpt", "openai"), "chatgpt", "openai.com"),
    (("github copilot", "github"), "github", "github.com"),
    (("slack",), "slack", "slack.com"),
    (("zoom",), "zoom", "zoom.us"),
    (("linkedin premium", "linkedin"), "linkedin", "linkedin.com"),
    (("figma",), "figma", "figma.com"),
    (("jetbrains",), "jetbrains", "jetbrains.com"),
    (("1password", "1 password"), "1password", "1password.com"),
    (("lastpass", "last pass"), "lastpass", "lastpass.com"),
    (("claude", "anthropic"), "claude", "claude.ai"),
    (("gemini advanced", "google gemini", "gemini"), "gemini", "gemini.google.com"),

    # ── Eğitim ───────────────────────────────────────────────────────────
    (("udemy",), "udemy", "udemy.com"),
    (("coursera",), "coursera", "coursera.org"),
    (("duolingo",), "duolingo", "duolingo.com"),
    (("skillshare",), "skillshare", "skillshare.com"),

    # ── Spor / sağlık ────────────────────────────────────────────────────
    (("macfit", "mac fit"), "macfit", "macfit.com"),
    (("club sporium", "clubsporium", "sporium"), "sporium", "clubsporium.com.tr"),
    (("strava",), "strava", "strava.com"),
    (("headspace",), "headspace", "headspace.com"),

    # ── Üyelik / destek ──────────────────────────────────────────────────
    (("patreon",), "patreon", "patreon.com"),
    (("wikipedia", "wikimedia"), "wikipedia", "wikipedia.org"),

    # ── Proton gizlilik paketi ───────────────────────────────────────────
    # Ürün adları genel "proton" girdisinden önce olmalı; böylece her ürünün
    # önbelleği bağımsız kalır ve VPN kendi alan adının ikonunu kullanabilir.
    (("proton vpn", "protonvpn"), "proton-vpn", "protonvpn.com"),
    (("proton mail", "protonmail"), "proton-mail", "proton.me"),
    (("proton pass", "protonpass"), "proton-pass", "proton.me"),
    (("proton drive", "protondrive"), "proton-drive", "proton.me"),
    (("proton calendar", "protoncalendar"), "proton-calendar", "proton.me"),
    (
        ("proton unlimited", "proton duo", "proton family",
         "proton visionary", "proton"),
        "proton",
        "proton.me",
    ),

    # ── Telekomünikasyon / internet ─────────────────────────────────────
    # Alt markalar ana operatörden önce gelir: "Turkcell Superonline"
    # metni Turkcell'in mobil logosuna değil Superonline'ın kendi ikonuna
    # çözülmeli. Türkçe karakterli ve fatura/ekstrelerde görülen bitişik
    # yazımlar normalize edilerek aynı cache anahtarında birleşir.
    (
        ("turkcell superonline", "superonline"),
        "superonline",
        "superonline.net",
    ),
    (
        ("türk telekom", "turk telekom", "türktelekom", "turktelekom",
         "ttnet"),
        "turk-telekom",
        "turktelekom.com.tr",
    ),
    (
        ("vodafone türkiye", "vodafone turkey", "vodafone net", "vodafone"),
        "vodafone",
        "vodafone.com.tr",
    ),
    (
        ("turkcell",),
        "turkcell",
        "turkcell.com.tr",
    ),

    # ── Sosyal medya ────────────────────────────────────────────────────
    # Instagram'ın kendisi ücretsizdir; tanınan asıl ürün rozet/destek
    # paketi "Meta Verified"tir (Instagram + Facebook). Kullanıcı çoğunlukla
    # abonelik adını yalnızca "Instagram" olarak girer; ikon yine de
    # instagram.com'un kendi favicon'undan gelir — Meta'nın genel logosundan
    # daha tanınır olduğu için.
    (("meta verified", "instagram"), "instagram", "instagram.com"),

    # ── VPN ─────────────────────────────────────────────────────────────
    (("nordvpn", "nord vpn"), "nordvpn", "nordvpn.com"),
    (("expressvpn", "express vpn"), "expressvpn", "expressvpn.com"),

    # Genel "amazon" (Prime/Prime Video DIŞINDA, ör. Amazon Music/Kindle
    # Unlimited) — listenin SONUNDA durmalı: yukarıdaki "amazon prime" /
    # "prime video" girdisi daha özgül, önce sınanmalı. Sıra iterasyon
    # sırasıyla eşleşen İLK girdiyi döndürür (bkz. classify_brand).
    (("amazon",), "amazon", "amazon.com"),
)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9+]+", " ", ascii_text).split())


def classify_brand(text: str):
    """Metin için ``(cache_key, png_url)`` döndürür; eşleşme yoksa None'lar.

    DÜZELTME: `logo.clearbit.com` artık HİÇBİR DNS sunucusundan (1.1.1.1,
    8.8.8.8 dahil) çözülmüyor — Clearbit'in ücretsiz logo API'si kapatılmış.
    Bu yüzden abonelik kartlarında hiçbir marka ikonu hiç görünmüyordu; sessiz
    ağ hatası (bkz. fetch_and_cache_brand_icon'daki genel except) sorunu
    maskeliyordu. Google'ın kendi favicon servisine geçirildi: Clearbit gibi
    aracı bir üçüncü parti olmadan doğrudan Google altyapısından PNG döner,
    denenen tüm marka alan adları için çalıştığı doğrulandı.
    """
    normalized = _normalize(text)
    if not normalized:
        return None, None
    padded = f" {normalized} "
    for aliases, cache_key, domain in _BRANDS:
        if any(f" {_normalize(alias)} " in padded for alias in aliases):
            return (
                cache_key,
                f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
            )
    return None, None


def resolve_cached_brand_icon_path(text: str) -> str | None:
    """Yalnızca yerel önbelleği kontrol eder; ağ çağrısı yapmaz."""
    cache_key, _ = classify_brand(text)
    if not cache_key:
        return None
    path = os.path.join(BRAND_ICON_CACHE_DIR, f"{cache_key}.png")
    return path if os.path.exists(path) else None


def fetch_and_cache_brand_icon(text: str) -> bool:
    """Tanınan markanın PNG logosunu indirir; her hatada sessizce False döner."""
    cache_key, url = classify_brand(text)
    if not cache_key or not url:
        return False

    destination = os.path.join(BRAND_ICON_CACHE_DIR, f"{cache_key}.png")
    if os.path.exists(destination):
        return True

    try:
        import requests

        response = requests.get(url, timeout=4)
        content_type = response.headers.get("Content-Type", "").lower()
        if (
            response.status_code == 200
            and content_type.startswith("image/")
            and response.content
        ):
            os.makedirs(BRAND_ICON_CACHE_DIR, exist_ok=True)
            with open(destination, "wb") as image_file:
                image_file.write(response.content)
            return True
    except Exception:
        pass
    return False
