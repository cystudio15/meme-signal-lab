#!/usr/bin/env python3
"""Validate NIULAI daily candles and calculate the exchange event window."""

from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.market import (
    build_case_timeline,
    calculate_event_window,
    load_daily_market,
    validate_daily_market,
    write_event_window,
)
from pipeline import load_events


INPUT = ROOT / "data" / "manual" / "niulai_daily_ohlcv.csv"
OUTPUT = ROOT / "data" / "processed" / "niulai_binance_event_metrics.json"
EVENTS = ROOT / "data" / "processed" / "events_verified.csv"
TIMELINE = ROOT / "data" / "processed" / "niulai_timeline.csv"


def main() -> None:
    frame = load_daily_market(INPUT)
    validation = validate_daily_market(frame)
    if not validation.is_valid:
        raise SystemExit("; ".join(validation.errors))
    metrics = calculate_event_window(frame, "2026-09-09T11:30:00Z")
    write_event_window(metrics, OUTPUT)
    timeline = build_case_timeline(load_events(EVENTS), frame, "NIULAI")
    timeline.to_csv(TIMELINE, index=False)
    print(f"Validated {len(frame)} NIULAI daily candles")
    print(f"Event-day close return: {metrics['event_day_close_return_pct']:.2f}%")
    print(f"Next-day close return: {metrics['next_day_close_return_pct']:.2f}%")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {len(timeline)} timeline rows to {TIMELINE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
