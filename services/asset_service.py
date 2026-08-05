"""
Asset Service — yfinance tabanlı canlı fiyat çekme & K/Z hesaplama.

Borsa İstanbul (BIST) hisselerinde kullanıcı sembolü (örn: 'THYAO') girer;
bu servis otomatik olarak '.IS' ekleyerek Yahoo Finance'tan veri çeker.

Desteklenen asset_type değerleri:
    'Hisse'  → BIST hissesi  (THYAO → THYAO.IS)
    'Altın'  → GC=F veya XAUUSD  (ons/USD çekilir, ₺/gram'a çevrilir — bkz. _normalize_to_try)
               Çeyrek/Yarım/Tam/Ons gibi fiziksel altın türleri için gerçek bir
               yfinance sembolü yoktur; bunun yerine dahili GOLD-* sembolleri
               kullanılır ve gram/₺ fiyatı üzerinden çarpanla hesaplanır (bkz.
               GOLD_TYPE_MULTIPLIERS, _fetch_gold_gram_price_try).
    'Tahvil' → sembol direkt gönderilir
    'Döviz'  → sembol direkt gönderilir (örn: USDTRY=X, zaten ₺ cinsinden)
    'Kripto' → CODE-USD çekilir, ₺'ye çevrilir (bkz. _normalize_to_try)
    'Diğer'  → sembol direkt gönderilir, çevrilmez

Not: Uygulamadaki tüm alım fiyatları (`purchase_price`) kullanıcı tarafından ₺
cinsinden girilir (bkz. mixins/asset_mixin.py "Alım Fiyatı (₺)" alanı). Altın ve
Kripto için yfinance sembolleri USD döndürdüğünden, bu iki tür için güncel fiyat
burada ₺'ye çevrilmeden K/Z hesabı (services/asset_service.calculate_pnl) TL alım
fiyatını USD güncel fiyatla kıyaslar ve tamamen yanlış sonuç üretirdi.
"""

import sqlite3
import threading
import time
from datetime import date

from utils.errors import (
    ArchlenceError,
    DecryptionError,
    KeyUnavailableError,
)


def _log():
    """Fiyat/portföy hata kaydı için merkezi rotating log.

    NEDEN (v0.0.1'de düzeltildi): bu modüldeki fiyat çekme hataları `print()`
    ile bildiriliyordu. Paketlenmiş Windows uygulaması `console=False` ile
    derleniyor (archlence.spec) — yani stdout/stderr hiçbir yere gitmiyor ve o
    mesajlar TAMAMEN kayboluyordu. Sonuç: "Windows'ta altın fiyatı yüklenmiyor"
    gibi bir şikâyette elimizde tek bir satır bile kanıt olmuyordu.

    Logger tembel çözülür: modül import'unda çağırmak log dizinini erkenden
    oluşturur ve testlerdeki XDG yönlendirmesinden önce çalışabilirdi.
    """
    from utils.logging_config import get_logger

    return get_logger()


_PORTFOLIO_CACHE_TABLE = "asset_portfolio_cache"
_PORTFOLIO_CACHE_TTL = 300

GRAMS_PER_TROY_OUNCE = 31.1034768

# -------------------------------------------------------------------------
# GLOBAL PRE-CACHE (WARM-UP)
# -------------------------------------------------------------------------
_asset_data_cache = {
    "summary": {"cash": 0, "card_debt": 0, "net": 0},
    "accounts": [],
    "recent": {},
    "active_assets_result": None,
    "ready": False
}
_warmup_lock = threading.Lock()
_warmup_generation = 0

# Bakiyeye dokunan bir yazım oldu ama snapshot henüz tazelenmedi mi?
#
# NEDEN: `render_accounts` hız için hiç SQL çalıştırmaz, yalnızca
# `_asset_data_cache`ten çizer. Bu, yazan her akışın snapshot'ı elle
# tazelemesini şart koşuyordu ve akışların ÇOĞU bunu yapmıyordu: yalnızca işlem
# ekleme (transaction_mixin) ve kart silme (invalidate_asset_data_cache) doğru
# davranıyordu. Hesap ekleme, kart borcu ödeme, birikim hedefine para atma ve
# otomatik ödeme talimatları bakiyeyi DB'de değiştirip ekranda ESKİ değeri
# bırakıyordu — kullanıcının gördüğü "hesap ekledim, toplam güncellendi ama
# listedeki bakiye eski" hatası buydu. (Ana sayfadaki toplam tutarlı
# görünüyordu çünkü o `_compute_dashboard_metrics` ile her seferinde DB'den
# taze okunuyor; liste ise RAM'den geliyordu — sayılar değil, OKUMA YOLLARI
# ayrışmıştı.)
#
# Çözüm tek tek çağrı noktalarına tazeleme eklemek değil (unutulmaya devam
# ederdi): yazan taraf bayrağı DÜŞÜRÜR, okuyan taraf gerekiyorsa tazeler.
_account_cache_stale = False
_financial_data_revision = 0


def mark_account_cache_stale():
    """Finansal yazımdan sonra hesap snapshot'ını ve grafik sürümünü eskitir."""
    global _account_cache_stale, _financial_data_revision
    _account_cache_stale = True
    _financial_data_revision += 1


def mark_financial_data_changed():
    """Türetilmiş finansal sonuçları eskitir — hesap snapshot'ına DOKUNMADAN.

    `mark_account_cache_stale` bakiyeye dokunan yazımlar içindir. Bazı
    değişiklikler ise bakiyeyi HİÇ değiştirmediği hâlde türetilmiş özeti
    değiştirir: kategori `importance` alanı (main/extra ayrımı)
    `summarize_transactions`'ın kovalarını belirliyor. Bunun için hesap
    snapshot'ını da eskitmek gereksiz iş olurdu, ama sürüm artmazsa
    dashboard metrik önbelleği BAYAT kalırdı.
    """
    global _financial_data_revision
    _financial_data_revision += 1


def get_financial_data_revision():
    """Grafiklerin dayandığı finansal verinin süreç-içi monoton sürümü."""
    return _financial_data_revision


def financial_chart_cache_key(period):
    """Dönem + veri sürümü + takvim gününden güvenli grafik anahtarı üretir."""
    return (str(period), _financial_data_revision, date.today().isoformat())


def ensure_account_cache_fresh():
    """Bayat snapshot'ı tazeleyip GÜNCEL sözlüğü döndürür.

    Dönüş değeri önemlidir: `refresh_account_cache_snapshot` modül global'ini
    YENİDEN ATAR, bu yüzden `from ... import _asset_data_cache` ile alınmış eski
    bir yerel ad tazelemeden sonra hâlâ eski sözlüğe bakar. Çağıran bu
    fonksiyonun döndürdüğünü kullanmalıdır.

    Henüz ısınmamış (ready=False) cache tazelenmez: açılış worker'ı zaten
    yazımdan sonraki DB'yi okuyacak ve ağ gerektiren `active_assets_result`
    alanını da dolduracak; araya girmek onu None'a düşürürdü.
    """
    global _account_cache_stale
    if not _account_cache_stale:
        return _asset_data_cache
    if not (_asset_data_cache and _asset_data_cache.get("ready")):
        return _asset_data_cache
    _account_cache_stale = False
    return refresh_account_cache_snapshot()


def invalidate_asset_data_cache(deleted_account_id=None, deleted_card_debt=0.0):
    """Eski worker'ı iptal edip snapshot'tan silinen kartı atomik çıkarır."""
    global _asset_data_cache, _warmup_generation, _account_cache_stale
    global _financial_data_revision
    # Snapshot burada zaten cerrahi olarak yeniden kuruluyor; bayrağı düşürmek
    # `render_accounts`'ın üstüne bir de tam tazeleme yapmasını önler (silme
    # yolundaki solma animasyonu bu cerrahi güncellemeye bağlı).
    _account_cache_stale = False
    _financial_data_revision += 1
    with _warmup_lock:
        _warmup_generation += 1
        previous = _asset_data_cache or {}
        if deleted_account_id is not None:
            account_id = int(deleted_account_id)
            old_summary = previous.get("summary") or {}
            debt = max(0.0, float(deleted_card_debt or 0))
            old_card_debt = float(old_summary.get("card_debt") or 0)
            summary = {
                "cash": float(old_summary.get("cash") or 0),
                "card_debt": max(0.0, old_card_debt - debt),
                "net": float(old_summary.get("net") or 0) + debt,
            }
            accounts_raw = previous.get("accounts")
            accounts_list = accounts_raw if isinstance(accounts_raw, list) else []
            accounts = [
                account for account in accounts_list
                if isinstance(account, dict) and int(account.get("id", 0)) != account_id
            ]
            recent_raw = previous.get("recent")
            recent_dict = recent_raw if isinstance(recent_raw, dict) else {}
            recent = dict(recent_dict)
            recent.pop(str(account_id), None)
            _asset_data_cache = {
                "summary": summary,
                "accounts": accounts,
                "recent": recent,
                "active_assets_result": previous.get("active_assets_result"),
                "ready": True,
            }
            return

        _asset_data_cache = {
            "summary": {"cash": 0, "card_debt": 0, "net": 0},
            "accounts": [],
            "recent": {},
            "active_assets_result": None,
            "ready": False,
        }

def start_data_warmup(callback=None):
    """
    Arka planda tüm verileri önceden yükler (Data Warm-up).
    Uygulama açılışında çağrılır, veriler _asset_data_cache içine yazılır.
    'Veri Hazır' flag'ini kaldırır.
    """
    global _warmup_generation
    with _warmup_lock:
        _warmup_generation += 1
        generation = _warmup_generation

    def publish(summary, accounts, recent, result):
        with _warmup_lock:
            if generation != _warmup_generation:
                return
            _asset_data_cache["summary"] = summary
            _asset_data_cache["accounts"] = accounts
            _asset_data_cache["recent"] = recent
            _asset_data_cache["active_assets_result"] = result
            # Son alan olarak yazılır; UI yalnız eksiksiz snapshot görür.
            _asset_data_cache["ready"] = True
        if callback:
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: callback(), 0)

    def worker():
        from services.account_service import AccountService
        from services.transaction_service import TransactionService
        try:
            summary = AccountService.get_net_worth()
            accounts = AccountService.get_accounts()
            recent = {}
            for account in accounts:
                if account["account_type"] == "credit_card" or account.get("has_card_number", False):
                    recent[account["id"]] = TransactionService.get_recent_for_account(account["id"], limit=3)
            
            def on_non_try(res):
                publish(summary, accounts, recent, res)

            fetch_active_non_try_total(on_non_try)
        # BİLEREK GENİŞ (incelendi, daraltılmayacak): aşağıdaki yorumun
        # gerekçesi tam da budur — bu blok, ne olursa olsun bir terminal
        # snapshot yayımlanmasını GARANTİ eder. Daraltmak, listelenmeyen bir
        # hata türünde `publish` çağrısının hiç yapılmaması ve arayüzün
        # sonsuza kadar spinner'da kalması demek olurdu.
        except Exception as e:
            _log().error("Data warm-up failed: %s", e, exc_info=True)
            # Hata durumunda da terminal snapshot yayımlanır; UI spinner/polling
            # döngüsünde sonsuza dek kalmaz.
            publish(
                {"cash": 0, "card_debt": 0, "net": 0}, [], {},
                {"total": 0.0, "asset_count": 0, "priced_count": 0,
                 "cached_count": 0, "complete": True, "error": str(e)},
            )
            
    threading.Thread(target=worker, daemon=True).start()


def refresh_account_cache_snapshot():
    """Hesap bakiyelerini ağ beklemeden mevcut cache'e atomik olarak yazar.

    İşlem kaydı worker'ından çağrılır; UI thread'indeki ``render_accounts``
    böylece eski açılış snapshot'ını değil yeni DB durumunu görür.
    """
    global _asset_data_cache, _account_cache_stale
    # Taze snapshot yazılıyor: bekleyen bayat işareti varsa düşer.
    _account_cache_stale = False
    from services.account_service import AccountService
    from services.transaction_service import TransactionService

    summary = AccountService.get_net_worth()
    accounts = AccountService.get_accounts()
    recent = {}
    for account in accounts:
        if (
            account["account_type"] == "credit_card"
            or account.get("has_card_number", False)
        ):
            recent[account["id"]] = TransactionService.get_recent_for_account(
                account["id"], limit=3
            )

    with _warmup_lock:
        previous = _asset_data_cache or {}
        _asset_data_cache = {
            "summary": summary,
            "accounts": accounts,
            "recent": recent,
            "active_assets_result": previous.get("active_assets_result"),
            "ready": True,
        }
    return _asset_data_cache

# USD/TRY kuru için modül seviyesinde, kısa ömürlü önbellek — Altın/Kripto
# fiyatlarını her seferinde ayrı bir yfinance isteğiyle çevirmemek için.
_usdtry_cache = {"rate": None, "time": 0.0}
_USDTRY_CACHE_TTL = 300  # 5 dakika — uygulamadaki diğer fiyat önbellekleriyle tutarlı

# Fiziksel altın türleri için gerçek bir yfinance sembolü yok; bu dahili
# sembollerin fiyatı gram altın (GC=F) fiyatının standart piyasa çarpanıyla
# türetilir (ör. Çeyrek Altın ≈ 1,75 gram karşılığı).
GOLD_TYPE_MULTIPLIERS = {
    "GOLD-ONS": GRAMS_PER_TROY_OUNCE,  # 1 ons = ~31.10 gram karşılığı
    "GOLD-CEYREK": 1.75,
    "GOLD-YARIM": 3.5,
    "GOLD-TAM": 7.0,
}

from typing import Any
_gold_gram_cache: dict[str, Any] = {"price": None, "time": 0.0}
_GOLD_GRAM_CACHE_TTL = 300


def _fetch_usdtry_rate() -> float | None:
    """Güncel USD/TRY kurunu döndürür (₺ cinsinden 1 USD). 5 dakika önbelleklenir;
    ağ hatasında eski (varsa) değeri, hiç yoksa None döner."""
    now = time.time()
    if _usdtry_cache["rate"] is not None and (now - _usdtry_cache["time"]) < _USDTRY_CACHE_TTL:
        return _usdtry_cache["rate"]

    import math
    import yfinance as yf
    try:
        hist = yf.Ticker("USDTRY=X").history(period="5d")
        if not hist.empty:
            rate = float(hist["Close"].dropna().iloc[-1])
            if not math.isnan(rate) and not math.isinf(rate) and rate > 0:
                _usdtry_cache["rate"] = rate
                _usdtry_cache["time"] = now
                return rate
    except Exception:
        _log().exception("USD/TRY kuru çekilemedi")
    return _usdtry_cache["rate"]  # varsa bayat değeri döndür, yoksa None


def _normalize_to_try(raw_price: float, asset_type: str) -> float | None:
    """yfinance'tan USD cinsinden gelen ham fiyatı ₺'ye çevirir.

    'Altın' için ayrıca ons -> gram dönüşümü uygular (yfinance altın sembolleri
    ons/USD fiyat verir, uygulama gram/₺ üzerinden çalışır). 'Kripto' için sadece
    USD -> ₺ çevrilir. Diğer türler zaten ₺ cinsinden geldiği için dokunulmaz.
    Kur çekilemezse None döner (çağıran taraf bunu 'fiyat alınamadı' sayar)."""
    usdtry = _fetch_usdtry_rate()
    if usdtry is None:
        return None
    if asset_type == "Altın":
        return (raw_price * usdtry) / GRAMS_PER_TROY_OUNCE
    return raw_price * usdtry  # Kripto


# ─── Sembol normalleştirme & aday oluşturma ────────────────────────────────────

def get_ticker_candidates(asset_code: str, asset_type: str) -> list:
    """Kullanıcının girdiği kod için olası Yahoo Finance sembollerini döndürür."""
    code = asset_code.strip().upper()
    candidates = []
    
    if asset_type == "Hisse":
        if not code.endswith(".IS") and "." not in code:
            candidates.append(f"{code}.IS") # Önce BIST
            candidates.append(code)         # Sonra Amerikan vb.
        else:
            candidates.append(code)
            
    elif asset_type == "Altın":
        if code in ["ALTIN", "GOLD", "GRAM", "XAU", "GLD"]:
            candidates.extend(["GC=F", "XAUUSD=X"])
        else:
            candidates.append(code)
            
    elif asset_type == "Döviz":
        if len(code) == 3:
            candidates.extend([f"{code}TRY=X", f"{code}USD=X"])
        if not code.endswith("=X"):
            candidates.append(f"{code}=X")
        candidates.append(code)
        
    elif asset_type in ["Kripto", "Crypto"]:
        if "-" not in code:
            candidates.append(f"{code}-USD")
        candidates.append(code)
        
    else:
        candidates.append(code)
        
    return candidates


# ─── Tek bir varlık için canlı fiyat çek ─────────────────────────────────────

def _fetch_gold_gram_price_try() -> float | None:
    """Güncel gram altın (GC=F) fiyatını ₺ cinsinden döndürür; 5 dakika
    önbelleklenir. Çeyrek/Yarım/Tam/Ons gibi türetilmiş altın türleri bu temel
    fiyatı GOLD_TYPE_MULTIPLIERS ile çarpar (bkz. fetch_current_price)."""
    now = time.time()
    if _gold_gram_cache["price"] is not None and (now - _gold_gram_cache["time"]) < _GOLD_GRAM_CACHE_TTL:
        return _gold_gram_cache["price"]

    price = fetch_current_price("GC=F", "Altın")
    if price is not None:
        _gold_gram_cache["price"] = price
        _gold_gram_cache["time"] = now
        return price
    return _gold_gram_cache["price"]  # varsa bayat değeri döndür, yoksa None


def fetch_current_price(asset_code: str, asset_type: str) -> float | None:
    """
    Verilen sembol için güncel kapanış/anlık fiyatı ₺ cinsinden döndürür.
    Alternatif sembolleri dener. 'Altın' ve 'Kripto' için yfinance'tan USD
    gelen ham fiyat _normalize_to_try ile ₺'ye çevrilir (bkz. modül docstring'i).
    GOLD-ONS/GOLD-CEYREK/GOLD-YARIM/GOLD-TAM gibi dahili sembollerin gerçek bir
    yfinance karşılığı yoktur; bunlar için gram altın fiyatı çekilip standart
    piyasa çarpanıyla ölçeklenir. Hata durumunda None döndürür.
    """
    code = (asset_code or "").strip().upper()
    if asset_type == "Altın" and code in GOLD_TYPE_MULTIPLIERS:
        gram_price = _fetch_gold_gram_price_try()
        if gram_price is None:
            return None
        return gram_price * GOLD_TYPE_MULTIPLIERS[code]

    import math
    import yfinance as yf
    import logging

    # yfinance ve önbellek kütüphanelerinin stderr loglarını tamamen sustur
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)

    candidates = get_ticker_candidates(asset_code, asset_type)

    for ticker_sym in candidates:
        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].dropna().iloc[-1])
                if not math.isnan(price) and not math.isinf(price):
                    if asset_type in ("Altın", "Kripto", "Crypto"):
                        return _normalize_to_try(price, "Altın" if asset_type == "Altın" else "Kripto")
                    return price
        except Exception as exc:
            # EXCEPTION-AUDIT: bilinçli geniş — yfinance + requests +
            # pandas, üç ayrı üçüncü parti yüzeyi tek blokta.
            # BİLEREK geniş: tek blokta üç ayrı üçüncü parti yüzeyi var —
            # yfinance'in `YFException` ailesi, altındaki requests/OSError ve
            # üstündeki pandas indeksleme. Kümeyi eksik yazmak, kütüphane
            # sürümü değişince aday-deneme döngüsünü sessizce kırar.
            # Sessiz `pass` yerine debug'a düşürüldü: aday sembollerin
            # ELENMESİ normal akış, hata değil — ama fiyat hiç bulunamadığında
            # nedenin izi kalmalı.
            _log().debug(
                "%s için '%s' adayı fiyat vermedi: %r",
                asset_code, ticker_sym, exc)

    return None



# ─── BIST 100 toplu fiyat çekme (hisse seçim listesi için) ───────────────────

# BIST kodu olmayan istisnalar → doğrudan Yahoo Finance sembolü
_BIST_SYMBOL_OVERRIDES = {"USDTR": "USDTRY=X"}


def fetch_bist100_prices(codes: list, callback) -> None:
    """
    Arka plan thread'inde BIST hisse listesinin fiyatlarını tek toplu istekle
    çeker (Yahoo Finance BIST verisi, ~15 dk gecikmeli).
    Tamamlanınca callback({kod: fiyat}) çağrılır; alınamayanlar sözlükte olmaz.
    """
    import threading

    def _worker():
        import math
        import logging
        import yfinance as yf

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)

        tickers = {
            code: _BIST_SYMBOL_OVERRIDES.get(code, f"{code}.IS")
            for code in codes
        }
        prices = {}
        try:
            data = yf.download(
                list(tickers.values()),
                period="1d",
                progress=False,
                threads=True,
            )
            close = data["Close"].iloc[-1]
            for code, sym in tickers.items():
                try:
                    price = float(close[sym])
                    if not math.isnan(price) and not math.isinf(price):
                        prices[code] = price
                except (KeyError, IndexError, TypeError, ValueError):
                    # Ölçülen pandas yüzeyi: sembol satırda yoksa KeyError;
                    # yf.download TEK ticker'da Series yerine skaler döndüğünde
                    # IndexError ("invalid index to scalar variable");
                    # hücre None ise TypeError; metin ("n/a") ise ValueError.
                    pass
        except Exception as e:
            _log().error("BIST100 fiyat çekme hatası: %s", e, exc_info=True)
        callback(prices)

    threading.Thread(target=_worker, daemon=True).start()


# ─── K/Z hesaplama ────────────────────────────────────────────────────────────

def calculate_pnl(current_price: float, purchase_price: float, quantity: float) -> dict:
    """
    Kâr/Zarar bilgisini hesaplar.

    Dönüş değeri::
        {
            'pnl_amount':  float,   # TL cinsinden net K/Z (current - purchase) * qty
            'pnl_pct':     float,   # Yüzdesel K/Z
            'total_value': float,   # Güncel portföy değeri
            'total_cost':  float,   # Alım maliyeti
            'signal':      str      # 'profit' | 'loss' | 'breakeven'
        }
    """
    total_cost  = purchase_price * quantity
    total_value = current_price  * quantity
    pnl_amount  = total_value - total_cost
    pnl_pct     = ((current_price - purchase_price) / purchase_price) * 100 if purchase_price > 0 else 0.0

    if pnl_pct > 0:
        signal = "profit"
    elif pnl_pct < 0:
        signal = "loss"
    else:
        signal = "breakeven"

    return {
        "pnl_amount":  round(pnl_amount,  2),
        "pnl_pct":     round(pnl_pct,     2),
        "total_value": round(total_value, 2),
        "total_cost":  round(total_cost,  2),
        "signal":      signal,
    }


# ─── Renk kodlaması (KivyMD rgba) ────────────────────────────────────────────

PNL_COLORS = {
    "profit":    [0.08, 0.86, 0.29, 1],   # yeşil
    "loss":      [0.95, 0.22, 0.22, 1],   # kırmızı
    "breakeven": [0.99, 0.86, 0.02, 1],   # sarı
    "pending":   [0.65, 0.65, 0.65, 1],   # gri (veri bekleniyor)
    "error":     [0.9, 0.2, 0.2, 1],      # kırmızı (bağlantı hatası)
}


def get_pnl_color(signal: str) -> list:
    return PNL_COLORS.get(signal, PNL_COLORS["pending"])


def _read_cached_portfolio(assets, allow_stale=False):
    """Return a complete cached portfolio when IDs/positions still match."""
    import json
    from database.db import get_connection

    if not assets:
        return []
    conn = get_connection()
    try:
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {_PORTFOLIO_CACHE_TABLE} (
            asset_id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )""")
        rows = conn.execute(
            f"SELECT asset_id, payload, updated_at FROM {_PORTFOLIO_CACHE_TABLE}"
        ).fetchall()
        conn.commit()
    finally:
        conn.close()
    by_id = {int(row["asset_id"]): row for row in rows}
    now = int(time.time())
    cached = []
    for asset in assets:
        row = by_id.get(int(asset["id"]))
        if row is None or (not allow_stale and now - int(row["updated_at"]) > _PORTFOLIO_CACHE_TTL):
            return None
        try:
            entry = json.loads(row["payload"])
        except (TypeError, ValueError):
            return None
        if (float(entry.get("quantity", -1)) != float(asset.get("quantity", 0))
                or float(entry.get("purchase_price", -1)) != float(asset.get("purchase_price", 0))):
            return None
        cached.append(entry)
    return cached


def _store_cached_portfolio(enriched):
    import json
    from database.db import get_connection

    if not enriched:
        return
    conn = get_connection()
    try:
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {_PORTFOLIO_CACHE_TABLE} (
            asset_id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )""")
        now = int(time.time())
        conn.executemany(
            f"""INSERT INTO {_PORTFOLIO_CACHE_TABLE}(asset_id, payload, updated_at)
                VALUES (?, ?, ?) ON CONFLICT(asset_id) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""",
            [(int(item["id"]), json.dumps(item, ensure_ascii=False), now)
             for item in enriched],
        )
        conn.commit()
    finally:
        conn.close()


# ─── Tüm portföy için toplu fiyat çekme (threading destekli) ─────────────────

def fetch_portfolio_with_prices(assets: list, callback, item_callback=None,
                                cache_callback=None, force_refresh=False) -> None:
    """
    Arka plan thread'inde tüm varlıkların canlı fiyatlarını TEK bir toplu
    yfinance isteğiyle çeker (bkz. fetch_bist100_prices'daki aynı toplu indirme
    deseni). Önceki sürüm her varlık için ayrı, sıralı bir yfinance çağrısı
    yapıyordu; 12+ varlıklı bir portföyde bu, uygulamanın onlarca saniye ila
    birkaç dakika donmasına yol açıyordu.

    GOLD-ONS/GOLD-CEYREK/GOLD-YARIM/GOLD-TAM gibi dahili altın sembollerinin
    gerçek bir yfinance karşılığı yoktur; bunlar toplu istekten hariç tutulur,
    gerektiğinde tek seferlik GC=F (gram altın) fiyatından çarpanla türetilir
    (bkz. GOLD_TYPE_MULTIPLIERS).

    Tamamlandığında callback(enriched_assets) çağrılır. Her eleman şunları
    içerir (orijinal asset dict + ekstra alanlar):
        current_price, pnl_amount, pnl_pct, total_value, total_cost, signal
    """
    # Parent/UI process: cache-first, then perform all yfinance/pandas work in
    # a separate interpreter. The child re-enters this function with the env
    # flag and uses the existing local worker implementation below.
    import os
    if not os.environ.get("ARCHLENCE_ASSET_PRICE_CHILD"):
        def _isolated_worker():
            fresh = None if force_refresh else _read_cached_portfolio(assets)
            if fresh is not None:
                callback(fresh)
                return
            stale = _read_cached_portfolio(assets, allow_stale=True)
            if stale and cache_callback is not None:
                cache_callback(stale)

            import json
            import subprocess
            import sys
            import tempfile
            fd, output_path = tempfile.mkstemp(prefix="archlence_prices_", suffix=".json")
            os.close(fd)
            try:
                env = dict(os.environ)
                env["ARCHLENCE_ASSET_PRICE_CHILD"] = "1"
                # cwd=proje kökü ŞART: `-m services.asset_price_worker` modülü
                # bulmak için proje kökünün sys.path'te olmasını ister. Uygulama
                # başka bir dizinden başlatılırsa (ya da paketlenmişse) alt süreç
                # ModuleNotFoundError ile ölüyordu — DEVNULL bunu gizliyordu.
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                proc = subprocess.run(
                    [sys.executable, "-m", "services.asset_price_worker", output_path],
                    input=json.dumps(assets, ensure_ascii=False), text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=70, check=False, env=env, cwd=project_root,
                )
                # Sessiz ölümü artık logluyoruz: dönüş kodu 0 değilse veya
                # stderr doluysa neden görünür olsun (eskiden hiç iz kalmıyordu).
                if proc.returncode != 0:
                    _log().error(
                        "Fiyat worker'ı hata kodu %s ile döndü: %s",
                        proc.returncode,
                        (proc.stderr or "").strip()[:500],
                    )
                elif proc.stderr and proc.stderr.strip():
                    _log().warning(
                        "Fiyat worker uyarısı: %s",
                        proc.stderr.strip()[:500],
                    )
                try:
                    with open(output_path, "r", encoding="utf-8") as stream:
                        enriched = json.load(stream)
                except (OSError, ValueError):
                    enriched = stale or []
                if enriched:
                    _store_cached_portfolio(enriched)
                callback(enriched)
            # EXCEPTION-AUDIT: bilinçli geniş — izole alt süreç sınırı.
            # BİLEREK GENİŞ (incelendi): izole alt süreç sınırı. Aşağıdaki
            # `callback(stale or [])`'in HER durumda çalışması gerekiyor;
            # daraltmak, arayüzün sonuç beklerken asılı kalmasına yol açar.
            except Exception as exc:
                _log().error("İzole fiyat worker hatası: %s", exc, exc_info=True)
                callback(stale or [])
            finally:
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

        threading.Thread(target=_isolated_worker, daemon=True).start()
        return

    def _error_entries():
        result = []
        for asset in assets:
            entry = dict(asset)
            entry.update({
                "current_price": None, "pnl_amount": None, "pnl_pct": None,
                "total_value": None, "total_cost": None, "signal": "error",
            })
            result.append(entry)
        return result

    def _worker_impl():
        import math
        import logging
        import yfinance as yf

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        logging.getLogger("requests_cache").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)

        # Her varlık için toplu indirmede kullanılacak tek yfinance sembolünü
        # belirle (get_ticker_candidates'ın ilk/en olası adayı). GOLD-* dahili
        # sembollerin gerçek bir ticker'ı yok — id -> None ile işaretlenir,
        # bunun yerine GC=F'nin (varsa) toplu isteğe dahil edilmesi sağlanır.
        ticker_by_id = {}
        needs_gold_gram = False
        for asset in assets:
            code = (asset["asset_code"] or "").strip().upper()
            a_type = asset["asset_type"]
            if a_type == "Altın" and code in GOLD_TYPE_MULTIPLIERS:
                ticker_by_id[asset["id"]] = None
                needs_gold_gram = True
            else:
                candidates = get_ticker_candidates(asset["asset_code"], a_type)
                ticker_by_id[asset["id"]] = candidates[0] if candidates else None

        unique_tickers = {t for t in ticker_by_id.values() if t}
        if needs_gold_gram:
            unique_tickers.add("GC=F")

        def _last_close(close_obj, sym):
            """yf.download çıktısından sembolün son geçerli kapanışını çeker.

            yfinance 1.4.x TEK sembolde de MultiIndex sütun döndürüyor
            (('Close','THYAO.IS')), bu yüzden hist['Close'] bir Series değil
            DataFrame olabilir — eski kod float(Series) ile TypeError alıp
            fiyatı sessizce düşürüyordu (tüm portföyün ₺0,00 kalmasının kök
            nedeni). Hem düz hem MultiIndex biçimi güvenle ele alınır.
            """
            if close_obj is None:
                return None
            series = close_obj[sym] if hasattr(close_obj, "columns") else close_obj
            try:
                valid = series.dropna()
            except AttributeError:
                return None
            if len(valid) == 0:
                return None
            price = float(valid.iloc[-1])
            if math.isnan(price) or math.isinf(price):
                return None
            return price

        raw_prices = {}  # yfinance sembolü -> ham kapanış fiyatı (USD veya doğrudan ₺)
        if unique_tickers:
            try:
                if len(unique_tickers) == 1:
                    sym = next(iter(unique_tickers))
                    hist = yf.download(sym, period="5d", progress=False)
                    if not hist.empty:
                        price = _last_close(hist["Close"], sym)
                        if price is not None:
                            raw_prices[sym] = price
                else:
                    data = yf.download(
                        list(unique_tickers),
                        period="5d",
                        progress=False,
                        threads=True,
                    )
                    close_df = data["Close"]
                    for sym in unique_tickers:
                        price = _last_close(close_df, sym)
                        if price is not None:
                            raw_prices[sym] = price
            # BİLEREK GENİŞ (incelendi): tek blokta ÜÇ farklı üçüncü parti
            # yüzeyi var — yfinance (kendi `YFException` ailesi), altında
            # requests (OSError ailesi) ve pandas indeksleme (`data["Close"]`,
            # `_last_close`: KeyError/IndexError/TypeError, bozuk frame'de
            # AttributeError). Bu kümeyi eksik yazmak, şu an nazikçe bozulup
            # boş fiyatla devam eden yolu thread ölümüne çevirir; kütüphane
            # sürümü değiştiğinde de sessizce kırılır. Hata zaten loglanıyor
            # ve akış eksik fiyatlarla güvenle sürüyor.
            except Exception as e:
                _log().error("Portföy fiyat çekme hatası: %s", e, exc_info=True)

        # Gram altın (₺) fiyatı: toplu istekten geldiyse onu kullan (ve
        # önbelleğe yaz), gelmediyse tekil/önbellek yedeğine düş.
        gram_gold_try = None
        if "GC=F" in raw_prices:
            gram_gold_try = _normalize_to_try(raw_prices["GC=F"], "Altın")
            if gram_gold_try is not None:
                _gold_gram_cache["price"] = gram_gold_try
                _gold_gram_cache["time"] = time.time()
        elif needs_gold_gram:
            gram_gold_try = _fetch_gold_gram_price_try()

        enriched = []
        for asset in assets:
            code = (asset["asset_code"] or "").strip().upper()
            a_type = asset["asset_type"]
            current_price = None

            if a_type == "Altın" and code in GOLD_TYPE_MULTIPLIERS:
                if gram_gold_try is not None:
                    current_price = gram_gold_try * GOLD_TYPE_MULTIPLIERS[code]
            else:
                sym = ticker_by_id.get(asset["id"])
                raw = raw_prices.get(sym) if sym else None
                if raw is not None:
                    if a_type in ("Altın", "Kripto", "Crypto"):
                        current_price = _normalize_to_try(raw, "Altın" if a_type == "Altın" else "Kripto")
                    else:
                        current_price = raw

            entry = dict(asset)
            if current_price is not None:
                pnl = calculate_pnl(current_price, asset["purchase_price"], asset["quantity"])
                entry.update(pnl)
                entry["current_price"] = current_price
            else:
                entry["current_price"] = None
                entry["pnl_amount"]    = None
                entry["pnl_pct"]       = None
                entry["total_value"]   = None
                entry["total_cost"]    = None
                entry["signal"]        = "error"
            enriched.append(entry)
            if item_callback is not None:
                try:
                    item_callback(entry)
                except Exception as exc:
                    from utils.logging_config import get_logger
                    get_logger().exception("Portföy parça callback hatası")
        callback(enriched)

    def _worker():
        try:
            _worker_impl()
        except Exception as exc:
            # Import, bozuk satır veya beklenmeyen matematik hatası dahil her
            # durumda UI'ın loading durumunu kapatacak final callback gönderilir.
            _log().error(
                "Portföy fiyatlandırma tamamlanamadı: %s", exc, exc_info=True)
            fallback = _error_entries()
            if item_callback is not None:
                for entry in fallback:
                    try:
                        item_callback(entry)
                    except Exception:
                        # EXCEPTION-AUDIT: bilinçli geniş — garantili
                        # tamamlanma sınırı (hata dalının kendisi).
                        # BİLEREK geniş: burası zaten HATA dalı. Tek amacı
                        # aşağıdaki final `callback(fallback)`'e ulaşmak —
                        # tek bir satırın callback'i patlarsa arayüz sonsuza
                        # kadar spinner'da kalır. Daraltmanın kazancı burada
                        # zararına dönüşür.
                        pass
            try:
                callback(fallback)
            except Exception as callback_exc:
                from utils.logging_config import get_logger
                get_logger().exception("Portföy final callback hatası")

    threading.Thread(target=_worker, daemon=True).start()


# ─── Hesaplarım Bento özeti ──────────────────────────────────────────────────

# Bare kripto sembolü → CoinGecko coin id. Depoda kod çoğu zaman yfinance
# biçiminde ('BTC-USD') tutulduğu için eşleştirmeden ÖNCE alıntı eki
# (-USD/-USDT/-TRY …) soyulur; bkz. _coingecko_id_for.
COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "ETC": "ethereum-classic",
    "USDT": "tether", "USDC": "usd-coin", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "SOL": "solana", "DOGE": "dogecoin",
    "DOT": "polkadot", "TRX": "tron", "AVAX": "avalanche-2",
    "SHIB": "shiba-inu", "LTC": "litecoin", "LINK": "chainlink",
    "MATIC": "matic-network", "XLM": "stellar", "ATOM": "cosmos",
    "UNI": "uniswap", "XMR": "monero", "BCH": "bitcoin-cash",
    "FIL": "filecoin", "APT": "aptos", "ARB": "arbitrum", "OP": "optimism",
}
_PRICE_TIMEOUT = (3.05, 8.0)
_PRICE_CACHE_TABLE = "asset_price_cache"

# Kripto kodundan CoinGecko id çözerken soyulacak alıntı/karşı-para ekleri.
_CRYPTO_QUOTE_SUFFIXES = ("-USDTRY", "-USDT", "-USDC", "-BUSD", "-USD", "-TRY", "-EUR")


def _coingecko_id_for(asset_code) -> str | None:
    """'BTC-USD' → 'bitcoin'. Alıntı eki soyulup bare sembol map'te aranır.

    Kod zaten bare ('BTC') ise doğrudan eşleşir; kripto olmayan kodlar için
    None döner (çağıran yfinance/döviz yoluna düşer)."""
    base = (asset_code or "").strip().upper()
    if not base:
        return None
    for suffix in _CRYPTO_QUOTE_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return COINGECKO_IDS.get(base)


def _frankfurter_base_for(asset_code) -> str | None:
    """TL cinsinden değeri Frankfurter ile bulunabilecek dövizin 3 harfli
    kodunu döndürür: 'USDTRY=X' → 'USD', 'EUR' → 'EUR'. Aksi halde None.

    Yalnızca TRY karşılığı olan çiftler (…TRY=X) veya çıplak 3 harfli kodlar
    kabul edilir; 'GBPUSD=X' gibi TRY dışı çiftler yanlış fiyatlanmasın diye
    dışarıda bırakılır."""
    code = (asset_code or "").strip().upper()
    if len(code) == 3 and code.isalpha():
        return code
    if code.endswith("TRY=X"):
        base = code[: -len("TRY=X")]
        if len(base) == 3 and base.isalpha():
            return base
    return None


def _is_direct_try_asset(asset: dict) -> bool:
    """Doğrudan Türk lirası kaydını ayıklar; USDTRY gibi dövizleri korur."""
    code = str(asset.get("asset_code") or "").strip().upper()
    name = " ".join(str(asset.get("asset_name") or "").strip().casefold().split())
    return code in {"TL", "TRY", "TRY=X"} or name in {
        "tl", "try", "türk lirası", "turk lirasi",
    }


def get_active_non_try_assets() -> list:
    """SQLite'tan miktarı pozitif, doğrudan TL olmayan varlıkları getirir."""
    from database.db import SECRET_KEY, get_connection
    from utils.crypto import decrypt

    conn = get_connection()
    try:
        # Fonksiyonlu filtre normal asset_code indeksini kullanamaz. Aynı WHERE
        # ifadesine sahip partial index, TL dışı aktif portföy taramasını id
        # sırasından doğrudan karşılar.
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_assets_non_try
                ON active_assets(id DESC)
             WHERE UPPER(TRIM(asset_code)) NOT IN ('TRY', 'TL', 'TRY=X')
        """)
        conn.commit()
        rows = conn.execute("""
            SELECT id, asset_name, asset_code, asset_type, purchase_price, quantity
              FROM active_assets
             WHERE UPPER(TRIM(asset_code)) NOT IN ('TRY', 'TL', 'TRY=X')
             ORDER BY id DESC
        """).fetchall()
    finally:
        conn.close()
    assets = []
    for row in rows:
        try:
            quantity = float(decrypt(row["quantity"], SECRET_KEY))
            purchase_price = float(decrypt(row["purchase_price"], SECRET_KEY))
        except KeyUnavailableError:
            # Anahtar yoksa TÜM varlıklar etkilenir; satır bazında yutmak
            # toplam arızayı boş portföy gibi gösterirdi.
            raise
        except (DecryptionError, ValueError, TypeError) as e:
            _log().error(
                "[VERİ BÜTÜNLÜĞÜ] active_assets id=%s çözülemedi: %s",
                row["id"], e)
            continue
        if quantity > 0:
            assets.append({
                "id": row["id"], "asset_name": row["asset_name"],
                "asset_code": row["asset_code"], "asset_type": row["asset_type"],
                "purchase_price": purchase_price, "quantity": quantity,
            })
    return assets


def _ensure_price_cache(conn) -> None:
    from database.models import ASSET_PRICE_CACHE_SCHEMA
    conn.execute(ASSET_PRICE_CACHE_SCHEMA)
    conn.commit()


def _read_cached_prices(symbols: set[str]) -> dict[str, float]:
    if not symbols:
        return {}
    from database.db import get_connection
    conn = get_connection()
    try:
        _ensure_price_cache(conn)
        placeholders = ",".join("?" for _ in symbols)
        rows = conn.execute(
            f"SELECT symbol, price FROM {_PRICE_CACHE_TABLE} WHERE symbol IN ({placeholders})",
            tuple(symbols),
        ).fetchall()
        return {row["symbol"]: float(row["price"]) for row in rows}
    finally:
        conn.close()


def _store_prices(prices: dict[str, float]) -> None:
    if not prices:
        return
    from database.db import get_connection
    conn = get_connection()
    try:
        _ensure_price_cache(conn)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Istanbul")).isoformat()
        conn.executemany(
            f"""INSERT INTO {_PRICE_CACHE_TABLE}
                    (symbol, price, asset_type, updated_at)
                VALUES (?, ?, 'UNKNOWN', ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    price=excluded.price, updated_at=excluded.updated_at""",
            [(symbol, price, now) for symbol, price in prices.items()],
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_live_try_prices(assets: list[dict]) -> dict[str, float]:
    """CoinGecko (kripto) ve Frankfurter (döviz) üzerinden TL fiyatlarını getirir.

    Dönen sözlük, varlığın DEPODAKİ tam kodu (örn. 'BTC-USD', 'USDTRY=X') ile
    anahtarlanır; böylece çağıran `fetch_active_non_try_total` her varlığı kendi
    koduyla eşleştirip miktarla çarpabilir. Her iki servis de API anahtarı
    gerektirmez. İkisi de erişilemez ve hiç fiyat toplanamazsa RuntimeError
    fırlatılır (çağıran önbelleğe/yfinance yedeğine düşer)."""
    import requests
    prices: dict[str, float] = {}
    errors = []

    # ── Kripto: tam kod → CoinGecko coin id (alıntı eki soyularak) ──
    crypto_ids = {}
    for asset in assets:
        code = (asset.get("asset_code") or "").strip().upper()
        coin_id = _coingecko_id_for(code)
        if coin_id:
            crypto_ids[code] = coin_id
    if crypto_ids:
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(sorted(set(crypto_ids.values()))), "vs_currencies": "try"},
                timeout=_PRICE_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            for full_code, coin_id in crypto_ids.items():
                value = payload.get(coin_id, {}).get("try")
                if value is not None and float(value) > 0:
                    prices[full_code] = float(value)
        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(exc)

    # ── Döviz: tam kod → 3 harfli baz (USDTRY=X → USD). Frankfurter TRY→baz
    #    kurunu verir; 1 birim dövizin TL değeri = 1 / (TRY başına baz). ──
    fiat_bases = {}
    for asset in assets:
        if asset.get("asset_type") not in ("Döviz", "Forex"):
            continue
        code = (asset.get("asset_code") or "").strip().upper()
        base = _frankfurter_base_for(code)
        if base and base != "TRY":
            fiat_bases[code] = base
    if fiat_bases:
        try:
            response = requests.get(
                "https://api.frankfurter.app/latest",
                params={"from": "TRY", "to": ",".join(sorted(set(fiat_bases.values())))},
                timeout=_PRICE_TIMEOUT,
            )
            response.raise_for_status()
            rates = response.json().get("rates", {})
            for full_code, base in fiat_bases.items():
                rate = rates.get(base)
                if rate is not None and float(rate) > 0:
                    prices[full_code] = 1.0 / float(rate)
        except (requests.RequestException, ValueError, TypeError) as exc:
            errors.append(exc)

    if errors and not prices:
        raise RuntimeError("Canlı fiyat servislerine ulaşılamadı") from errors[0]
    return prices


def fetch_active_non_try_total(callback, progress_callback=None) -> None:
    """TL dışı portföy toplamını dinamik TTL cache'iyle arka planda hesaplar.

    Bu özet yolu ağ sonucu beklemez: son fiyatları anında toplar, eksik/bayat
    sembollerin yenilenmesini price_service daemon thread'lerine bırakır.
    """
    def _load_assets():
        try:
            assets = get_active_non_try_assets()
        except (sqlite3.Error, OSError, ArchlenceError) as exc:
            # `get_active_non_try_assets` yalnızca DB okur ve çözer: sorgu
            # hataları sqlite3.Error, veri dizini erişimi OSError, anahtar/
            # şifre çözme sorunları ArchlenceError türevi (KeyUnavailableError,
            # DecryptionError) — bunlar satır içindeki (ValueError, TypeError)
            # korumasına TAKILMAZ, buraya kadar gelir.
            _log().exception("TL dışı varlık listesi okunamadı")
            callback({"total": 0.0, "asset_count": 0, "priced_count": 0,
                      "cached_count": 0, "complete": True, "error": str(exc)})
            return

        if not assets:
            callback({"total": 0.0, "asset_count": 0, "priced_count": 0,
                      "cached_count": 0, "complete": True})
            return

        # UI hiçbir ağ isteğini beklemeden 0 TL şablonunu gösterebilir.
        if progress_callback is not None:
            progress_callback({
                "total": 0.0, "asset_count": len(assets), "priced_count": 0,
                "cached_count": 0, "complete": False,
            })

        from services.price_service import (
            fetch_prices_async, get_cached_prices,
        )

        requested = [
            (
                (asset["asset_code"] or "").strip().upper(),
                asset.get("asset_type"),
            )
            for asset in assets
        ]
        prices = get_cached_prices(symbol for symbol, _kind in requested)
        # Tek çağrı bütün vadesi dolmuş sembolleri bir batch worker'a toplar.
        fetch_prices_async(requested, callback=None)
        total = 0.0
        priced_count = 0
        for asset in assets:
            symbol = (asset["asset_code"] or "").strip().upper()
            price = prices.get(symbol)
            if price is None:
                continue
            priced_count += 1
            total += float(asset["quantity"]) * float(price)
            if progress_callback is not None:
                progress_callback({
                    "total": total, "asset_count": len(assets),
                    "priced_count": priced_count,
                    "cached_count": priced_count, "complete": False,
                    "asset": asset,
                })
        callback({
            "total": total, "asset_count": len(assets),
            "priced_count": priced_count, "cached_count": priced_count,
            "complete": True,
        })

    threading.Thread(target=_load_assets, daemon=True).start()
