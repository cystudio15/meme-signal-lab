import json

import pandas as pd

from pipeline.x_posts import X_POST_COLUMNS
from pipeline.x_quotes import merge_x_posts_with_quote_graph, normalize_x_quote_graph


def test_quote_graph_distinguishes_direct_and_downstream(tmp_path):
    raw = tmp_path / "quotes.json"
    raw.write_text(
        json.dumps(
            {
                "source": "x_api_quote_graph",
                "collected_at_utc": "2026-11-18T05:00:00Z",
                "seeds": [
                    {
                        "root_post_id": "root",
                        "pages": [
                            {
                                "body": {
                                    "data": [
                                        {
                                            "id": "quote",
                                            "text": "four times",
                                            "referenced_tweets": [
                                                {"id": "root", "type": "quoted"}
                                            ],
                                        },
                                        {
                                            "id": "repost",
                                            "text": "RT four times",
                                            "referenced_tweets": [
                                                {"id": "quote", "type": "retweeted"}
                                            ],
                                        },
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    posts, edges = normalize_x_quote_graph(raw)

    assert len(posts) == 2
    assert edges["propagation_level"].value_counts().to_dict() == {
        "direct_quote": 1,
        "downstream_amplification": 1,
    }


def test_merge_quote_graph_adds_relation_to_existing_post():
    base = pd.DataFrame(
        [
            {
                **{column: "" for column in X_POST_COLUMNS},
                "post_id": "quote",
                "query_id": "original_discussion",
                "matched_query_ids": "original_discussion",
                "matched_via": "keyword_search",
                "propagation_level": "search_match",
                "created_at_utc": pd.Timestamp("2026-11-18T05:00:00Z"),
            }
        ]
    )
    quote = base.copy()
    quote.loc[0, "query_id"] = "quote_graph"
    quote.loc[0, "matched_query_ids"] = "quote_graph"
    quote.loc[0, "matched_via"] = "quote_endpoint"
    quote.loc[0, "root_post_ids"] = "root"
    quote.loc[0, "propagation_level"] = "direct_quote"

    merged = merge_x_posts_with_quote_graph(base, quote)

    assert len(merged) == 1
    assert merged.iloc[0]["matched_query_ids"] == "original_discussion|quote_graph"
    assert merged.iloc[0]["root_post_ids"] == "root"
    assert merged.iloc[0]["propagation_level"] == "direct_quote"
