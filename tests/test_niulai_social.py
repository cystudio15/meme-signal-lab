import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parents[1]


def test_niulai_collection_preserves_bounded_audit_counts():
    summary = json.loads(
        (ROOT / "data/processed/niulai_x_collection_summary.json").read_text()
    )
    assert summary["raw_post_reads"] == 953
    assert summary["recent_post_reads"] == 356
    assert summary["archive_post_reads"] == 597
    assert summary["eligible_unique_posts"] == 544
    assert summary["ambiguous_or_wrong_contract_posts"] == 311
    assert summary["archive_probe_reads"] == 10
    assert summary["failed_partial_archive_reads_upper_bound"] == 193
    assert summary["collection_status"] == "complete"


def test_niulai_entity_disambiguation_excludes_wrong_contracts():
    frame = pd.read_csv(ROOT / "data/processed/niulai_x_posts.csv")
    eligible = frame[frame["entity_match"].isin(["explicit", "contextual"])]
    target = "0xbeea1d618e533a387d941f58a7d4c9b7bd377777"
    texts_with_ca = eligible["text"].fillna("").loc[
        eligible["text"].fillna("").str.contains(r"0x[a-fA-F0-9]{40}", regex=True)
    ]
    assert texts_with_ca.str.lower().str.contains(target, regex=False).all()
    assert eligible["post_id"].is_unique

