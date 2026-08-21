"""Veritabanı şema modelleri.

Proje ORM kullanmadığı için modeller, SQLite tablo sözleşmesini taşıyan hafif
dataclass'lar olarak tutulur. Gerçek tablo kurulumu/migration'ı init_db'dedir.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


@dataclass(frozen=True)
class AssetPriceCache:
    """Bir API sembolünün son bilinen, TL'ye normalize edilmiş fiyatı."""

    symbol: str
    price: float
    asset_type: str
    updated_at: datetime


    source: str = "Yahoo Finance"


class PriceFreshness(str, Enum):
    CURRENT = "current"
    DELAYED = "delayed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AssetPriceStatus:
    symbol: str
    price: Decimal | None
    source: str
    updated_at: datetime | None
    cache_age_seconds: int | None
    freshness: PriceFreshness


ASSET_PRICE_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_price_cache (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    asset_type TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- NULL olabilir: sütun eklenmeden önceki satırlar. Okuma tarafı bunu
    -- "Yahoo Finance"a çözer (o dönemde tek sağlayıcı oydu).
    source TEXT
)
"""
