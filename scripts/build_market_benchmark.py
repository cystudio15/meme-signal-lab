"""Collect a free Base pool snapshot and calibrate AX1 market activity."""

from __future__ import annotations

import json
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from pipeline.market_benchmark import (
    calculate_market_percentiles,
    normalize_geckoterminal_pools,
    select_matched_cohort,
    utc_now_iso,
)


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data/raw/market/ax1_base_pool_snapshot.json"
UNIVERSE_PATH = ROOT / "data/processed/base_pool_benchmark_universe.csv"
COHORT_PATH = ROOT / "data/processed/ax1_market_matched_cohort.csv"
RESULT_PATH = ROOT / "data/processed/ax1_market_heat_benchmark.json"
TARGET = "0x0947fb7076bfa307796f8fd533055f6016c6cccc"
BASE_URL = "https://api.geckoterminal.com/api/v2"
SYSTEM_CA_FILE = Path("/etc/ssl/cert.pem")


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "Meme-Signal-Lab/1.0"})
    context = (
        ssl.create_default_context(cafile=str(SYSTEM_CA_FILE))
        if SYSTEM_CA_FILE.exists()
        else ssl.create_default_context()
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30, context=context) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            retry_after = int(error.headers.get("Retry-After", 15))
            time.sleep(min(max(retry_after, 10), 45))
    raise RuntimeError("unreachable retry state")


def main() -> None:
    snapshot_utc = utc_now_iso()
    payloads: list[dict] = []
    records: list[dict] = []
    urls = [
        f"{BASE_URL}/networks/base/trending_pools?page={page}"
        for page in range(1, 11)
    ] + [
        f"{BASE_URL}/networks/base/new_pools?page={page}"
        for page in range(1, 11)
    ] + [f"{BASE_URL}/networks/base/tokens/{TARGET}/pools?page=1"]

    for index, url in enumerate(urls):
        payload = fetch_json(url)
        payloads.append({"url": url, "response": payload})
        records.extend(payload.get("data", []))
        if index < len(urls) - 1:
            time.sleep(6.1)

    raw = {
        "snapshot_utc": snapshot_utc,
        "source": "GeckoTerminal public API",
        "request_count": len(urls),
        "payloads": payloads,
    }
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    universe = normalize_geckoterminal_pools(records, snapshot_utc)
    universe = universe.sort_values(
        ["token_age_hours", "volume_h24_usd"], ascending=[True, False]
    )
    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(UNIVERSE_PATH, index=False)

    cohort, match = select_matched_cohort(universe, TARGET)
    cohort.to_csv(COHORT_PATH, index=False)
    calibration = calculate_market_percentiles(
        cohort, match["target_pool_id"], match["minimum_reliable_size"]
    )
    target = cohort[cohort["pool_id"].eq(match["target_pool_id"])].iloc[0]
    result = {
        "snapshot_utc": snapshot_utc,
        "source_url": f"{BASE_URL}/networks/base/tokens/{TARGET}/pools?page=1",
        "universe": {
            "unique_pools": int(len(universe)),
            "sampling": "ten trending pages plus ten new-pool pages on Base",
        },
        "matching": match,
        "target": {
            key: _json_value(target[key])
            for key in [
                "pool_id",
                "pool_name",
                "pool_created_at",
                "token_age_hours",
                "token_age_bucket",
                "liquidity_usd",
                "liquidity_bucket_usd",
                "fdv_usd",
                "volume_h24_usd",
                "transactions_h24",
                "unique_traders_h24",
                "volume_liquidity_ratio_h24",
                "price_change_h24_pct",
            ]
        },
        "calibration": calibration,
        "limits": [
            "The universe contains trending and new Base pools, not only manually verified Meme tokens.",
            "Percentiles describe this collection-time snapshot and can change with the market.",
            "Market activity is separate from social authenticity, safety and expected return.",
        ],
    }
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {UNIVERSE_PATH} ({len(universe)} unique pools)")
    print(f"wrote {COHORT_PATH} ({len(cohort)} matched pools)")
    print(f"wrote {RESULT_PATH}")


def _json_value(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


if __name__ == "__main__":
    main()
