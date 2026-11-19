"""Normalize manually verified public sources into the shared event schema."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from .io import load_events
from .validate import validate_events


OUTPUT_COLUMNS = [
    "event_id",
    "case_id",
    "token_symbol",
    "contract_address",
    "chain",
    "event_type",
    "event_time_utc",
    "collected_at_utc",
    "source_platform",
    "source_url",
    "source_account",
    "source_type",
    "raw_text",
    "language",
    "has_referral_link",
    "is_duplicate",
    "duplicate_group_id",
    "evidence_status",
    "collection_method",
    "time_method",
    "side",
    "price_usd",
    "notes",
]


def canonicalize_url(value: str) -> str:
    """Return a stable evidence URL without tracking fragments or media suffixes."""

    value = str(value).strip()
    parts = urlsplit(value)
    path = re.sub(r"/(photo|video)/\d+/?$", "", parts.path)
    query = parts.query if parts.netloc.lower() == "x.com" and path == "/search" else ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path.rstrip("/"), query, ""))


def _event_id(identity: str) -> str:
    return f"evt_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:12]}"


def normalize_manual_sources(path: str | Path) -> pd.DataFrame:
    """Load the curated input, normalize types, and mark exact duplicate evidence."""

    frame = pd.read_csv(path, keep_default_na=False)
    frame["source_url"] = frame["source_url"].map(canonicalize_url)
    frame["raw_text"] = frame.pop("text_summary").str.strip()
    frame["token_symbol"] = frame["token_symbol"].str.strip().str.upper()
    frame["contract_address"] = frame["contract_address"].str.strip().str.lower()
    frame["chain"] = frame["chain"].str.strip().str.lower()
    frame["has_referral_link"] = (
        frame["has_referral_link"].astype(str).str.lower().map({"true": True, "false": False})
    )

    identity = (
        frame["case_id"].astype(str)
        + "|"
        + frame["event_type"].astype(str)
        + "|"
        + frame["source_url"].astype(str)
    )
    frame["event_id"] = identity.map(_event_id)
    frame["is_duplicate"] = identity.duplicated(keep="first")
    duplicate_hash = identity.map(
        lambda value: f"dup_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:10]}"
    )
    frame["duplicate_group_id"] = duplicate_hash.where(
        identity.duplicated(keep=False), ""
    )
    # Keep the processed schema stable before market and wallet adapters arrive.
    # Blank values are honest missing data, not zero-price observations.
    frame["side"] = ""
    frame["price_usd"] = pd.NA

    normalized = frame.loc[:, OUTPUT_COLUMNS].copy()
    normalized = normalized.loc[~normalized["is_duplicate"]].reset_index(drop=True)
    return normalized


def write_processed_events(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Build the reproducible processed CSV and return it with parsed data types."""

    normalized = normalize_manual_sources(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False)
    return load_events(output_path)


def build_quality_report(frame: pd.DataFrame) -> dict:
    """Summarize provenance, missing evidence, and schema validation."""

    result = validate_events(frame)
    missing_contract = int(frame["contract_address"].fillna("").eq("").sum())
    return {
        "rows": len(frame),
        "cases": int(frame["case_id"].nunique()),
        "unique_source_urls": int(frame["source_url"].nunique()),
        "duplicate_event_ids": int(frame["event_id"].duplicated().sum()),
        "missing_contract_addresses": missing_contract,
        "evidence_status_counts": {
            str(key): int(value)
            for key, value in frame["evidence_status"].value_counts().sort_index().items()
        },
        "collection_method_counts": {
            str(key): int(value)
            for key, value in frame["collection_method"].value_counts().sort_index().items()
        },
        "validation": {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "metrics": result.metrics,
        },
    }


def write_quality_report(frame: pd.DataFrame, output_path: str | Path) -> dict:
    report = build_quality_report(frame)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report
