import json

import pandas as pd

from pipeline.x_users import build_ax1_author_profiles, normalize_x_users


def user_payload():
    return {
        "source": "x_api_user_lookup",
        "collected_at_utc": "2026-11-18T05:00:00Z",
        "batches": [
            {
                "body": {
                    "data": [
                        {
                            "id": "1",
                            "username": "caller",
                            "name": "Caller",
                            "created_at": "2020-01-01T00:00:00Z",
                            "public_metrics": {
                                "followers_count": 2000,
                                "following_count": 100,
                                "tweet_count": 500,
                            },
                        }
                    ]
                }
            }
        ],
    }


def test_normalize_x_users_extracts_public_metrics():
    frame = normalize_x_users(user_payload())

    assert len(frame) == 1
    assert frame.iloc[0]["followers_count"] == 2000
    assert frame.iloc[0]["x_profile_url"] == "https://x.com/caller"


def test_build_author_profiles_uses_candidate_labels(tmp_path):
    raw = tmp_path / "users.json"
    candidates = tmp_path / "candidates.csv"
    output = tmp_path / "profiles.csv"
    raw.write_text(json.dumps(user_payload()), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "author_id": "1",
                "post_count": 2,
                "total_interactions": 10,
                "official_track_posts": 0,
                "callout_track_posts": 1,
                "selected_for_profile_lookup": True,
            }
        ]
    ).to_csv(candidates, index=False)

    frame = build_ax1_author_profiles(raw, candidates, output)

    assert frame.iloc[0]["profile_segment_candidate"] == "kol_callout_candidate"
    assert frame.iloc[0]["profile_evidence_status"] == "api_collected"
    assert output.exists()
