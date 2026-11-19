"""Build an auditable same-stage market benchmark for newly traded tokens."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np
import pandas as pd


MARKET_METRICS = [
    "volume_h24_usd",
    "transactions_h24",
    "unique_traders_h24",
    "volume_liquidity_ratio_h24",
]


def normalize_geckoterminal_pools(
    records: Iterable[dict[str, Any]], snapshot_utc: str | datetime
) -> pd.DataFrame:
    """Flatten GeckoTerminal pool records into a stable analysis schema."""

    snapshot = pd.Timestamp(snapshot_utc)
    if snapshot.tzinfo is None:
        snapshot = snapshot.tz_localize("UTC")
    else:
        snapshot = snapshot.tz_convert("UTC")

    rows: list[dict[str, Any]] = []
    for record in records:
        attrs = record.get("attributes", {})
        relationships = record.get("relationships", {})
        created = pd.to_datetime(attrs.get("pool_created_at"), utc=True, errors="coerce")
        age_hours = (
            max((snapshot - created).total_seconds() / 3600, 0)
            if pd.notna(created)
            else np.nan
        )
        transactions = attrs.get("transactions", {}).get("h24", {}) or {}
        volume_h24 = _number((attrs.get("volume_usd", {}) or {}).get("h24"))
        liquidity = _number(attrs.get("reserve_in_usd"))
        buys = _integer(transactions.get("buys"))
        sells = _integer(transactions.get("sells"))
        token_id = relationships.get("base_token", {}).get("data", {}).get("id", "")
        rows.append(
            {
                "pool_id": record.get("id"),
                "pool_name": attrs.get("name"),
                "pool_address": attrs.get("address"),
                "token_address": token_id.removeprefix("base_"),
                "pool_created_at": created,
                "token_age_hours": age_hours,
                "token_age_bucket": age_bucket(age_hours),
                "liquidity_usd": liquidity,
                "liquidity_bucket_usd": liquidity_bucket(liquidity),
                "fdv_usd": _number(attrs.get("fdv_usd")),
                "market_cap_usd": _number(attrs.get("market_cap_usd")),
                "market_cap_bucket_usd": market_cap_bucket(
                    _number(attrs.get("market_cap_usd"))
                    if pd.notna(_number(attrs.get("market_cap_usd")))
                    else _number(attrs.get("fdv_usd"))
                ),
                "volume_h24_usd": volume_h24,
                "transactions_h24": buys + sells,
                "buys_h24": buys,
                "sells_h24": sells,
                "buy_transaction_share_h24": buys / (buys + sells)
                if buys + sells
                else np.nan,
                "unique_traders_h24": _integer(transactions.get("unique_traders")),
                "volume_liquidity_ratio_h24": volume_h24 / liquidity
                if liquidity and liquidity > 0
                else np.nan,
                "price_change_h24_pct": _number(
                    (attrs.get("price_change_percentage", {}) or {}).get("h24")
                ),
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["pool_id"], keep="first")


def select_matched_cohort(
    pools: pd.DataFrame,
    target_address: str,
    minimum_size: int = 20,
    desired_size: int = 40,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Match by chain universe, token age and liquidity without outcome leakage."""

    if pools.empty:
        raise ValueError("market benchmark input is empty")
    target_rows = pools[pools["token_address"].str.lower().eq(target_address.lower())]
    if target_rows.empty:
        raise ValueError("target token is missing from benchmark input")
    target = target_rows.sort_values("liquidity_usd", ascending=False).iloc[0]

    cohort = pools[
        pools["token_age_bucket"].eq(target["token_age_bucket"])
        & pools["liquidity_bucket_usd"].eq(target["liquidity_bucket_usd"])
    ]
    rule = "same_age_and_liquidity_bucket"
    if len(cohort) < minimum_size:
        candidates = pools.copy()
        target_age = max(float(target["token_age_hours"]), 0)
        target_liquidity = max(float(target["liquidity_usd"]), 0)
        candidates["match_distance"] = (
            np.abs(np.log1p(candidates["token_age_hours"]) - np.log1p(target_age))
            + 0.5
            * np.abs(
                np.log1p(candidates["liquidity_usd"])
                - np.log1p(target_liquidity)
            )
        )
        cohort = candidates.sort_values("match_distance").head(desired_size)
        rule = "nearest_neighbor_log_age_and_liquidity"

    cohort = cohort.drop_duplicates(subset=["pool_id"]).copy()
    if target["pool_id"] not in set(cohort["pool_id"]):
        cohort = pd.concat([cohort, target.to_frame().T], ignore_index=True)
    metadata = {
        "match_rule": rule,
        "cohort_size": int(len(cohort)),
        "target_pool_id": target["pool_id"],
        "target_age_bucket": target["token_age_bucket"],
        "target_liquidity_bucket": target["liquidity_bucket_usd"],
        "minimum_reliable_size": minimum_size,
        "desired_size": desired_size,
        "reliable_cohort_size": len(cohort) >= minimum_size,
        "matching_note": (
            "Nearest-neighbor fallback uses log token age plus half-weighted log liquidity "
            "distance when strict buckets contain fewer than the minimum sample."
            if rule == "nearest_neighbor_log_age_and_liquidity"
            else "Strict same-stage buckets contained enough observations."
        ),
    }
    return cohort, metadata


def calculate_market_percentiles(
    cohort: pd.DataFrame, target_pool_id: str, minimum_size: int = 20
) -> dict[str, Any]:
    """Calculate a transparent activity score from matched-cohort percentiles."""

    if len(cohort) < minimum_size:
        return {
            "status": "insufficient_cohort",
            "cohort_size": int(len(cohort)),
            "minimum_size": minimum_size,
            "market_activity_score_0_100": None,
        }
    frame = cohort.copy()
    target = frame[frame["pool_id"].eq(target_pool_id)]
    if target.empty:
        raise ValueError("target pool is missing from matched cohort")

    percentiles: dict[str, float | None] = {}
    for metric in MARKET_METRICS:
        valid = pd.to_numeric(frame[metric], errors="coerce")
        ranks = valid.rank(method="average", pct=True) * 100
        value = ranks.loc[target.index[0]]
        percentiles[metric] = round(float(value), 1) if pd.notna(value) else None
    valid_scores = [value for value in percentiles.values() if value is not None]
    score = round(float(np.mean(valid_scores)), 1) if valid_scores else None
    return {
        "status": "calibrated_snapshot",
        "cohort_size": int(len(frame)),
        "metric_percentiles": percentiles,
        "market_activity_score_0_100": score,
        "score_definition": "equal-weight mean of four same-stage activity percentiles",
        "excluded_from_score": ["price_change_h24_pct", "fdv_usd", "market_cap_usd"],
        "warning": "This is a current pool snapshot, not a prediction or investment score.",
    }


def age_bucket(hours: float | int | None) -> str:
    if hours is None or pd.isna(hours):
        return "unknown"
    if hours < 6:
        return "0-6h"
    if hours < 24:
        return "6-24h"
    if hours < 24 * 7:
        return "1-7d"
    if hours < 24 * 30:
        return "7-30d"
    return "30d+"


def liquidity_bucket(value: float | None) -> str:
    return _bucket(
        value,
        [(10_000, "<10k"), (50_000, "10k-50k"), (100_000, "50k-100k"), (500_000, "100k-500k")],
        "500k+",
    )


def market_cap_bucket(value: float | None) -> str:
    return _bucket(
        value,
        [(1_000_000, "<1m"), (10_000_000, "1m-10m"), (100_000_000, "10m-100m")],
        "100m+",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket(value: float | None, boundaries: list[tuple[float, str]], last: str) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    for upper, label in boundaries:
        if value < upper:
            return label
    return last


def _number(value: Any) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if pd.notna(parsed) else np.nan


def _integer(value: Any) -> int:
    parsed = pd.to_numeric(value, errors="coerce")
    return int(parsed) if pd.notna(parsed) else 0
