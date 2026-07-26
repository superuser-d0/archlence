"""Cache-first, dinamik TTL'li ve tamamen non-blocking fiyat servisi."""

from __future__ import annotations

from datetime import datetime, time as clock_time
import logging
import math
import threading
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from database.models import ASSET_PRICE_CACHE_SCHEMA, AssetPriceCache
from utils.ticker_mapper import (
    gold_multiplier,
    normalize_asset_type,
    to_api_ticker,
)


logger = logging.getLogger(__name__)
ISTANBUL = ZoneInfo("Europe/Istanbul")
MARKET_OPEN = clock_time(9, 55)
MARKET_CLOSE = clock_time(18, 10)
INFINITE_TTL = math.inf
GRAMS_PER_TROY_OUNCE = 31.1034768

_inflight: set[str] = set()
_inflight_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(ISTANBUL)


def get_ttl_minutes(
    asset_type: str, symbol: str = "", now: datetime | None = None
) -> float:
    """Varlık türü ve İstanbul piyasa saatine göre cache ömrü."""

    del symbol  # Gelecekte sembol-bazlı seans takvimleri için API'yi sabit tutar.
    kind = normalize_asset_type(asset_type)
    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=ISTANBUL)
    else:
        current = current.astimezone(ISTANBUL)

    if kind == "CRYPTO":
        return 3
    if kind == "STOCK":
        if current.weekday() < 5 and MARKET_OPEN <= current.time() <= MARKET_CLOSE:
            return 5
        return INFINITE_TTL
    if kind == "FX_GOLD":
        return 10 if current.weekday() < 5 else INFINITE_TTL
    return 10


def _parse_updated_at(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, ISTANBUL)
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ISTANBUL)
    return parsed.astimezone(ISTANBUL)


def _ensure_cache(conn) -> None:
    conn.execute(ASSET_PRICE_CACHE_SCHEMA)


def _read_cache(symbols: Iterable[str]) -> dict[str, AssetPriceCache]:
    keys = {str(symbol).strip().upper() for symbol in symbols if symbol}
    if not keys:
        return {}
    from database.db import get_connection

    conn = get_connection()
    try:
        _ensure_cache(conn)
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            "SELECT symbol, price, asset_type, updated_at "
            f"FROM asset_price_cache WHERE symbol IN ({placeholders})",
            tuple(keys),
        ).fetchall()
        return {
            row["symbol"]: AssetPriceCache(
                symbol=row["symbol"],
                price=float(row["price"]),
                asset_type=row["asset_type"],
                updated_at=_parse_updated_at(row["updated_at"]),
            )
            for row in rows
        }
    finally:
        conn.close()


def _store_cache(
    prices: dict[str, float], asset_types: dict[str, str],
    updated_at: datetime | None = None,
) -> None:
    if not prices:
        return
    from database.db import get_connection

    stamp = (updated_at or _now()).astimezone(ISTANBUL).isoformat()
    conn = get_connection()
    try:
        _ensure_cache(conn)
        conn.executemany(
            """INSERT INTO asset_price_cache
                   (symbol, price, asset_type, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(symbol) DO UPDATE SET
                   price=excluded.price,
                   asset_type=excluded.asset_type,
                   updated_at=excluded.updated_at""",
            [
                (
                    symbol, float(price),
                    normalize_asset_type(asset_types.get(symbol)), stamp,
                )
                for symbol, price in prices.items()
                if price is not None and float(price) > 0
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_price(symbol: str) -> float | None:
    row = _read_cache({symbol}).get((symbol or "").strip().upper())
    return row.price if row else None


def get_cached_prices(symbols: Iterable[str]) -> dict[str, float]:
    """Birden çok sembolü tek SQLite sorgusunda döndürür."""

    return {
        symbol: row.price for symbol, row in _read_cache(symbols).items()
    }


def get_price(
    symbol: str, asset_type: str = "FX_GOLD", force_refresh: bool = False
) -> float | None:
    """Cache değerini anında döndürür; gerekiyorsa yenilemeyi arkada başlatır."""

    key = (symbol or "").strip().upper()
    cached = _read_cache({key}).get(key)
    ttl = get_ttl_minutes(asset_type, key)
    stale = cached is None
    if cached is not None and ttl != INFINITE_TTL:
        stale = (_now() - cached.updated_at).total_seconds() >= ttl * 60

    # Sonsuz TTL piyasa kapalı anlamına gelir; force bile kapalı piyasaya istek
    # attırmaz. Son bilinen değer (varsa) aynen kullanılır.
    if ttl != INFINITE_TTL and (force_refresh or stale):
        fetch_prices_async(
            [(key, asset_type)], callback=None, force_refresh=force_refresh
        )
    return cached.price if cached else None


def _extract_last_close(data, ticker: str, single: bool) -> float | None:
    try:
        close = data["Close"]
        # yfinance 1.4.x TEK sembolde de MultiIndex sütun döndürüyor, yani
        # data["Close"] bir Series değil DataFrame olabilir. `single` olsa bile
        # sütunlu ise ticker'ı (yoksa ilk sütunu) seç; float(DataFrame) aksi
        # halde TypeError verip fiyatı sessizce düşürüyordu (tek varlıklı
        # portföyde "Aktif Varlıklarım ₺0,00" kalmasının kök nedeni).
        if hasattr(close, "columns"):
            series = close[ticker] if ticker in close.columns else close.iloc[:, 0]
        else:
            series = close
        value = float(series.dropna().iloc[-1])
        return value if math.isfinite(value) and value > 0 else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _download_batch(tickers: list[str]) -> dict[str, float]:
    """Tek yf.download çağrısında ham fiyatları döndürür."""

    if not tickers:
        return {}
    import yfinance as yf

    try:
        data = yf.download(
            tickers[0] if len(tickers) == 1 else tickers,
            period="5d", progress=False, threads=True, timeout=10,
        )
        return {
            ticker: price
            for ticker in tickers
            if (price := _extract_last_close(data, ticker, len(tickers) == 1))
            is not None
        }
    except Exception as e:
        logger.error(f"Fiyat çekme hatası (timeout/ağ): {e}")
        return {}


def _schedule_callback(callback, prices) -> None:
    if callback is None:
        return
    try:
        from kivy.clock import Clock
        Clock.schedule_once(lambda _dt: callback(prices), 0)
    except Exception:
        # Kivy başlatılmamış unit-test/CLI ortamında sonucu yine teslim et.
        callback(prices)


def _normalize_requests(symbols_list) -> dict[str, str]:
    requests = {}
    for item in symbols_list or []:
        if isinstance(item, dict):
            symbol = item.get("symbol") or item.get("asset_code")
            asset_type = item.get("asset_type")
        elif isinstance(item, (tuple, list)):
            symbol, asset_type = item[0], item[1]
        else:
            symbol, asset_type = item, "FX_GOLD"
        key = str(symbol or "").strip().upper()
        if key:
            requests[key] = normalize_asset_type(asset_type)
    return requests


def fetch_prices_async(
    symbols_list, callback: Callable[[dict[str, float]], None] | None,
    force_refresh: bool = False,
) -> threading.Thread | None:
    """Uygun sembolleri tek batch çağrıda yeniler ve sonucu UI thread'ine yollar."""

    requested = _normalize_requests(symbols_list)
    cached = _read_cache(requested)
    now = _now()
    due = {}
    for symbol, asset_type in requested.items():
        row = cached.get(symbol)
        ttl = get_ttl_minutes(asset_type, symbol, now=now)
        if ttl == INFINITE_TTL:
            # Sonsuz TTL "piyasa kapalı" demek — normalde gereksiz isteği
            # önlemek için atlanır. AMA hiç cache'i olmayan (row is None) bir
            # varlık için bu atlama, kullanıcıyı "Canlı veri bekleniyor…"
            # durumunda SONSUZA KADAR bırakırdı (hafta sonu eklenen bir
            # hisse/altın/döviz asla ilk fiyatını alamaz, oysa kripto TTL'i
            # hep sonlu olduğundan bu sorunu hiç yaşamaz). Piyasa kapalıyken
            # bile son kapanış fiyatı, hiç fiyat olmamasından iyidir — bu
            # yüzden İLK çekim için istisna tanınır.
            if row is None:
                due[symbol] = asset_type
            continue
        expired = (
            row is None
            or (now - row.updated_at).total_seconds() >= ttl * 60
        )
        if force_refresh or expired:
            due[symbol] = asset_type

    if not due:
        _schedule_callback(
            callback, {symbol: row.price for symbol, row in cached.items()}
        )
        return None

    with _inflight_lock:
        new_due = {
            symbol: kind for symbol, kind in due.items()
            if symbol not in _inflight
        }
        _inflight.update(new_due)
    if not new_due:
        _schedule_callback(
            callback, {symbol: row.price for symbol, row in cached.items()}
        )
        return None

    def worker():
        final = {symbol: row.price for symbol, row in cached.items()}
        try:
            ticker_by_symbol = {
                symbol: to_api_ticker(symbol, kind)
                for symbol, kind in new_due.items()
            }
            tickers = set(ticker_by_symbol.values())
            needs_usdtry = any(
                kind == "CRYPTO"
                or (kind == "FX_GOLD" and ticker_by_symbol[symbol] == "GC=F")
                for symbol, kind in new_due.items()
            )
            if needs_usdtry:
                tickers.add("USDTRY=X")
            raw = _download_batch(sorted(tickers))
            usdtry = raw.get("USDTRY=X")
            live = {}
            for symbol, kind in new_due.items():
                ticker = ticker_by_symbol[symbol]
                value = raw.get(ticker)
                if value is None:
                    continue
                if kind == "CRYPTO":
                    value = value * usdtry if usdtry else None
                elif kind == "FX_GOLD" and ticker == "GC=F":
                    value = (
                        value * usdtry / GRAMS_PER_TROY_OUNCE
                        if usdtry else None
                    )
                    multiplier = gold_multiplier(symbol)
                    if value is not None and multiplier is not None:
                        value *= multiplier
                if value is not None and math.isfinite(value) and value > 0:
                    live[symbol] = float(value)
            _store_cache(live, new_due, updated_at=now)
            final.update(live)
        except Exception as exc:
            message = str(exc)
            if "429" in message or "rate" in message.casefold():
                logger.warning("Fiyat servisi rate limit'e takıldı: %s", exc)
            else:
                logger.warning("Fiyatlar güncellenemedi; cache kullanılacak: %s", exc)
        finally:
            with _inflight_lock:
                _inflight.difference_update(new_due)
            _schedule_callback(callback, final)

    thread = threading.Thread(
        target=worker, name="asset-price-batch", daemon=True
    )
    thread.start()
    return thread


def enrich_assets_from_cache(assets: list[dict]) -> list[dict]:
    """Portföy satırlarını yalnızca yerel cache ile, ağ beklemeden zenginleştirir."""

    from services.asset_service import calculate_pnl

    symbols = {
        (asset.get("asset_code") or "").strip().upper() for asset in assets
    }
    cached = _read_cache(symbols)
    enriched = []
    for asset in assets:
        entry = dict(asset)
        symbol = (asset.get("asset_code") or "").strip().upper()
        row = cached.get(symbol)
        if row:
            entry.update(calculate_pnl(
                row.price, float(asset["purchase_price"]),
                float(asset["quantity"]),
            ))
            entry["current_price"] = row.price
            entry["price_updated_at"] = row.updated_at
        else:
            entry.update({
                "current_price": None, "pnl_amount": None, "pnl_pct": None,
                "total_value": None, "total_cost": None, "signal": "pending",
            })
        enriched.append(entry)
    return enriched


def fetch_asset_prices_async(
    assets: list[dict], callback, force_refresh: bool = False
):
    """Asset dict listesini batch yenileyip zenginleştirilmiş portföy döndürür."""

    requests = [
        (asset.get("asset_code"), asset.get("asset_type")) for asset in assets
    ]

    def complete(_prices):
        callback(enrich_assets_from_cache(assets))

    return fetch_prices_async(
        requests, complete, force_refresh=force_refresh
    )


def get_last_updated_at(symbols: Iterable[str] | None = None) -> datetime | None:
    from database.db import get_connection

    conn = get_connection()
    try:
        _ensure_cache(conn)
        if symbols:
            keys = {(symbol or "").strip().upper() for symbol in symbols}
            placeholders = ",".join("?" for _ in keys)
            row = conn.execute(
                "SELECT MAX(updated_at) AS updated_at FROM asset_price_cache "
                f"WHERE symbol IN ({placeholders})", tuple(keys),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT MAX(updated_at) AS updated_at FROM asset_price_cache"
            ).fetchone()
        return (
            _parse_updated_at(row["updated_at"])
            if row and row["updated_at"] else None
        )
    finally:
        conn.close()
