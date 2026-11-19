"""Transparent evidence-readiness scoring for a Meme signal candidate."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


WEIGHTS = {
    "source_traceability": 0.25,
    "market_data_quality": 0.20,
    "timing_resolution": 0.20,
    "wallet_evidence": 0.20,
    "contract_evidence": 0.15,
}


def build_readiness_score(
    events: pd.DataFrame,
    market: pd.DataFrame,
    onchain_profile: dict,
    event_metrics: dict,
    token_symbol: str,
) -> dict:
    """Score whether evidence is ready for a user-facing signal, not the token."""

    token = token_symbol.upper()
    selected = events.loc[events["token_symbol"].str.upper() == token]
    verified_share = (
        float(selected["evidence_status"].eq("verified").mean())
        if len(selected)
        else 0.0
    )
    source_traceability = round(verified_share * 100.0, 2)

    market_crosschecked = bool(
        len(market)
        and market["evidence_status"].eq("crosschecked_secondary").all()
    )
    market_data_quality = 70.0 if market_crosschecked else 35.0
    timing_resolution = 25.0 if event_metrics.get("market_granularity") == "1d_utc" else 80.0
    wallet_evidence = 0.0 if not onchain_profile["wallet_confirmation_available"] else 70.0

    conflict_count = len(onchain_profile.get("conflict_metrics", []))
    claim_count = onchain_profile["validation"]["metrics"].get("project_claims", 0)
    contract_evidence = max(0.0, 70.0 - conflict_count * 15.0 - claim_count * 2.0)

    components = {
        "source_traceability": source_traceability,
        "market_data_quality": market_data_quality,
        "timing_resolution": timing_resolution,
        "wallet_evidence": wallet_evidence,
        "contract_evidence": contract_evidence,
    }
    readiness = round(sum(components[key] * WEIGHTS[key] for key in WEIGHTS), 2)
    return {
        "token_symbol": token,
        "score_name": "evidence_decision_readiness",
        "score": readiness,
        "score_out_of": 100,
        "components": components,
        "weights": WEIGHTS,
        "confidence": "low",
        "lifecycle_observation": "catalyst-driven high volatility",
        "user_facing_status": "insufficient_evidence_for_push",
        "blocking_gaps": [
            "No verified wallet transaction path or wallet labels",
            "Daily candles cannot measure post-announcement 15m/1h/4h returns",
            "Conflicting liquidity-control and holder-concentration evidence",
        ],
        "market_path_observations": {
            "event_day_close_return_pct": event_metrics[
                "event_day_close_return_pct"
            ],
            "event_day_range_vs_open_pct": event_metrics[
                "event_day_range_vs_open_pct"
            ],
            "next_day_close_return_pct": event_metrics[
                "next_day_close_return_pct"
            ],
        },
        "explanation": (
            "This score measures whether the product has enough auditable evidence to "
            "show a high-confidence signal. It is not a buy score, price forecast, "
            "or smart-money claim. Missing wallet evidence scores zero rather than "
            "being silently omitted."
        ),
    }


def write_readiness_score(score: dict, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
