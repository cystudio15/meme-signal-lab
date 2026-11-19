#!/usr/bin/env python3
"""Build the verified social-event sample and machine-readable quality report."""

from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.manual_sources import write_processed_events, write_quality_report


INPUT = ROOT / "data" / "manual" / "social_sources.csv"
OUTPUT = ROOT / "data" / "processed" / "events_verified.csv"
REPORT = ROOT / "data" / "processed" / "quality_report.json"


def main() -> None:
    frame = write_processed_events(INPUT, OUTPUT)
    report = write_quality_report(frame, REPORT)
    print(f"Wrote {report['rows']} events to {OUTPUT.relative_to(ROOT)}")
    print(f"Validation passed: {report['validation']['is_valid']}")
    print(f"Quality report: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
