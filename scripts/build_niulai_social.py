"""Normalize NIULAI X collections and build attention artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.social_heat import build_hourly_social_activity, calculate_social_heat_evidence  # noqa: E402
from pipeline.x_posts import normalize_x_post_collections  # noqa: E402

RAW = ROOT / "data/raw/x"
PROCESSED = ROOT / "data/processed"
TARGET_CA = "0xbeea1d618e533a387d941f58a7d4c9b7bd377777"


def label_entity_match(posts: pd.DataFrame) -> pd.DataFrame:
    """Separate the target token from generic '牛来' phrases and same-name tokens."""

    frame = posts.copy()
    text = frame["text"].fillna("")
    addresses = text.str.findall(r"0x[a-fA-F0-9]{40}")
    wrong_ca = addresses.map(
        lambda values: any(value.lower() != TARGET_CA for value in values)
    ) & ~text.str.contains(TARGET_CA, case=False, regex=False)
    explicit = (
        frame["matched_query_ids"].fillna("").str.contains("official", regex=False)
        | text.str.contains(r"\$NIULAI|@niulai_on_bnb|#牛来", case=False, regex=True)
        | text.str.contains(TARGET_CA, case=False, regex=False)
    )
    token_context = text.str.contains(
        r"币安|binance|bnb|bsc|token|meme|币|持仓|抄底|市值|价格|现货|合约|社区|钱包|"
        r"聪明钱|涨|跌|买|卖|交易|仓位|控盘|k线|回撤|倍|u\b",
        case=False,
        regex=True,
    )
    contextual = text.str.contains("牛来", regex=False) & token_context & ~wrong_ca
    frame["entity_match"] = "ambiguous"
    frame.loc[contextual, "entity_match"] = "contextual"
    frame.loc[explicit & ~wrong_ca, "entity_match"] = "explicit"
    frame.loc[wrong_ca, "entity_match"] = "wrong_contract"
    return frame


def main() -> None:
    directories = sorted(path for path in RAW.glob("niulai_*") if path.is_dir())
    if not directories:
        raise FileNotFoundError("no NIULAI X collection directory found")
    paths, payloads = [], []
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("source") in {"x_api_recent_search", "x_api_full_archive_search"}:
                paths.append(path)
                payloads.append(payload)
    posts = label_entity_match(normalize_x_post_collections(paths))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    posts.to_csv(PROCESSED / "niulai_x_posts.csv", index=False)
    raw_reads = sum(int(item.get("post_count", 0)) for item in payloads)
    archive_reads = sum(
        int(item.get("post_count", 0))
        for item in payloads
        if item.get("source") == "x_api_full_archive_search"
    )
    recent_reads = raw_reads - archive_reads
    eligible = posts[posts["entity_match"].isin(["explicit", "contextual"])].copy()
    summary = {
        "case_id": "niulai_bnb_current",
        "raw_collection_directories": [str(path.relative_to(ROOT)) for path in directories],
        "latest_raw_collection_directory": str(directories[-1].relative_to(ROOT)),
        "query_track_reads": len(payloads),
        "query_tracks": len({item.get("query_id") for item in payloads}),
        "raw_post_reads": raw_reads,
        "recent_post_reads": recent_reads,
        "archive_post_reads": archive_reads,
        "unique_posts_before_quote_graph": len(posts),
        "unique_posts_after_quote_graph": len(posts),
        "cross_query_duplicates": raw_reads - len(posts),
        "unique_authors": int(posts["author_id"].nunique()),
        "eligible_unique_posts": len(eligible),
        "eligible_unique_authors": int(eligible["author_id"].nunique()),
        "ambiguous_or_wrong_contract_posts": int(len(posts) - len(eligible)),
        "archive_probe_reads": 10,
        "failed_partial_archive_reads_upper_bound": 193,
        "collection_status": "complete"
    }
    (PROCESSED / "niulai_x_collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    evidence = calculate_social_heat_evidence(eligible, summary)
    (PROCESSED / "niulai_social_heat_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    build_hourly_social_activity(eligible).to_csv(
        PROCESSED / "niulai_social_activity_hourly.csv", index=False
    )
    print(
        f"NIULAI: {len(eligible)} eligible of {len(posts)} unique posts / "
        f"{eligible.author_id.nunique()} authors"
    )


if __name__ == "__main__":
    main()
