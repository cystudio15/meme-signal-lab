import json

import pandas as pd

from pipeline.x_posts import (
    build_x_posts_preview,
    normalize_x_post_collections,
    normalize_x_posts,
)


def sample_payload():
    first_post = {
        "id": "100",
        "created_at": "2026-11-17T10:00:00Z",
        "author_id": "author-1",
        "conversation_id": "conversation-1",
        "text": "Meme test reply",
        "lang": "en",
        "possibly_sensitive": False,
        "referenced_tweets": [{"type": "replied_to", "id": "90"}],
        "public_metrics": {
            "reply_count": 1,
            "retweet_count": 2,
            "like_count": 3,
            "quote_count": 4,
            "impression_count": 50,
            "bookmark_count": 5,
        },
    }
    return {
        "source": "x_api_recent_search",
        "query_id": "test_track",
        "query": "$MEME",
        "collected_at_utc": "2026-11-17T10:05:00Z",
        "pages": [
            {"body": {"data": [first_post]}},
            {"body": {"data": [first_post, {"id": "101", "text": "original"}]}},
        ],
    }


def test_normalize_x_posts_deduplicates_and_calculates_interactions():
    frame = normalize_x_posts(sample_payload())

    assert frame["post_id"].tolist() == ["100", "101"]
    reply = frame.loc[frame["post_id"] == "100"].iloc[0]
    assert reply["post_type"] == "reply"
    assert reply["total_interactions"] == 15
    assert reply["impression_count"] == 50
    assert reply["source_url"] == "https://x.com/i/web/status/100"
    assert reply["matched_query_ids"] == "test_track"
    assert str(frame["created_at_utc"].dtype) == "datetime64[ns, UTC]"


def test_build_x_posts_preview_writes_readable_csv(tmp_path):
    raw_path = tmp_path / "raw.json"
    output_path = tmp_path / "preview.csv"
    raw_path.write_text(json.dumps(sample_payload()), encoding="utf-8")

    written = build_x_posts_preview(raw_path, output_path)
    reloaded = pd.read_csv(output_path)

    assert len(written) == 2
    assert reloaded["post_id"].astype(str).tolist() == ["100", "101"]
    assert "text" in reloaded.columns
    assert "source_url" in reloaded.columns


def test_normalize_multiple_query_tracks_preserves_matches(tmp_path):
    first = sample_payload()
    second = sample_payload()
    second["query_id"] = "second_track"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")

    merged = normalize_x_post_collections([first_path, second_path])

    assert len(merged) == 2
    assert set(merged["matched_query_ids"]) == {"second_track|test_track"}
