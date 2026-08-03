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
BRAND_ICON_CACHE_DIR = os.path.join(cache_dir(), "brand_icon_cache_v3")

# Yalnızca bozuk/anlamsız görüntüleri eler. Gerçek favicon'lar en az 16px'tir.
#
# KARAR GEÇMİŞİ: bir ara bu eşik 32'ydi ve altındakiler önbelleğe HİÇ
# alınmıyordu (gerekçe: 16 pikseli germek bulanık durur, vektör ikon daha
# temiz). Sahada yanlış çıktı — bazı markalar (turktelekom.com.tr,
# superonline.net) hiçbir sağlayıcıda 16x16'dan büyük favicon yayınlamıyor
# ve o markaların logosu tamamen kayboldu. Kullanıcı için markayı TANIMAK,
# kenarların keskinliğinden daha önemli: artık küçük logolar da kabul edilip
# `TARGET_ICON_PX`'e LANCZOS ile büyütülüyor.
MIN_ACCEPTABLE_ICON_PX = 16

# Aday bu boyuta ulaşınca kalan sağlayıcılar denenmez (erken çıkış).
# Daha küçük kalan logolar diske yazılmadan önce bu boyuta büyütülür.
TARGET_ICON_PX = 128

# "Bu markada kullanılabilir logo bulunamadı" bilgisi de önbelleklenir.
# NEDEN ZORUNLU: çağıran taraf (main.py::_render_recent_transactions) diskte
# ikon YOKSA yeniden indirmeyi tetikler. Negatif sonuç hatırlanmazsa
# turkcell gibi kalıcı olarak elenen her marka, dashboard'ın HER
# çiziminde sağlayıcı sayısı kadar HTTP isteği doğururdu.
# Süre sınırlı: marka ileride daha büyük bir favicon yayınlayabilir.
_MISS_TTL_SECONDS = 30 * 24 * 3600

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

    # ── Bankalar ve Cüzdanlar (Türkiye) ─────────────────────────────────
    (("garanti bbva", "garanti bankası", "garanti"), "garanti", "garantibbva.com.tr"),
    (("iş bankası", "is bankasi", "işcep", "iscep", "is bank"), "is-bankasi", "isbank.com.tr"),
    (("yapı kredi", "yapi kredi", "yapıkredi", "yapikredi"), "yapi-kredi", "yapikredi.com.tr"),
    (("ziraat bankası", "ziraat bankasi", "ziraat"), "ziraat", "ziraatbank.com.tr"),
    (("akbank", "axess"), "akbank", "akbank.com"),
    (("vakıfbank", "vakifbank", "vakıf bank", "vakif bank"), "vakifbank", "vakifbank.com.tr"),
    (("halkbank", "halk bank", "halk bankası"), "halkbank", "halkbank.com.tr"),
    (("enpara.com", "enpara"), "enpara", "enpara.com"),
    (("qnb finansbank", "finansbank", "qnb"), "qnb", "qnbfinansbank.com"),
    (("teb", "türk ekonomi bankası", "cepteteb"), "teb", "teb.com.tr"),
    (("denizbank", "deniz bank"), "denizbank", "denizbank.com"),
    (("kuveyt türk", "kuveyttürk", "kuveyt turk"), "kuveytturk", "kuveytturk.com.tr"),
    (("türkiye finans", "turkiye finans"), "turkiye-finans", "turkiyefinans.com.tr"),
    (("albaraka", "albaraka türk"), "albaraka", "albarakaturk.com.tr"),
    (("papara",), "papara", "papara.com"),
    (("ininal", "ininal kart"), "ininal", "ininal.com"),
    (("tosla",), "tosla", "tosla.com"),
    (("paycell",), "paycell", "paycell.com.tr"),
    (("nays",), "nays", "naysapp.com.tr"),
    (("pokus",), "pokus", "pokus.com.tr"),
    (("ozan", "ozan superapp"), "ozan", "ozan.com"),

    # Genel sağlayıcı adları SONDA durmalı: yukarıdaki daha özgül ürün/marka
    # girdileri önce sınanır. Örneğin banka ekstresindeki "GOOGLE *ProtonVPN"
    # genel Google ikonuna değil Proton VPN'e çözülmelidir.
    (("google",), "google", "google.com"),
    (("amazon",), "amazon", "amazon.com"),
)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9+]+", " ", ascii_text).split())


# Takma adların normalize edilmiş hâli SABİTTİR — import'ta bir kez hesaplanır.
#
# NEDEN (ölçüldü, 2026-08-02): eşleşme döngüsü her çağrıda 176 takma adın
# HEPSİNİ yeniden `_normalize` ediyordu (NFKD + regex). Eşleşmeyen bir metin
# için tek `classify_brand` çağrısı 220 µs sürüyordu. Ana sayfa bunu her
# abonelik ve her "son işlem" satırı için çağırdığı (üstelik bazı yollarda
# satır başına iki kez) maliyet doğrudan abonelik sayısıyla büyüyordu —
# "abonelik ekledikçe ana sayfa yavaşlıyor" şikayetinin ölçülebilir kısmı.
# Boşluklu ("` alias `") biçimde saklanır ki eşleşme testi düz bir alt-dize
# aramasına insin ve tam kelime sınırı korunsun.
_NORMALIZED_BRANDS = tuple(
    (
        tuple(f" {_normalize(alias)} " for alias in aliases),
        cache_key,
        domain,
    )
    for aliases, cache_key, domain in _BRANDS
)


def icon_source_urls(domain: str) -> tuple[str, ...]:
    """`domain` için sağlayıcı adaylarını sırayla döndürür.

    NEDEN TEK SAĞLAYICI YETMİYOR (ölçüldü, 2026-08-02): hiçbir sağlayıcı her
    markada en iyi değil. Aynı domain'ler için dönen en büyük kenar:

        domain             google sz=256   icon.horse
        claude.ai          248             48
        openai.com         180             256
        google.com         144             32

    Tek sağlayıcıya bağlanmak, o sağlayıcının zayıf olduğu markalarda
    kalitesiz ikon demek — Clearbit → Google Favicon → icon.horse geçişleri
    hep bu yüzden birbirini tam çözemedi. Bunun yerine adaylar sırayla
    denenir ve `TARGET_ICON_PX`'i geçen ilk sonuç kazanır; hiçbiri geçmezse
    en büyüğü seçilir (bkz. `fetch_and_cache_brand_icon`).
    """
    return (
        f"https://www.google.com/s2/favicons?domain={domain}&sz=256",
        f"https://icon.horse/icon/{domain}",
        f"https://unavatar.io/{domain}",
    )


def _classify_domain(text: str):
    """``(cache_key, domain)`` döndürür; eşleşme yoksa ``(None, None)``."""
    normalized = _normalize(text)
    if not normalized:
        return None, None
    padded = f" {normalized} "
    for aliases, cache_key, domain in _NORMALIZED_BRANDS:
        if any(alias in padded for alias in aliases):
            return cache_key, domain
    return None, None


def classify_brand(text: str):
    """Metin için ``(cache_key, png_url)`` döndürür; eşleşme yoksa None'lar.

    Döndürülen URL **birincil** sağlayıcıdır. İndirme yolu tek bir URL'ye
    bağlı değildir; `icon_source_urls` ile tüm adayları dener.
    """
    cache_key, domain = _classify_domain(text)
    if not cache_key:
        return None, None
    return cache_key, icon_source_urls(domain)[0]


def resolve_cached_brand_icon_path(text: str) -> str | None:
    """Yalnızca yerel önbelleği kontrol eder; ağ çağrısı yapmaz."""
    cache_key, _ = classify_brand(text)
    if not cache_key:
        return None
    path = os.path.join(BRAND_ICON_CACHE_DIR, f"{cache_key}.png")
    return path if os.path.exists(path) else None


def _miss_path(cache_key: str) -> str:
    return os.path.join(BRAND_ICON_CACHE_DIR, f"{cache_key}.miss")


def _miss_is_fresh(cache_key: str) -> bool:
    """Bu marka için yakın zamanda "uygun logo yok" kararı verildi mi?"""
    import time

    try:
        age = time.time() - os.path.getmtime(_miss_path(cache_key))
    except OSError:
        return False
    return age < _MISS_TTL_SECONDS


def _record_miss(cache_key: str) -> None:
    """Başarısız aramayı işaretler; hata olursa sessizce vazgeçilir (yalnızca
    bir sonraki denemenin erken çıkışını kaybederiz, davranış bozulmaz)."""
    try:
        os.makedirs(BRAND_ICON_CACHE_DIR, exist_ok=True)
        with open(_miss_path(cache_key), "wb"):
            pass
    except OSError:
        pass


def _decode_largest_frame(payload: bytes):
    """Baytları çözer ve EN BÜYÜK kareyi RGBA olarak döndürür; olmazsa None.

    Content-Type'a GÜVENİLMEZ, içerik gerçekten çözülerek doğrulanır. İki
    somut sebep (ikisi de sahada ölçüldü):

      * Sağlayıcılar `.png` isteğine ICO döndürebiliyor (icon.horse →
        claude.ai/turkcell.com.tr). Eski kod ham baytları `{key}.png` adıyla
        diske yazıyordu: dosya PNG diye adlandırılmış bir ICO oluyordu.
        Pillow içeriği sniff ettiği için masaüstünde şans eseri açılıyordu,
        ama uzantıya göre yükleyici seçen her ortamda (paketlenmiş Windows
        derlemesinde SDL2_image) sessizce kırılmaya açıktı.
      * ICO çok kareli olabilir; 16x16 kare 256x256 karenin yanında
        duruyorsa büyük olan seçilmelidir.
    """
    from io import BytesIO

    from PIL import Image

    image = Image.open(BytesIO(payload))
    if getattr(image, "format", None) == "ICO":
        try:
            largest = max(image.ico.sizes())
            image = image.ico.getimage(largest)
        except (AttributeError, KeyError, ValueError, OSError):
            # Pillow'un ICO iç yapısı sürümden sürüme değişebilir; en büyük
            # kare alınamazsa Image.open'ın seçtiği kareyle devam edilir.
            pass
    return image.convert("RGBA")


def fetch_and_cache_brand_icon(text: str) -> bool:
    """Tanınan markanın logosunu indirip GERÇEK PNG olarak önbelleğe alır.

    Adaylar sırayla denenir; `TARGET_ICON_PX`'i geçen ilk sonuçta durulur,
    yoksa en büyüğü seçilir. Sonuç `MIN_ACCEPTABLE_ICON_PX`'in altındaysa
    HİÇBİR ŞEY yazılmaz ve False döner — arayüz o markada kendi vektör
    ikonunu kullanmaya devam eder (bulanık bir 16x16 lekesi göstermektense).
    Ağ/HTTP/çözme hataları hiçbir zaman çağırana taşınmaz.
    """
    cache_key, domain = _classify_domain(text)
    if not cache_key or not domain:
        return False

    destination = os.path.join(BRAND_ICON_CACHE_DIR, f"{cache_key}.png")
    if os.path.exists(destination):
        return True
    if _miss_is_fresh(cache_key):
        return False

    best = None
    for url in icon_source_urls(domain):
        try:
            import requests

            response = requests.get(url, timeout=4)
            if response.status_code != 200 or not response.content:
                continue
            candidate = _decode_largest_frame(response.content)
        except (OSError, ValueError):
            # OSError, hem `requests.RequestException`'ı (ağ/DNS/timeout) hem
            # `PIL.UnidentifiedImageError`'ı (çözülemeyen içerik) kapsar —
            # ikisi de OSError türevi. Bir sağlayıcının düşmesi diğerlerinin
            # denenmesini engellememeli, o yüzden `continue`.
            continue
        if best is None or candidate.size[0] > best.size[0]:
            best = candidate
        if best.size[0] >= TARGET_ICON_PX:
            break

    if best is None or best.size[0] < MIN_ACCEPTABLE_ICON_PX:
        _record_miss(cache_key)
        return False

    if best.size[0] < TARGET_ICON_PX:
        # Küçük favicon'u LANCZOS ile büyüt. Keskinlik kazandırmaz (var olmayan
        # ayrıntı üretilemez) ama kenarları yumuşatır ve diskteki her logonun
        # ekranda küçültülerek çizilmesini sağlar — FitImage'daki `mipmap` da
        # ancak küçültmede devreye girer.
        try:
            from PIL import Image

            best = best.resize(
                (TARGET_ICON_PX, TARGET_ICON_PX), Image.LANCZOS)
        except (OSError, ValueError, AttributeError):
            pass  # büyütülemezse özgün boyutuyla yazılır, ikon yine görünür

    try:
        os.makedirs(BRAND_ICON_CACHE_DIR, exist_ok=True)
        best.save(destination, format="PNG")
        return True
    except (OSError, ValueError):
        return False
