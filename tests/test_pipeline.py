from pathlib import Path

import pandas as pd

from pipeline import (
    build_onchain_profile,
    build_quality_report,
    build_case_timeline,
    build_readiness_score,
    calculate_event_window,
    load_daily_market,
    load_events,
    load_onchain_evidence,
    normalize_manual_sources,
    validate_daily_market,
    validate_events,
    validate_onchain_evidence,
)


ROOT = Path(__file__).parents[1]
DEMO_DATA = ROOT / "data" / "samples" / "events_demo.csv"
MANUAL_DATA = ROOT / "data" / "manual" / "social_sources.csv"
SOURCE_REGISTRY = ROOT / "data" / "sources" / "source_registry.csv"
NIULAI_MARKET = ROOT / "data" / "manual" / "niulai_daily_ohlcv.csv"
NIULAI_ONCHAIN = ROOT / "data" / "manual" / "niulai_onchain_evidence.csv"


def test_demo_data_loads_and_has_expected_rows():
    frame = load_events(DEMO_DATA)

    assert len(frame) == 8
    assert frame["event_id"].is_unique
    assert str(frame["event_time_utc"].dtype) == "datetime64[ns, UTC]"


def test_demo_data_schema_is_valid_but_warns_about_evidence():
    frame = load_events(DEMO_DATA)
    result = validate_events(frame)

    assert result.is_valid
    assert result.metrics["unverified_rows"] == 8
    assert result.warnings


def test_duplicate_event_id_is_rejected():
    frame = load_events(DEMO_DATA)
    frame.loc[1, "event_id"] = frame.loc[0, "event_id"]

    result = validate_events(frame)

    assert not result.is_valid
    assert result.metrics["duplicate_event_ids"] == 1


def test_manual_sources_normalize_to_unique_traceable_events():
    frame = normalize_manual_sources(MANUAL_DATA)

    assert len(frame) == 7
    assert frame["event_id"].is_unique
    assert frame["source_url"].str.startswith("https://").all()
    assert set(frame["evidence_status"]) == {"verified", "partial"}
    assert frame.loc[frame["case_id"] == "niulai", "contract_address"].nunique() == 1


def test_quality_report_keeps_missing_contracts_visible():
    frame = normalize_manual_sources(MANUAL_DATA)
    frame["event_time_utc"] = pd.to_datetime(
        frame["event_time_utc"], utc=True, format="mixed"
    )
    frame["collected_at_utc"] = pd.to_datetime(
        frame["collected_at_utc"], utc=True, format="mixed"
    )
    report = build_quality_report(frame)

    assert report["validation"]["is_valid"]
    assert report["missing_contract_addresses"] == 3
    assert report["evidence_status_counts"]["verified"] == 6


def test_source_registry_records_collection_and_terms_boundaries():
    registry = pd.read_csv(SOURCE_REGISTRY)

    assert {"source_id", "collection_mode", "automation_status", "terms_notes"}.issubset(
        registry.columns
    )
    assert registry["source_id"].is_unique
    assert registry["terms_notes"].fillna("").str.len().gt(0).all()


def test_niulai_daily_market_is_valid_and_continuous():
    frame = load_daily_market(NIULAI_MARKET)
    result = validate_daily_market(frame)

    assert len(frame) == 18
    assert result.is_valid
    assert result.metrics["missing_calendar_days"] == 0
    assert result.metrics["invalid_ohlc_rows"] == 0


def test_niulai_binance_event_window_is_reproducible():
    frame = load_daily_market(NIULAI_MARKET)
    metrics = calculate_event_window(frame, "2026-09-09T11:30:00Z")

    assert round(metrics["event_day_close_return_pct"], 2) == -22.91
    assert round(metrics["next_day_close_return_pct"], 2) == 54.18
    assert round(metrics["volume_multiple_vs_previous_day"], 2) == 2.16
    assert metrics["market_granularity"] == "1d_utc"


def test_invalid_ohlc_is_rejected():
    frame = load_daily_market(NIULAI_MARKET)
    frame.loc[0, "high_usd"] = frame.loc[0, "low_usd"] / 2

    result = validate_daily_market(frame)

    assert not result.is_valid
    assert result.metrics["invalid_ohlc_rows"] == 1


def test_niulai_timeline_combines_events_and_market_without_wallet_claims():
    events = load_events(ROOT / "data" / "processed" / "events_verified.csv")
    market = load_daily_market(NIULAI_MARKET)
    timeline = build_case_timeline(events, market, "NIULAI")

    assert len(timeline) == 21
    assert set(timeline["track"]) == {"platform_or_media", "market"}
    assert "wallet" not in set(timeline["track"])
    assert timeline["event_time_utc"].is_monotonic_increasing


def test_onchain_evidence_is_valid_but_preserves_conflicts():
    evidence = load_onchain_evidence(NIULAI_ONCHAIN)
    result = validate_onchain_evidence(evidence)
    profile = build_onchain_profile(evidence)

    assert result.is_valid
    assert result.metrics["project_claims"] == 5
    assert result.metrics["conflicting_facts"] == 3
    assert profile["wallet_confirmation_available"] is False
    assert profile["conflict_metrics"] == [
        "liquidity_control_status",
        "top10_share_pct",
    ]


def test_invalid_onchain_address_is_rejected():
    evidence = load_onchain_evidence(NIULAI_ONCHAIN)
    evidence.loc[0, "address"] = "not-an-address"

    result = validate_onchain_evidence(evidence)

    assert not result.is_valid
    assert result.metrics["invalid_entity_addresses"] == 1


def test_readiness_score_penalizes_missing_wallet_evidence():
    events = load_events(ROOT / "data" / "processed" / "events_verified.csv")
    market = load_daily_market(NIULAI_MARKET)
    profile = build_onchain_profile(load_onchain_evidence(NIULAI_ONCHAIN))
    metrics = __import__("json").loads(
        (ROOT / "data" / "processed" / "niulai_binance_event_metrics.json").read_text()
    )
    score = build_readiness_score(events, market, profile, metrics, "NIULAI")

    assert score["components"]["wallet_evidence"] == 0
    assert score["score"] == 48.5
    assert score["user_facing_status"] == "insufficient_evidence_for_push"

