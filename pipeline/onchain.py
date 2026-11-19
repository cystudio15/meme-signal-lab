"""Validate public on-chain evidence without inventing wallet labels."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


EVM_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
REQUIRED_COLUMNS = {
    "fact_id",
    "token_symbol",
    "contract_address",
    "observed_at_utc",
    "entity_type",
    "metric_name",
    "source_url",
    "evidence_status",
    "interpretation",
}


@dataclass
class OnchainValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int | float] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_onchain_evidence(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["observed_at_utc"] = pd.to_datetime(
        frame["observed_at_utc"], utc=True, errors="coerce", format="mixed"
    )
    frame["value_numeric"] = pd.to_numeric(frame["value_numeric"], errors="coerce")
    frame["contract_address"] = frame["contract_address"].str.lower()
    frame["address"] = frame["address"].fillna("").str.lower()
    return frame


def validate_onchain_evidence(frame: pd.DataFrame) -> OnchainValidation:
    result = OnchainValidation(metrics={"rows": len(frame)})
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        result.errors.append(f"缺少链上证据字段：{', '.join(missing_columns)}")
        return result

    missing_values = int(
        frame[list(REQUIRED_COLUMNS)].replace("", pd.NA).isna().sum().sum()
    )
    duplicate_ids = int(frame["fact_id"].duplicated().sum())
    invalid_contracts = int(
        (~frame["contract_address"].fillna("").map(lambda x: bool(EVM_ADDRESS.match(x)))).sum()
    )
    nonempty_addresses = frame["address"].fillna("").ne("")
    invalid_addresses = int(
        (~frame.loc[nonempty_addresses, "address"].map(lambda x: bool(EVM_ADDRESS.match(x)))).sum()
    )
    missing_value = int(
        (frame["value_numeric"].isna() & frame["value_text"].fillna("").eq("")).sum()
    )
    result.metrics.update(
        {
            "duplicate_fact_ids": duplicate_ids,
            "missing_required_values": missing_values,
            "invalid_contract_addresses": invalid_contracts,
            "invalid_entity_addresses": invalid_addresses,
            "facts_without_value": missing_value,
        }
    )
    if missing_values:
        result.errors.append(f"链上证据必填字段共有 {missing_values} 个空值")
    if duplicate_ids:
        result.errors.append(f"发现 {duplicate_ids} 个重复 fact_id")
    if invalid_contracts or invalid_addresses:
        result.errors.append("存在非法 EVM 地址")
    if missing_value:
        result.errors.append(f"发现 {missing_value} 条没有数值或文本值的事实")

    project_claims = int(frame["evidence_status"].eq("project_claim").sum())
    conflicts = int(frame["evidence_status"].eq("conflicting_secondary").sum())
    result.metrics["project_claims"] = project_claims
    result.metrics["conflicting_facts"] = conflicts
    if project_claims:
        result.warnings.append(f"有 {project_claims} 条项目方声明尚未完成链上核验")
    if conflicts:
        result.warnings.append(f"有 {conflicts} 条二级来源冲突，需要池级/区块级复核")
    return result


def build_onchain_profile(frame: pd.DataFrame) -> dict:
    validation = validate_onchain_evidence(frame)
    creator_rows = frame.loc[frame["metric_name"] == "creator_address"]
    conflict_metrics = sorted(
        frame.loc[
            frame["evidence_status"] == "conflicting_secondary", "metric_name"
        ].unique()
    )
    holder_rows = frame.loc[frame["metric_name"] == "holder_count", "value_numeric"]
    return {
        "token_symbol": str(frame["token_symbol"].iloc[0]),
        "contract_address": str(frame["contract_address"].iloc[0]),
        "creator_candidate": (
            str(creator_rows["value_text"].iloc[0]) if not creator_rows.empty else None
        ),
        "holder_count_snapshot": (
            int(holder_rows.iloc[-1]) if not holder_rows.empty else None
        ),
        "wallet_transaction_events": 0,
        "wallet_confirmation_available": False,
        "conflict_metrics": conflict_metrics,
        "profile_status": "needs_primary_onchain_verification",
        "validation": {
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "metrics": validation.metrics,
        },
        "interpretation": (
            "The creator candidate and holder snapshot are research leads. "
            "No historical wallet trade path or Smart Money label is verified."
        ),
    }


def write_onchain_profile(profile: dict, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
