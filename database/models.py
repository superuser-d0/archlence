"""Veritabanı şema modelleri.

Proje ORM kullanmadığı için modeller, SQLite tablo sözleşmesini taşıyan hafif
dataclass'lar olarak tutulur. Gerçek tablo kurulumu/migration'ı init_db'dedir.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AssetPriceCache:
    """Bir API sembolünün son bilinen, TL'ye normalize edilmiş fiyatı."""

    symbol: str
    price: float
    asset_type: str
    updated_at: datetime


ASSET_PRICE_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_price_cache (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    asset_type TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""
