"""Isolated portfolio price worker.

Runs yfinance/pandas outside the Kivy process so their imports and dataframe
work cannot hold the UI process GIL. Communication is JSON-only.
"""
import json
import os
import sys
import threading


def main():
    output_path = sys.argv[1]
    assets = json.loads(sys.stdin.read() or "[]")
    os.environ["ARCHLENCE_ASSET_PRICE_CHILD"] = "1"

    result = []
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
