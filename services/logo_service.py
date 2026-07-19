"""
Logo Service — Varlık Geçmişi listesinde Kripto, Döviz ve Altın kalemleri için
uzak logo/bayrak/simge görseli çeker, yerel diske önbellekler.

BIST hisseleri için zaten yerel bir logo mekanizması var (mixins/asset_mixin.py
get_stock_logo, assets/stock_logos/) — burada tekrarlanmıyor, sadece Kripto,
Döviz ve Altın için (bunların yerel karşılığı yok) ele alınıyor. Tahvil/Diğer
için de logo aranmıyor, mevcut renkli MDI ikon fallback'i yeterli.

Ağ erişimi HER ZAMAN best-effort'tur: zaman aşımı, DNS hatası, 404, bozuk
içerik gibi durumların hiçbiri exception fırlatmaz — fetch_and_cache_logo
sessizce False döner, çağıran taraf (asset_mixin.py) mevcut MDI ikonuna düşer.
"""
import os

LOGO_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo_cache"
)

# Kripto sembolü (ör. 'BTC-USD' -> 'BTC') -> CoinCap ikon CDN'inde kullanılan kod.
# Yalnızca tanınan yaygın coin'ler için; eşleşmeyen semboller ağa hiç gidilmeden
# fallback ikona düşer (yanlış tahminle boşa istek atılmaz).
_CRYPTO_SYMBOLS = {"BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT"}

# Döviz kodu -> bayrak CDN'inde (flagcdn.com) kullanılan ISO ülke kodu.
_FOREX_COUNTRY = {
    "USD": "us", "EUR": "eu", "GBP": "gb", "JPY": "jp",
    "CHF": "ch", "CAD": "ca", "AUD": "au",
}

# Altın için kod içinde aranan anahtar kelimeler (Yahoo Finance sembolü
# "GC=F", uluslararası kod "XAU", serbest girilen "ALTIN" metni veya fiziksel
# altın türleri için dahili "GOLD-*" semboller — bkz. asset_mixin.py _GOLD_TYPES).
_GOLD_KEYWORDS = ("GC=F", "XAU", "ALTIN", "GOLD")
# Twemoji CDN (jsdelivr) üzerinden sabit bir altın külçe/madeni para görseli.
_GOLD_LOGO_URL = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1fa99.png"


def _classify(code: str):
    """Ham kod (ör. 'BTC-USD', 'USDTRY=X', 'GC=F') için (cache_key, remote_url)
    döndürür. Tanınmayan/desteklenmeyen kodlar için (None, None) — bu durumda
    hiçbir ağ çağrısı denenmez."""
    c = (code or "").strip().upper()

    if c.endswith("-USD"):
        sym = c.split("-")[0]
        if sym in _CRYPTO_SYMBOLS:
            return sym, f"https://assets.coincap.io/assets/icons/{sym.lower()}@2x.png"

    elif c.endswith("=X") and len(c) >= 5:
        base = c[:3]
        if base in _FOREX_COUNTRY:
            return base, f"https://flagcdn.com/w80/{_FOREX_COUNTRY[base]}.png"

    elif any(keyword in c for keyword in _GOLD_KEYWORDS):
        return "XAU", _GOLD_LOGO_URL

    return None, None


def resolve_remote_logo_url(code: str) -> str | None:
    """Ham kod için (AĞ ÇAĞRISI YOK) doğrudan bir AsyncImage/FitImage
    `source`'una verilebilecek uzak logo URL'sini döndürür; tanınmayan kodlar
    için None. Asıl ağ isteğini widget'ın kendi async loader'ı yapar, bu
    fonksiyon sadece URL üretir — Varlık Ekle akışındaki anlık önizleme için
    kullanılır (kalıcı önbelleğe yazmaz, bkz. fetch_and_cache_logo)."""
    _, url = _classify(code)
    return url


def resolve_cached_logo_path(code: str) -> str | None:
    """Sadece yerel diski kontrol eder (AĞ ÇAĞRISI YOK) — UI thread'inden
    güvenle çağrılabilir. Daha önce başarıyla indirilmiş bir logo varsa yolunu
    döner, yoksa None."""
    cache_key, _ = _classify(code)
    if not cache_key:
        return None
    path = os.path.join(LOGO_CACHE_DIR, f"{cache_key}.png")
    return path if os.path.exists(path) else None


def fetch_and_cache_logo(code: str) -> bool:
    """Arka plan thread'inden çağrılmalı — bloklayan bir ağ isteği içerir.
    Logoyu indirip önbelleğe yazar. Kod tanınmıyorsa, ağ erişilemiyorsa, zaman
    aşımına uğrarsa veya dönen içerik görsel değilse sessizce False döner;
    hiçbir koşulda exception fırlatmaz."""
    cache_key, url = _classify(code)
    if not cache_key or not url:
        return False

    dest = os.path.join(LOGO_CACHE_DIR, f"{cache_key}.png")
    if os.path.exists(dest):
        return True

    try:
        import requests
        resp = requests.get(url, timeout=4)
        content_type = resp.headers.get("Content-Type", "")
        if resp.status_code == 200 and content_type.startswith("image/") and resp.content:
            os.makedirs(LOGO_CACHE_DIR, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False
