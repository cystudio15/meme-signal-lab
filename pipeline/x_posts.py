"""Transform auditable X API raw collections into a readable post table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


X_POST_COLUMNS = [
    "post_id",
    "query_id",
    "matched_query_ids",
    "matched_via",
    "root_post_ids",
    "propagation_level",
    "created_at_utc",
    "author_id",
    "post_type",
    "text",
    "lang",
    "reply_count",
    "retweet_count",
    "like_count",
    "quote_count",
    "impression_count",
    "bookmark_count",
    "total_interactions",
    "possibly_sensitive",
    "conversation_id",
    "referenced_post_ids",
    "source_url",
    "search_query",
    "collected_at_utc",
    "collection_source",
]


def load_x_raw_collection(path: str | Path) -> dict[str, Any]:
    """Load one raw artifact written by the Go X collector."""

    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if payload.get("source") not in {"x_api_recent_search", "x_api_full_archive_search"}:
        raise ValueError("expected an X search raw collection")
    if not isinstance(payload.get("pages"), list):
        raise ValueError("raw X collection is missing pages")
    return payload


def normalize_x_posts(payload: dict[str, Any]) -> pd.DataFrame:
    """Flatten paginated X responses, normalize metrics, and deduplicate IDs."""

    records: list[dict[str, Any]] = []
    for page in payload.get("pages", []):
        body = page.get("body") or {}
        for post in body.get("data") or []:
            metrics = post.get("public_metrics") or {}
            references = post.get("referenced_tweets") or []
            reference_types = [item.get("type", "") for item in references]
            reference_ids = [item.get("id", "") for item in references if item.get("id")]

            counts = {
                name: _non_negative_int(metrics.get(name, 0))
                for name in (
                    "reply_count",
                    "retweet_count",
                    "like_count",
                    "quote_count",
                    "impression_count",
                    "bookmark_count",
                )
            }
            total_interactions = sum(
                counts[name]
                for name in (
                    "reply_count",
                    "retweet_count",
                    "like_count",
                    "quote_count",
                    "bookmark_count",
                )
            )
            post_id = str(post.get("id", "")).strip()
            if not post_id:
                continue

            records.append(
                {
                    "post_id": post_id,
                    "query_id": payload.get("query_id", ""),
                    "matched_query_ids": payload.get("query_id", ""),
                    "matched_via": "keyword_search",
                    "root_post_ids": "",
                    "propagation_level": "search_match",
                    "created_at_utc": post.get("created_at"),
                    "author_id": str(post.get("author_id", "")),
                    "post_type": _classify_post_type(reference_types),
                    "text": post.get("text", ""),
                    "lang": post.get("lang", "und"),
                    **counts,
                    "total_interactions": total_interactions,
                    "possibly_sensitive": bool(post.get("possibly_sensitive", False)),
                    "conversation_id": str(post.get("conversation_id", "")),
                    "referenced_post_ids": "|".join(reference_ids),
                    "source_url": f"https://x.com/i/web/status/{post_id}",
                    "search_query": payload.get("query", ""),
                    "collected_at_utc": payload.get("collected_at_utc"),
                    "collection_source": payload.get("source", ""),
                }
            )

    if not records:
        return pd.DataFrame(columns=X_POST_COLUMNS)

    frame = pd.DataFrame.from_records(records, columns=X_POST_COLUMNS)
    frame["created_at_utc"] = pd.to_datetime(
        frame["created_at_utc"], utc=True, errors="coerce"
    )
    frame["collected_at_utc"] = pd.to_datetime(
        frame["collected_at_utc"], utc=True, errors="coerce"
    )
    frame = (
        frame.drop_duplicates(subset=["post_id"], keep="first")
        .sort_values(["created_at_utc", "post_id"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return frame


def normalize_x_post_collections(paths: list[str | Path]) -> pd.DataFrame:
    """Merge query-track artifacts and preserve all tracks matched by each post."""

    frames = [normalize_x_posts(load_x_raw_collection(path)) for path in paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=X_POST_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    matched_queries = combined.groupby("post_id")["query_id"].agg(
        lambda values: "|".join(sorted({value for value in values if value}))
    )
    merged = (
        combined.sort_values(
            ["created_at_utc", "post_id"], ascending=[False, False]
        )
        .drop_duplicates(subset=["post_id"], keep="first")
        .reset_index(drop=True)
    )
    merged["matched_query_ids"] = merged["post_id"].map(matched_queries)
    return merged[X_POST_COLUMNS]


def build_x_posts_preview(raw_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Build a human-readable CSV from one raw artifact or a query directory."""

    source = Path(raw_path)
    if source.is_dir():
        paths = [
            path
            for path in sorted(source.glob("*.json"))
            if json.loads(path.read_text(encoding="utf-8")).get("source")
            in {"x_api_recent_search", "x_api_full_archive_search"}
        ]
    else:
        paths = [source]
    frame = normalize_x_post_collections(paths)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return frame


def _classify_post_type(reference_types: list[str]) -> str:
    mapping = {
        "retweeted": "retweet",
        "replied_to": "reply",
        "quoted": "quote",
    }
    for reference_type in ("retweeted", "replied_to", "quoted"):
        if reference_type in reference_types:
            return mapping[reference_type]
    return "original"


def _non_negative_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0
