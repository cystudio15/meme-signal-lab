import pandas as pd
import pytest

from pipeline.social_heat import (
    build_hourly_social_activity,
    calculate_social_heat_evidence,
)


def sample_posts():
    return pd.DataFrame(
        [
            {
                "post_id": "1",
                "author_id": "a",
                "created_at_utc": "2026-11-18T01:05:00Z",
                "post_type": "original",
                "total_interactions": 0,
                "propagation_level": "search_match",
            },
            {
                "post_id": "2",
                "author_id": "b",
                "created_at_utc": "2026-11-18T01:45:00Z",
                "post_type": "reply",
                "total_interactions": 1,
                "propagation_level": "direct_quote",
            },
            {
                "post_id": "3",
                "author_id": "a",
                "created_at_utc": "2026-11-18T02:15:00Z",
                "post_type": "retweet",
                "total_interactions": 100,
                "propagation_level": "downstream_amplification",
            },
        ]
    )


def test_social_heat_reports_evidence_without_inventing_score():
    summary = {
        "raw_post_reads": 4,
        "cross_query_duplicates": 1,
        "unique_posts_before_quote_graph": 2,
    }

    result = calculate_social_heat_evidence(sample_posts(), summary)

    assert result["social_attention"]["unique_posts"] == 3
    assert result["social_attention"]["unique_authors"] == 2
    assert result["social_attention"]["interaction_median"] == 1.0
    assert result["propagation"]["direct_quote_posts"] == 1
    assert result["propagation"]["downstream_amplification_posts"] == 1
    assert result["collection_quality"]["cross_query_duplicate_rate"] == 0.25
    assert result["calibration"]["status"] == "uncalibrated"
    assert result["calibration"]["score_0_100"] is None


def test_hourly_social_activity_uses_utc_hours():
    hourly = build_hourly_social_activity(sample_posts())

    assert hourly["post_count"].tolist() == [2, 1]
    assert hourly["unique_authors"].tolist() == [2, 1]
    assert hourly["interactions"].tolist() == [1, 100]
    assert str(hourly["hour_utc"].dtype) == "datetime64[ns, UTC]"


def test_social_heat_rejects_missing_schema():
    with pytest.raises(ValueError, match="missing columns"):
        calculate_social_heat_evidence(pd.DataFrame({"post_id": ["1"]}))
