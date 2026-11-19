from pipeline.market_benchmark import (
    age_bucket,
    calculate_market_percentiles,
    normalize_geckoterminal_pools,
    select_matched_cohort,
)


def record(index: int, token: str, liquidity: float, volume: float) -> dict:
    return {
        "id": f"base_pool_{index}",
        "attributes": {
            "address": f"pool-{index}",
            "name": f"TOKEN{index} / WETH",
            "pool_created_at": "2026-11-17T00:00:00Z",
            "reserve_in_usd": str(liquidity),
            "fdv_usd": "5000000",
            "market_cap_usd": None,
            "volume_usd": {"h24": str(volume)},
            "transactions": {
                "h24": {
                    "buys": index + 1,
                    "sells": index,
                    "unique_traders": index + 2,
                }
            },
            "price_change_percentage": {"h24": str(index)},
        },
        "relationships": {
            "base_token": {"data": {"id": f"base_{token}"}},
            "dex": {"data": {"id": "test-dex"}},
        },
    }


def test_age_bucket_boundaries():
    assert age_bucket(5.9) == "0-6h"
    assert age_bucket(6) == "6-24h"
    assert age_bucket(24) == "1-7d"
    assert age_bucket(24 * 7) == "7-30d"


def test_normalize_and_match_cohort():
    records = [record(i, f"0x{i:040x}", 200_000, i * 1_000) for i in range(25)]
    target = records[10]["relationships"]["base_token"]["data"]["id"].split("_", 1)[1]
    frame = normalize_geckoterminal_pools(records, "2026-11-18T12:00:00Z")
    cohort, metadata = select_matched_cohort(frame, target)

    assert len(cohort) == 25
    assert metadata["reliable_cohort_size"] is True
    assert frame.loc[0, "volume_liquidity_ratio_h24"] == 0


def test_market_score_excludes_price_return():
    records = [record(i, f"0x{i:040x}", 200_000, i * 1_000) for i in range(25)]
    frame = normalize_geckoterminal_pools(records, "2026-11-18T12:00:00Z")
    result = calculate_market_percentiles(frame, "base_pool_10")

    assert result["status"] == "calibrated_snapshot"
    assert result["market_activity_score_0_100"] is not None
    assert "price_change_h24_pct" in result["excluded_from_score"]


def test_sparse_bucket_uses_nearest_neighbors():
    records = [
        record(i, f"0x{i:040x}", 20_000 + i * 20_000, i * 1_000)
        for i in range(50)
    ]
    frame = normalize_geckoterminal_pools(records, "2026-11-18T12:00:00Z")
    target = records[10]["relationships"]["base_token"]["data"]["id"].split("_", 1)[1]
    cohort, metadata = select_matched_cohort(frame, target, minimum_size=30)

    assert len(cohort) == 40
    assert metadata["match_rule"] == "nearest_neighbor_log_age_and_liquidity"
