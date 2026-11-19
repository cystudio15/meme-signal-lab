"""Download an auditable hourly AX1 OHLCV snapshot from GeckoTerminal."""

from __future__ import annotations

import json
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POOL = "0x28752b1c1be27a1d5947dc880dd7d969de945f7a7718d6f3747776dfd536ea76"
URL = (
    "https://api.geckoterminal.com/api/v2/networks/base/pools/"
    f"{POOL}/ohlcv/hour?aggregate=1&limit=168&currency=usd&token=base"
)
RAW_PATH = ROOT / "data/raw/market/ax1_hourly_ohlcv.json"
OUTPUT_PATH = ROOT / "data/processed/ax1_hourly_ohlcv.csv"


def main() -> None:
    context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    request = Request(URL, headers={"User-Agent": "Meme-Signal-Lab/1.0"})
    with urlopen(request, timeout=30, context=context) as response:
        payload = json.load(response)

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = payload["data"]["attributes"]["ohlcv_list"]
    frame = pd.DataFrame(
        rows,
        columns=[
            "timestamp_unix",
            "open_usd",
            "high_usd",
            "low_usd",
            "close_usd",
            "volume_usd",
        ],
    )
    frame["hour_utc"] = pd.to_datetime(frame["timestamp_unix"], unit="s", utc=True)
    frame["source_url"] = URL
    frame = frame.sort_values("hour_utc").reset_index(drop=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame[
        [
            "hour_utc",
            "open_usd",
            "high_usd",
            "low_usd",
            "close_usd",
            "volume_usd",
            "source_url",
        ]
    ].to_csv(OUTPUT_PATH, index=False)
    print(f"wrote {len(frame)} hourly candles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
