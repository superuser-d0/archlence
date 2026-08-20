"""yfinance kesildiğinde devreye giren yedek fiyat sağlayıcıları.

NEDEN: `price_service._download_batch` tek sağlayıcıya (yfinance) bağlıydı.
O çağrı boş dönerse tüm portföy sessizce bayat cache'e düşüyordu ve kullanıcı
bunu ancak fiyatların güncellenmediğini fark ederek anlıyordu.

TASARIM — bu modül BİLEREK yfinance'in birim uzayında konuşur:
`_download_batch`'in dönüşünü aynı sözleşmeyle doldurur, böylece
`fetch_prices_async` içindeki TL'ye çevirme matematiğinin (USDTRY çarpımı,
ons→gram bölmesi, altın çarpanı) hiçbir dalı değişmez. Yani bir sembol
CoinGecko'dan gelse de yfinance'ten gelse de aşağı akış aynı sayıyı görür.

KAPSAM — dürüst sınırlar:
  * `XXX-USD`  (kripto)  -> CoinGecko, USD cinsinden  ✓
  * `XXXTRY=X` (döviz)   -> Frankfurter, TL/birim     ✓
  * `GC=F`     (altın)   -> yedek YOK
  * `XXXX.IS`  (BIST)    -> yedek YOK
Son ikisi için ücretsiz ve halihazırda depoda kanıtlanmış bir kaynak yok;
uydurma bir sağlayıcı eklemektense kapsam dışı bırakıldılar. `USDTRY=X`'in
yedeklenmesi yine de altını DOLAYLI olarak kurtarır: altın fiyatı
`GC=F * USDTRY` ile TL'ye çevrildiğinden, USDTRY yfinance'te düşüp burada
kurtarıldığında ons fiyatı cache'ten gelse bile çevrim tamamlanabilir.

Sağlayıcıların ikisi de `services/asset_service.py::_fetch_live_try_prices`
içinde zaten kullanılıyordu; buradaki fark, sonucun TL değil yfinance
biriminde döndürülmesi.
"""

import re

from services.price_guard import finite_positive_price
from utils.logging_config import get_logger

# `asset_service._PRICE_TIMEOUT` ile aynı bütçe; yedek yol birincil yoldan
# daha uzun beklememeli, aksi halde "yavaş ama çalışıyor" hissi kaybolur.
_TIMEOUT = 8

SOURCE_YAHOO = "Yahoo Finance"
SOURCE_COINGECKO = "CoinGecko"
SOURCE_FRANKFURTER = "Frankfurter (ECB)"

_FIAT_TICKER = re.compile(r"^([A-Z]{3})TRY=X$")
_CRYPTO_TICKER = re.compile(r"^([A-Z0-9]{2,10})-(USD|USDT)$")

# CoinGecko sembol->id eşlemesi. asset_service._COINGECKO_IDS ile aynı kaynağı
# kullanır; burada yeniden tanımlamak yerine oradan okunur (tek doğruluk
# kaynağı — yeni bir coin eklenince iki yerde güncelleme gerekmesin).


def _coingecko_ids_for(symbols):
    from services.asset_service import _coingecko_id_for

    out = {}
    for symbol in symbols:
        coin_id = _coingecko_id_for(symbol)
        if coin_id:
            out[symbol] = coin_id
    return out


def _fetch_crypto_usd(tickers):
    """`BTC-USD` gibi tickerlar için CoinGecko'dan USD fiyatı."""
    import requests

    wanted = {}
    for ticker in tickers:
        match = _CRYPTO_TICKER.match(ticker)
        if match:
            wanted[ticker] = ticker
    if not wanted:
        return {}

    ids = _coingecko_ids_for(wanted.values())
    if not ids:
        return {}

    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": ",".join(sorted(set(ids.values()))),
            # USD — yfinance de `BTC-USD` için USD döner. TL'ye çevirme
            # aşağı akışta USDTRY ile yapılıyor, burada YAPILMAMALI.
            "vs_currencies": "usd",
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    out = {}
    for ticker, symbol in wanted.items():
        coin_id = ids.get(symbol)
        if not coin_id:
            continue
        # `float(value) > 0` YETMEZ: `float("inf") > 0` True'dur ve
        # `json.loads` `Infinity`/`NaN` sabitlerini varsayılan olarak
        # ayrıştırır (bkz. services/price_guard.py).
        price = finite_positive_price(payload.get(coin_id, {}).get("usd"))
        if price is not None:
            out[ticker] = price
    return out


def _fetch_fiat_try(tickers):
    """`USDTRY=X` gibi tickerlar için Frankfurter'dan 1 birimin TL değeri."""
    import requests

    bases = {}
    for ticker in tickers:
        match = _FIAT_TICKER.match(ticker)
        if match and match.group(1) != "TRY":
            bases[ticker] = match.group(1)
    if not bases:
        return {}

    # `from=TRY&to=USD,EUR` -> 1 TL kaç USD/EUR eder. Bir birim dövizin TL
    # karşılığı bunun TERSİ. (asset_service'teki aynı çevrimle birebir.)
    response = requests.get(
        "https://api.frankfurter.app/latest",
        params={"from": "TRY", "to": ",".join(sorted(set(bases.values())))},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    rates = response.json().get("rates", {})

    out = {}
    for ticker, base in bases.items():
        # Kur ÖNCE sınanır, sonra tersi alınır: sonsuz bir kurun tersi 0,
        # sıfır bir kurun tersi ZeroDivisionError olurdu.
        rate = finite_positive_price(rates.get(base))
        if rate is not None:
            inverted = finite_positive_price(1.0 / rate)
            if inverted is not None:
                out[ticker] = inverted
    return out


def fetch_fallback_prices(tickers):
    """Verilen yfinance tickerları için yedek sağlayıcılardan fiyat toplar.

    Dönüş: `{ticker: (price, source)}` — yalnızca GERÇEKTEN bulunanlar.
    Kapsanmayan ticker'lar (BIST, `GC=F`) sessizce atlanır; bu bir hata
    değil, belgelenmiş bir sınır.

    Bir sağlayıcının patlaması diğerini engellemez: her biri kendi bloğunda
    yakalanır, kısmi sonuç tam sonuçsuzluktan iyidir.
    """
    if not tickers:
        return {}

    import requests

    logger = get_logger()
    results = {}
    for label, source, fetch in (
        ("CoinGecko", SOURCE_COINGECKO, _fetch_crypto_usd),
        ("Frankfurter", SOURCE_FRANKFURTER, _fetch_fiat_try),
    ):
        try:
            for ticker, price in fetch(tickers).items():
                results[ticker] = (price, source)
        except (requests.RequestException, ValueError, TypeError,
                KeyError) as exc:
            # Ölçülen yüzey: ağ/HTTP hataları RequestException; bozuk JSON
            # ValueError; beklenmeyen gövde şekli TypeError/KeyError.
            logger.warning(
                "Yedek fiyat sağlayıcısı %s başarısız: %r", label, exc)
    return results
