"""Uygulama sembollerini Yahoo Finance batch sembollerine dönüştürür."""


_GOLD_INTERNAL = {
    "ALTIN": "GC=F",
    "GOLD": "GC=F",
    "GRAM": "GC=F",
    "XAU": "GC=F",
    "GOLD-ONS": "GC=F",
    "GOLD-CEYREK": "GC=F",
    "GOLD-YARIM": "GC=F",
    "GOLD-TAM": "GC=F",
}


def normalize_asset_type(asset_type: str | None) -> str:
    value = (asset_type or "").strip().upper()
    if value in {"CRYPTO", "KRIPTO", "KRİPTO"}:
        return "CRYPTO"
    if value in {"STOCK", "HISSE", "HİSSE"}:
        return "STOCK"
    if value in {"FX_GOLD", "DÖVIZ", "DÖVİZ", "FOREX", "ALTIN", "GOLD"}:
        return "FX_GOLD"
    return value or "FX_GOLD"


def to_api_ticker(symbol: str, asset_type: str | None = None) -> str:
    """Örn. ASELS→ASELS.IS, USD→USDTRY=X, BTC→BTC-USD."""

    code = (symbol or "").strip().upper()
    kind = normalize_asset_type(asset_type)
    if not code:
        return ""
    if kind == "STOCK":
        return code if "." in code else f"{code}.IS"
    if kind == "CRYPTO":
        return code if "-" in code else f"{code}-USD"
    if code in _GOLD_INTERNAL:
        return _GOLD_INTERNAL[code]
    if len(code) == 3 and code.isalpha() and code != "TRY":
        return f"{code}TRY=X"
    return code


def gold_multiplier(symbol: str) -> float | None:
    """Dahili fiziksel altın sembolünün gram-altın çarpanı."""

    return {
        "GOLD-ONS": 31.1034768,
        "GOLD-CEYREK": 1.75,
        "GOLD-YARIM": 3.5,
        "GOLD-TAM": 7.0,
    }.get((symbol or "").strip().upper())
