"""Normalize X quote-endpoint results into posts and propagation edges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .x_posts import X_POST_COLUMNS, _classify_post_type, _non_negative_int


def normalize_x_quote_graph(
    raw_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    if payload.get("source") != "x_api_quote_graph":
        raise ValueError("expected an x_api_quote_graph artifact")

    post_records: list[dict[str, Any]] = []
    edge_records: list[dict[str, Any]] = []
    for seed in payload.get("seeds", []):
        root_post_id = str(seed.get("root_post_id", ""))
        seed_posts = [
            post
            for page in seed.get("pages", [])
            for post in (page.get("body") or {}).get("data") or []
        ]
        returned_ids = {str(post.get("id", "")) for post in seed_posts}
        for post in seed_posts:
            post_id = str(post.get("id", "")).strip()
            if not post_id:
                continue
            references = post.get("referenced_tweets") or []
            reference_types = [item.get("type", "") for item in references]
            reference_ids = [str(item.get("id", "")) for item in references if item.get("id")]
            propagation_level = _propagation_level(
                root_post_id, references, returned_ids
            )
            metrics = post.get("public_metrics") or {}
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
            post_records.append(
                {
                    "post_id": post_id,
                    "query_id": "quote_graph",
                    "matched_query_ids": "quote_graph",
                    "matched_via": "quote_endpoint",
                    "root_post_ids": root_post_id,
                    "propagation_level": propagation_level,
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
                    "search_query": "",
                    "collected_at_utc": payload.get("collected_at_utc"),
                    "collection_source": payload.get("source", ""),
                }
            )
            edge_records.append(
                {
                    "root_post_id": root_post_id,
                    "propagation_post_id": post_id,
                    "propagation_level": propagation_level,
                    "immediate_parent_ids": "|".join(reference_ids),
                    "immediate_relation_types": "|".join(reference_types),
                    "created_at_utc": post.get("created_at"),
                    "author_id": str(post.get("author_id", "")),
                    "source_url": f"https://x.com/i/web/status/{post_id}",
                }
            )

    posts = pd.DataFrame.from_records(post_records, columns=X_POST_COLUMNS)
    edges = pd.DataFrame.from_records(edge_records)
    for frame in (posts, edges):
        if not frame.empty:
            frame["created_at_utc"] = pd.to_datetime(
                frame["created_at_utc"], utc=True, errors="coerce"
            )
    if not posts.empty:
        roots = posts.groupby("post_id")["root_post_ids"].agg(
            lambda values: "|".join(sorted(set(values)))
        )
        posts = posts.drop_duplicates("post_id", keep="first").reset_index(drop=True)
        posts["root_post_ids"] = posts["post_id"].map(roots)
    if not edges.empty:
        edges = edges.drop_duplicates(
            ["root_post_id", "propagation_post_id"], keep="first"
        ).reset_index(drop=True)
    return posts, edges


def merge_x_posts_with_quote_graph(
    search_posts: pd.DataFrame, quote_posts: pd.DataFrame
) -> pd.DataFrame:
    if quote_posts.empty:
        return search_posts
    combined = pd.concat([search_posts, quote_posts], ignore_index=True)
    query_matches = combined.groupby("post_id")["matched_query_ids"].agg(
        lambda values: _join_pipe_values(values)
    )
    root_matches = combined.groupby("post_id")["root_post_ids"].agg(
        lambda values: _join_pipe_values(values)
    )
    propagation = combined.groupby("post_id")["propagation_level"].agg(
        lambda values: _preferred_propagation(values)
    )
    matched_via = combined.groupby("post_id")["matched_via"].agg(
        lambda values: _join_pipe_values(values)
    )
    merged = (
        combined.sort_values(
            ["created_at_utc", "post_id"], ascending=[False, False]
        )
        .drop_duplicates("post_id", keep="first")
        .reset_index(drop=True)
    )
    merged["matched_query_ids"] = merged["post_id"].map(query_matches)
    merged["root_post_ids"] = merged["post_id"].map(root_matches)
    merged["propagation_level"] = merged["post_id"].map(propagation)
    merged["matched_via"] = merged["post_id"].map(matched_via)
    return merged[X_POST_COLUMNS]


def _propagation_level(
    root_post_id: str, references: list[dict[str, Any]], returned_ids: set[str]
) -> str:
    if any(
        str(item.get("id", "")) == root_post_id and item.get("type") == "quoted"
        for item in references
    ):
        return "direct_quote"
    if any(str(item.get("id", "")) in returned_ids for item in references):
        return "downstream_amplification"
    return "endpoint_related_unresolved"


def _join_pipe_values(values: pd.Series) -> str:
    parts = {
        part
        for value in values.dropna().astype(str)
        for part in value.split("|")
        if part
    }
    return "|".join(sorted(parts))


def _preferred_propagation(values: pd.Series) -> str:
    priority = {
        "direct_quote": 3,
        "downstream_amplification": 2,
        "endpoint_related_unresolved": 1,
        "search_match": 0,
    }
    candidates = [value for value in values.dropna().astype(str) if value]
    return max(candidates, key=lambda value: priority.get(value, -1), default="search_match")
