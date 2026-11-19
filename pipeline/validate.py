"""Small, explainable data-quality checks for the event table."""

from dataclasses import dataclass, field

import pandas as pd


REQUIRED_COLUMNS = {
    "event_id",
    "token_symbol",
    "contract_address",
    "chain",
    "event_type",
    "event_time_utc",
    "collected_at_utc",
    "source_platform",
    "source_url",
    "source_type",
    "evidence_status",
}

# Some research events describe a platform campaign or an industry narrative,
# not one specific token. They still need a contract_address column for schema
# stability, but the value may be blank and must remain visibly missing.
REQUIRED_VALUE_COLUMNS = REQUIRED_COLUMNS - {"contract_address"}

ALLOWED_SOURCE_TYPES = {
    "official_project",
    "official_platform",
    "kol",
    "affiliate",
    "community",
    "paid_visibility",
    "bot_or_suspicious",
    "news_media",
    "onchain",
    "market",
    "unknown",
}


@dataclass
class ValidationResult:
    """Human-readable validation output used by tests and the UI."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int | float] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_events(frame: pd.DataFrame) -> ValidationResult:
    """Validate schema, identity, timestamps, and source classifications."""

    result = ValidationResult(metrics={"rows": len(frame)})
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        result.errors.append(f"缺少必填字段：{', '.join(missing_columns)}")
        return result

    duplicate_ids = int(frame["event_id"].duplicated().sum())
    missing_required = int(
        frame[list(REQUIRED_VALUE_COLUMNS)].replace("", pd.NA).isna().sum().sum()
    )
    invalid_sources = int((~frame["source_type"].isin(ALLOWED_SOURCE_TYPES)).sum())
    invalid_event_times = int(frame["event_time_utc"].isna().sum())
    invalid_collection_times = int(frame["collected_at_utc"].isna().sum())

    result.metrics.update(
        {
            "duplicate_event_ids": duplicate_ids,
            "missing_required_values": missing_required,
            "invalid_source_types": invalid_sources,
            "invalid_event_times": invalid_event_times,
            "invalid_collection_times": invalid_collection_times,
        }
    )

    if duplicate_ids:
        result.errors.append(f"发现 {duplicate_ids} 个重复 event_id")
    if missing_required:
        result.errors.append(f"必填字段共有 {missing_required} 个空值")
    if invalid_sources:
        result.errors.append(f"发现 {invalid_sources} 个未知 source_type")
    if invalid_event_times or invalid_collection_times:
        result.errors.append("存在无法解析的 UTC 时间")

    valid_times = frame["event_time_utc"].notna() & frame["collected_at_utc"].notna()
    collected_before_event = int(
        (
            frame.loc[valid_times, "collected_at_utc"]
            < frame.loc[valid_times, "event_time_utc"]
        ).sum()
    )
    result.metrics["collected_before_event"] = collected_before_event
    if collected_before_event:
        result.warnings.append(
            f"有 {collected_before_event} 条记录的采集时间早于事件时间，请核查时区"
        )

    unverified = int((frame["evidence_status"] != "verified").sum())
    result.metrics["unverified_rows"] = unverified
    if unverified:
        result.warnings.append(f"有 {unverified} 条记录尚未验证或仅用于演示")

    return result

