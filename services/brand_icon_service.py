"""İşlem ve abonelik adları için best-effort marka ikonu servisi.

Tanınan bir marka adı metinden çıkarılır, PNG logo ayrı bir yerel dizinde
önbelleklenir. Ağ/HTTP/içerik hataları hiçbir zaman çağırana taşınmaz; arayüz
mevcut MDI ikonuyla çalışmaya devam eder.
"""

import os
import re
import unicodedata


BRAND_ICON_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "brand_icon_cache",
)

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
)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9+]+", " ", ascii_text).split())


def classify_brand(text: str):
    """Metin için ``(cache_key, png_url)`` döndürür; eşleşme yoksa None'lar."""
    normalized = _normalize(text)
    if not normalized:
        return None, None
    padded = f" {normalized} "
    for aliases, cache_key, domain in _BRANDS:
        if any(f" {_normalize(alias)} " in padded for alias in aliases):
            return (
                cache_key,
                f"https://logo.clearbit.com/{domain}?size=128&format=png",
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
