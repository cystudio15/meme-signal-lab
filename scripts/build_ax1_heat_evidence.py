"""Build descriptive AX1 social-attention evidence and an hourly time series."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.social_heat import (  # noqa: E402
    build_hourly_social_activity,
    calculate_social_heat_evidence,
)


POSTS = ROOT / "data" / "processed" / "ax1_x_posts.csv"
COLLECTION_SUMMARY = ROOT / "data" / "processed" / "ax1_x_collection_summary.json"
EVIDENCE_OUTPUT = ROOT / "data" / "processed" / "ax1_social_heat_evidence.json"
HOURLY_OUTPUT = ROOT / "data" / "processed" / "ax1_social_activity_hourly.csv"


def main() -> None:
    posts = pd.read_csv(POSTS, dtype={"post_id": "string", "author_id": "string"})
    summary = json.loads(COLLECTION_SUMMARY.read_text(encoding="utf-8"))
    evidence = calculate_social_heat_evidence(posts, summary)
    hourly = build_hourly_social_activity(posts)

    EVIDENCE_OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    hourly.to_csv(HOURLY_OUTPUT, index=False)
    print(f"Wrote {EVIDENCE_OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {HOURLY_OUTPUT.relative_to(ROOT)} ({len(hourly)} hourly rows)")


if __name__ == "__main__":
    main()
