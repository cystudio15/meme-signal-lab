"""Rank AX1 authors before the paid X user-profile lookup."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data" / "processed" / "ax1_x_posts.csv"
CANDIDATES = ROOT / "data" / "processed" / "ax1_author_candidates.csv"
IDS = ROOT / "data" / "processed" / "ax1_author_ids_top150.txt"
AUTHOR_LIMIT = 150


def main() -> None:
    posts = pd.read_csv(
        POSTS,
        dtype={"post_id": "string", "author_id": "string"},
    )
    posts["created_at_utc"] = pd.to_datetime(
        posts["created_at_utc"], utc=True, errors="coerce"
    )
    posts["is_official_track"] = posts["matched_query_ids"].fillna("").str.contains(
        r"(?:^|\|)official(?:$|\|)", regex=True
    )
    posts["is_callout_track"] = posts["matched_query_ids"].fillna("").str.contains(
        r"(?:^|\|)callouts(?:$|\|)", regex=True
    )

    candidates = (
        posts.groupby("author_id", as_index=False)
        .agg(
            post_count=("post_id", "count"),
            total_interactions=("total_interactions", "sum"),
            total_impressions=("impression_count", "sum"),
            official_track_posts=("is_official_track", "sum"),
            callout_track_posts=("is_callout_track", "sum"),
            first_post_utc=("created_at_utc", "min"),
            last_post_utc=("created_at_utc", "max"),
        )
        .assign(
            selection_score=lambda frame: (
                frame["official_track_posts"] * 1_000_000
                + frame["callout_track_posts"] * 10_000
                + frame["post_count"] * 100
                + frame["total_interactions"]
            )
        )
        .sort_values(
            ["selection_score", "post_count", "total_interactions", "author_id"],
            ascending=[False, False, False, True],
        )
        .reset_index(drop=True)
    )
    candidates["selected_for_profile_lookup"] = candidates.index < AUTHOR_LIMIT
    candidates.to_csv(CANDIDATES, index=False)

    selected = candidates.loc[candidates["selected_for_profile_lookup"], "author_id"]
    IDS.write_text("\n".join(selected.astype(str)) + "\n", encoding="utf-8")
    print(f"Selected {len(selected)} of {len(candidates)} AX1 authors")


if __name__ == "__main__":
    main()
