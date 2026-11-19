"""Download the main NIULAI pool snapshot and hourly OHLCV from GeckoTerminal."""

from __future__ import annotations

import json
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "0xbeea1d618e533a387d941f58a7d4c9b7bd377777"
POOL = "0xe5ae318389b8d6d09370a675479c64862152d126"
POOLS_URL = f"https://api.geckoterminal.com/api/v2/networks/bsc/tokens/{TOKEN}/pools"
OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/bsc/pools/"
    f"{POOL}/ohlcv/hour?aggregate=1&limit=168&currency=usd&token=base"
)
DAILY_URL = (
    "https://api.geckoterminal.com/api/v2/networks/bsc/pools/"
    f"{POOL}/ohlcv/day?aggregate=1&limit=100&currency=usd&token=base"
)
RAW = ROOT / "data/raw/market"
OUTPUT = ROOT / "data/processed/niulai_hourly_ohlcv.csv"
DAILY_OUTPUT = ROOT / "data/processed/niulai_daily_ohlcv_full.csv"
SNAPSHOT = ROOT / "data/processed/niulai_market_snapshot.json"


def fetch(url: str) -> dict:
    context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    request = Request(url, headers={"User-Agent": "Meme-Signal-Lab/1.0"})
    with urlopen(request, timeout=30, context=context) as response:
        return json.load(response)


def main() -> None:
    pools = fetch(POOLS_URL)
    ohlcv = fetch(OHLCV_URL)
    daily = fetch(DAILY_URL)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "niulai_pools.json").write_text(
        json.dumps(pools, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RAW / "niulai_hourly_ohlcv.json").write_text(
        json.dumps(ohlcv, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RAW / "niulai_daily_ohlcv_full.json").write_text(
        json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pool = next(item for item in pools["data"] if item["attributes"]["address"].lower() == POOL)
    attrs = pool["attributes"]
    snapshot = {
        "contract_address": TOKEN,
        "network": "bsc",
        "pool_address": POOL,
        "pool_name": attrs["name"],
        "dex": pool["relationships"]["dex"]["data"]["id"],
        "price_usd": float(attrs["base_token_price_usd"]),
        "market_cap_usd": float(attrs["market_cap_usd"]),
        "liquidity_usd": float(attrs["reserve_in_usd"]),
        "volume_24h_usd": float(attrs["volume_usd"]["h24"]),
        "price_change_24h_pct": float(attrs["price_change_percentage"]["h24"]),
        "transactions_24h": attrs["transactions"]["h24"],
        "source_url": POOLS_URL,
        "source_note": "GeckoTerminal public API snapshot; values are dynamic.",
    }
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    frame = pd.DataFrame(
        ohlcv["data"]["attributes"]["ohlcv_list"],
        columns=["timestamp_unix", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"],
    )
    frame["hour_utc"] = pd.to_datetime(frame["timestamp_unix"], unit="s", utc=True)
    frame["source_url"] = OHLCV_URL
    frame.sort_values("hour_utc")[[
        "hour_utc", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd", "source_url"
    ]].to_csv(OUTPUT, index=False)
    daily_frame = pd.DataFrame(
        daily["data"]["attributes"]["ohlcv_list"],
        columns=["timestamp_unix", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"],
    )
    daily_frame["date_utc"] = pd.to_datetime(daily_frame["timestamp_unix"], unit="s", utc=True)
    daily_frame["source_url"] = DAILY_URL
    daily_frame.sort_values("date_utc")[[
        "date_utc", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd", "source_url"
    ]].to_csv(DAILY_OUTPUT, index=False)
    print(
        f"wrote {len(frame)} NIULAI hourly candles, {len(daily_frame)} daily candles, "
        "and market snapshot"
    )


if __name__ == "__main__":
    main()
