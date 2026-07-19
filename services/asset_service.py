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

import threading
import time

GRAMS_PER_TROY_OUNCE = 31.1034768

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

_gold_gram_cache = {"price": None, "time": 0.0}
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
        pass
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
        except Exception:
            pass

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
                except Exception:
                    pass
        except Exception as e:
            print("BIST100 fiyat çekme hatası:", e)
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


# ─── Tüm portföy için toplu fiyat çekme (threading destekli) ─────────────────

def fetch_portfolio_with_prices(assets: list, callback) -> None:
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
    def _worker():
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

        raw_prices = {}  # yfinance sembolü -> ham kapanış fiyatı (USD veya doğrudan ₺)
        if unique_tickers:
            try:
                if len(unique_tickers) == 1:
                    # Tek sembolde yf.download düz (MultiIndex olmayan) bir
                    # DataFrame döner; çoklu-sembol dalındaki data["Close"][sym]
                    # erişimi bu durumda çalışmaz, ayrı ele alınması gerekir.
                    sym = next(iter(unique_tickers))
                    hist = yf.download(sym, period="5d", progress=False)
                    if not hist.empty:
                        price = float(hist["Close"].dropna().iloc[-1])
                        if not math.isnan(price) and not math.isinf(price):
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
                        try:
                            price = float(close_df[sym].dropna().iloc[-1])
                            if not math.isnan(price) and not math.isinf(price):
                                raw_prices[sym] = price
                        except Exception:
                            pass
            except Exception as e:
                print("Portföy fiyat çekme hatası:", e)

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
        callback(enriched)

    threading.Thread(target=_worker, daemon=True).start()
