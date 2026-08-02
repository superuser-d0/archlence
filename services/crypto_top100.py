import threading
import time
import requests

from typing import Any

# 5 minutes cache to avoid rate limiting
_CACHE_TTL = 300
_crypto_cache: dict[str, Any] = {
    "data": None,
    "timestamp": 0
}

def fetch_top_100_cryptos(callback):
    """
    Arka planda CoinGecko API'sinden piyasa değerine göre ilk 100 kripto parayı çeker.
    Eğer önbellekte geçerli veri varsa onu döner.
    callback(list_of_cryptos) şeklinde çağrılır.
    Her bir eleman: {"symbol": "BTC", "name": "Bitcoin", "price": 60000.0, "image": "..."}
    """
    def _worker():
        now = time.time()
        if _crypto_cache["data"] and (now - _crypto_cache["timestamp"]) < _CACHE_TTL:
            callback(_crypto_cache["data"])
            return

        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false"
        }
        
        try:
            # User-Agent is added to prevent simple blocks from Cloudflare
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            cryptos = []
            for item in data:
                cryptos.append({
                    "symbol": item.get("symbol", "").upper(),
                    "name": item.get("name", ""),
                    "price": item.get("current_price", 0.0),
                    "image": item.get("image", "")
                })
                
            _crypto_cache["data"] = cryptos
            _crypto_cache["timestamp"] = now
            callback(cryptos)
        except Exception as e:
            from utils.logging_config import get_logger
            get_logger().exception("CoinGecko API çekme hatası")
            callback([])

    threading.Thread(target=_worker, daemon=True).start()
