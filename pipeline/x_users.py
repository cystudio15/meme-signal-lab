"""Normalize X user lookup artifacts and join transparent author features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def normalize_x_users(payload: dict[str, Any]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    collected_at = payload.get("collected_at_utc")
    for batch in payload.get("batches", []):
        for user in (batch.get("body") or {}).get("data") or []:
            metrics = user.get("public_metrics") or {}
            records.append(
                {
                    "author_id": str(user.get("id", "")),
                    "username": user.get("username", ""),
                    "name": user.get("name", ""),
                    "account_created_at_utc": user.get("created_at"),
                    "description": user.get("description", ""),
                    "location": user.get("location", ""),
                    "verified": bool(user.get("verified", False)),
                    "verified_type": user.get("verified_type", ""),
                    "protected": bool(user.get("protected", False)),
                    "followers_count": _integer(metrics.get("followers_count")),
                    "following_count": _integer(metrics.get("following_count")),
                    "tweet_count": _integer(metrics.get("tweet_count")),
                    "listed_count": _integer(metrics.get("listed_count")),
                    "like_count": _integer(metrics.get("like_count")),
                    "media_count": _integer(metrics.get("media_count")),
                    "profile_url": user.get("url", ""),
                    "profile_image_url": user.get("profile_image_url", ""),
                    "x_profile_url": f"https://x.com/{user.get('username', '')}",
                    "profile_collected_at_utc": collected_at,
                }
            )
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        return frame
    frame["account_created_at_utc"] = pd.to_datetime(
        frame["account_created_at_utc"], utc=True, errors="coerce"
    )
    frame["profile_collected_at_utc"] = pd.to_datetime(
        frame["profile_collected_at_utc"], utc=True, errors="coerce"
    )
    frame = frame.drop_duplicates("author_id", keep="first").reset_index(drop=True)
    return frame


def build_ax1_author_profiles(
    raw_users_path: str | Path,
    candidates_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    payload = json.loads(Path(raw_users_path).read_text(encoding="utf-8"))
    profiles = normalize_x_users(payload)
    candidates = pd.read_csv(candidates_path, dtype={"author_id": "string"})
    merged = candidates.merge(profiles, on="author_id", how="left", validate="one_to_one")

    collected = pd.to_datetime(
        merged["profile_collected_at_utc"], utc=True, errors="coerce"
    )
    created = pd.to_datetime(
        merged["account_created_at_utc"], utc=True, errors="coerce"
    )
    merged["account_age_days"] = (collected - created).dt.days
    merged["profile_segment_candidate"] = merged.apply(_candidate_segment, axis=1)
    merged["profile_evidence_status"] = merged["username"].apply(
        lambda value: "api_collected" if pd.notna(value) and value != "" else "not_looked_up"
    )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(destination, index=False)
    return merged


def _candidate_segment(row: pd.Series) -> str:
    if not bool(row.get("selected_for_profile_lookup", False)):
        return "not_profiled"
    if _integer(row.get("official_track_posts")) > 0:
        return "official_source_candidate"
    if _integer(row.get("callout_track_posts")) > 0 and _integer(
        row.get("followers_count")
    ) >= 1_000:
        return "kol_callout_candidate"
    if _integer(row.get("callout_track_posts")) > 0:
        return "callout_candidate"
    if _integer(row.get("post_count")) >= 3 and _integer(
        row.get("followers_count")
    ) < 100:
        return "high_frequency_low_reach_candidate"
    return "community_candidate"


def _integer(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0
