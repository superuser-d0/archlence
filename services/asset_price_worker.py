"""Isolated portfolio price worker.

Runs yfinance/pandas outside the Kivy process so their imports and dataframe
work cannot hold the UI process GIL. Communication is JSON-only.
"""
import json
import os
import sys
import threading
from typing import Any

# Proje kökünü sys.path'e ekle: bu modül `-m services.asset_price_worker` ile
# ayrı bir süreç olarak çalışıyor ve `from services...` importları proje
# kökünün path'te olmasını gerektiriyor. Çağıran cwd=proje_kökü veriyor
# (services/asset_service.py) ama paketlenmiş çalıştırmada cwd farklı olabilir;
# tests/*.py'deki aynı guard deseniyle bunu garantiye alıyoruz.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    output_path = sys.argv[1]
    assets = json.loads(sys.stdin.read() or "[]")
    os.environ["ARCHLENCE_ASSET_PRICE_CHILD"] = "1"

    result: list[dict[str, Any]] = []
    done = threading.Event()

    def complete(enriched):
        nonlocal result
        result = enriched or []
        done.set()

    from services.asset_service import fetch_portfolio_with_prices
    fetch_portfolio_with_prices(assets, callback=complete)
    done.wait(60)
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False)


if __name__ == "__main__":
    main()
