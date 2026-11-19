"""Recalculate AX1 calibration from the last audited market snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.market_benchmark import calculate_market_percentiles, select_matched_cohort


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data/raw/market/ax1_base_pool_snapshot.json"
UNIVERSE_PATH = ROOT / "data/processed/base_pool_benchmark_universe.csv"
COHORT_PATH = ROOT / "data/processed/ax1_market_matched_cohort.csv"
RESULT_PATH = ROOT / "data/processed/ax1_market_heat_benchmark.json"
TARGET = "0x0947fb7076bfa307796f8fd533055f6016c6cccc"
SOURCE_URL = (
    "https://api.geckoterminal.com/api/v2/networks/base/tokens/"
    f"{TARGET}/pools?page=1"
)


def main() -> None:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    universe = pd.read_csv(UNIVERSE_PATH)
    cohort, match = select_matched_cohort(universe, TARGET)
    cohort.to_csv(COHORT_PATH, index=False)
    calibration = calculate_market_percentiles(
        cohort, match["target_pool_id"], match["minimum_reliable_size"]
    )
    target = cohort[cohort["pool_id"].eq(match["target_pool_id"])].iloc[0]
    result = {
        "snapshot_utc": raw["snapshot_utc"],
        "source_url": SOURCE_URL,
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
            "Nearest-neighbor matching improves comparability but does not create historical outcomes.",
            "Percentiles describe this collection-time snapshot and can change with the market.",
            "Market activity is separate from social authenticity, safety and expected return.",
        ],
    }
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
