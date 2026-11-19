#!/usr/bin/env python3
"""Build on-chain evidence profile and final decision-readiness score."""

from pathlib import Path
import json
import sys


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import load_daily_market, load_events
from pipeline.onchain import (
    build_onchain_profile,
    load_onchain_evidence,
    write_onchain_profile,
)
from pipeline.scoring import build_readiness_score, write_readiness_score


ONCHAIN_INPUT = ROOT / "data" / "manual" / "niulai_onchain_evidence.csv"
EVENTS_INPUT = ROOT / "data" / "processed" / "events_verified.csv"
MARKET_INPUT = ROOT / "data" / "manual" / "niulai_daily_ohlcv.csv"
EVENT_METRICS_INPUT = (
    ROOT / "data" / "processed" / "niulai_binance_event_metrics.json"
)
PROFILE_OUTPUT = ROOT / "data" / "processed" / "niulai_onchain_profile.json"
SCORE_OUTPUT = ROOT / "data" / "processed" / "niulai_readiness_score.json"


def main() -> None:
    evidence = load_onchain_evidence(ONCHAIN_INPUT)
    profile = build_onchain_profile(evidence)
    if not profile["validation"]["is_valid"]:
        raise SystemExit("; ".join(profile["validation"]["errors"]))
    write_onchain_profile(profile, PROFILE_OUTPUT)

    event_metrics = json.loads(EVENT_METRICS_INPUT.read_text(encoding="utf-8"))
    score = build_readiness_score(
        load_events(EVENTS_INPUT),
        load_daily_market(MARKET_INPUT),
        profile,
        event_metrics,
        "NIULAI",
    )
    write_readiness_score(score, SCORE_OUTPUT)
    print(f"Validated {len(evidence)} on-chain evidence facts")
    print(f"Decision readiness: {score['score']}/100 ({score['confidence']} confidence)")
    print(f"Wrote {PROFILE_OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {SCORE_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
