"""Explain social attention without pretending that attention is investment quality."""

from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "post_id",
    "author_id",
    "created_at_utc",
    "post_type",
    "total_interactions",
    "propagation_level",
}


def calculate_social_heat_evidence(
    posts: pd.DataFrame, collection_summary: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return auditable attention evidence, not a buy score or hotness rank.

    A cross-token heat level requires a benchmark matched by chain, token age,
    liquidity and observation window.  Until that benchmark exists, this
    function reports descriptive evidence and an explicit uncalibrated status.
    """

    missing = REQUIRED_COLUMNS.difference(posts.columns)
    if missing:
        raise ValueError(f"social heat input is missing columns: {sorted(missing)}")
    if posts.empty:
        raise ValueError("social heat input must contain at least one post")

    frame = posts.copy()
    frame["created_at_utc"] = pd.to_datetime(
        frame["created_at_utc"], utc=True, errors="coerce"
    )
    frame["total_interactions"] = pd.to_numeric(
        frame["total_interactions"], errors="coerce"
    ).fillna(0)

    author_counts = frame["author_id"].fillna("").replace("", pd.NA).value_counts()
    interaction = frame["total_interactions"]
    post_types = frame["post_type"].fillna("unknown")
    propagation = frame["propagation_level"].fillna("unknown")
    valid_times = frame["created_at_utc"].dropna()

    direct_quotes = int(propagation.eq("direct_quote").sum())
    downstream = int(propagation.eq("downstream_amplification").sum())
    summary = collection_summary or {}
    raw_reads = _optional_int(summary.get("raw_post_reads"))
    cross_query_duplicates = _optional_int(summary.get("cross_query_duplicates"))
    before_quote_graph = _optional_int(summary.get("unique_posts_before_quote_graph"))

    observation_start = valid_times.min() if not valid_times.empty else None
    observation_end = valid_times.max() if not valid_times.empty else None
    observation_hours = None
    if observation_start is not None and observation_end is not None:
        observation_hours = max(
            (observation_end - observation_start).total_seconds() / 3600, 0.0
        )

    result: dict[str, Any] = {
        "definition": {
            "heat": "attention and trading activity intensity",
            "authenticity": "whether activity is broad and information-bearing",
            "stage": "whether attention leads or follows market movement",
            "tradability": "whether liquidity and risk permit execution",
        },
        "social_attention": {
            "unique_posts": int(frame["post_id"].nunique()),
            "unique_authors": int(author_counts.size),
            "posts_per_author": _round(len(frame) / author_counts.size)
            if author_counts.size
            else None,
            "interaction_total": int(interaction.sum()),
            "interaction_mean": _round(interaction.mean()),
            "interaction_median": _round(interaction.median()),
            "interaction_p90": _round(interaction.quantile(0.90)),
            "original_share": _round(post_types.eq("original").mean()),
            "reply_share": _round(post_types.eq("reply").mean()),
            "retweet_share": _round(post_types.eq("retweet").mean()),
            "quote_share": _round(post_types.eq("quote").mean()),
            "top_10_author_post_share": _round(
                author_counts.head(10).sum() / len(frame)
            )
            if author_counts.size
            else None,
            "single_post_author_share": _round(
                author_counts.eq(1).sum() / author_counts.size
            )
            if author_counts.size
            else None,
        },
        "propagation": {
            "direct_quote_posts": direct_quotes,
            "downstream_amplification_posts": downstream,
            "quote_graph_posts": direct_quotes + downstream,
            "propagation_observed": bool(direct_quotes or downstream),
        },
        "collection_quality": {
            "raw_post_reads": raw_reads,
            "cross_query_duplicates": cross_query_duplicates,
            "cross_query_duplicate_rate": _round(
                cross_query_duplicates / raw_reads
            )
            if raw_reads and cross_query_duplicates is not None
            else None,
            "quote_graph_unique_addition_rate": _round(
                (len(frame) - before_quote_graph) / len(frame)
            )
            if before_quote_graph is not None and len(frame)
            else None,
        },
        "time_coverage": {
            "start_utc": observation_start.isoformat()
            if observation_start is not None
            else None,
            "end_utc": observation_end.isoformat()
            if observation_end is not None
            else None,
            "observation_hours": _round(observation_hours),
            "posts_per_observed_hour": _round(len(frame) / observation_hours)
            if observation_hours
            else None,
        },
        "calibration": {
            "status": "uncalibrated",
            "display_label": "传播已形成，热度等级待基准校准",
            "reason": (
                "No matched historical cohort yet. A level requires the same chain, "
                "token-age, liquidity and observation-window baseline."
            ),
            "score_0_100": None,
        },
        "interpretation": [
            "Quote and downstream propagation are observed in the collected graph."
            if direct_quotes or downstream
            else "No quote propagation was observed in this bounded collection.",
            "Interaction is long-tailed; report median and P90 beside the mean."
            if interaction.mean() > max(interaction.median() * 3, 1)
            else "Interaction mean and median are not strongly separated.",
            "This is a bounded X API snapshot, not a full-market census.",
        ],
    }
    return result


def build_hourly_social_activity(posts: pd.DataFrame) -> pd.DataFrame:
    """Aggregate collected posts into UTC hours for transparent trend inspection."""

    missing = REQUIRED_COLUMNS.difference(posts.columns)
    if missing:
        raise ValueError(f"social heat input is missing columns: {sorted(missing)}")

    frame = posts.copy()
    frame["created_at_utc"] = pd.to_datetime(
        frame["created_at_utc"], utc=True, errors="coerce"
    )
    frame["total_interactions"] = pd.to_numeric(
        frame["total_interactions"], errors="coerce"
    ).fillna(0)
    frame = frame.dropna(subset=["created_at_utc"])
    if frame.empty:
        return pd.DataFrame(
            columns=["hour_utc", "post_count", "unique_authors", "interactions"]
        )

    frame["hour_utc"] = frame["created_at_utc"].dt.floor("h")
    hourly = (
        frame.groupby("hour_utc", as_index=False)
        .agg(
            post_count=("post_id", "nunique"),
            unique_authors=("author_id", "nunique"),
            interactions=("total_interactions", "sum"),
        )
        .sort_values("hour_utc")
        .reset_index(drop=True)
    )
    return hourly


def _round(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
