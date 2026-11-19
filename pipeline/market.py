"""Load, validate, and summarize daily market candles around a known event."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


MARKET_COLUMNS = {
    "token_symbol",
    "contract_address",
    "chain",
    "date_utc",
    "open_usd",
    "high_usd",
    "low_usd",
    "close_usd",
    "volume_usd",
    "source_url",
    "crosscheck_url",
    "evidence_status",
    "collected_at_utc",
}
PRICE_COLUMNS = ["open_usd", "high_usd", "low_usd", "close_usd"]


@dataclass
class MarketValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int | float] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_daily_market(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date_utc"] = pd.to_datetime(frame["date_utc"], utc=True, errors="coerce")
    frame["collected_at_utc"] = pd.to_datetime(
        frame["collected_at_utc"], utc=True, errors="coerce", format="mixed"
    )
    for column in [*PRICE_COLUMNS, "volume_usd"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("date_utc").reset_index(drop=True)


def validate_daily_market(frame: pd.DataFrame) -> MarketValidation:
    result = MarketValidation(metrics={"rows": len(frame)})
    missing_columns = sorted(MARKET_COLUMNS - set(frame.columns))
    if missing_columns:
        result.errors.append(f"缺少行情字段：{', '.join(missing_columns)}")
        return result

    missing_values = int(frame[list(MARKET_COLUMNS)].isna().sum().sum())
    duplicates = int(frame.duplicated(["token_symbol", "date_utc"]).sum())
    negative_values = int((frame[[*PRICE_COLUMNS, "volume_usd"]] < 0).sum().sum())
    invalid_ohlc = int(
        (
            (frame["low_usd"] > frame[PRICE_COLUMNS].min(axis=1))
            | (frame["high_usd"] < frame[PRICE_COLUMNS].max(axis=1))
        ).sum()
    )
    result.metrics.update(
        {
            "missing_required_values": missing_values,
            "duplicate_token_dates": duplicates,
            "negative_numeric_values": negative_values,
            "invalid_ohlc_rows": invalid_ohlc,
        }
    )
    if missing_values:
        result.errors.append(f"行情必填字段共有 {missing_values} 个空值")
    if duplicates:
        result.errors.append(f"发现 {duplicates} 个重复 token/date")
    if negative_values:
        result.errors.append(f"发现 {negative_values} 个负价格或负成交量")
    if invalid_ohlc:
        result.errors.append(f"发现 {invalid_ohlc} 条 OHLC 高低价关系错误")

    gaps = frame["date_utc"].diff().dt.days.dropna()
    missing_days = int((gaps - 1).clip(lower=0).sum())
    result.metrics["missing_calendar_days"] = missing_days
    if missing_days:
        result.warnings.append(f"时间范围内缺少 {missing_days} 个日历日")
    return result


def _pct(current: float, baseline: float) -> float:
    return (current / baseline - 1.0) * 100.0


def calculate_event_window(
    frame: pd.DataFrame, event_time_utc: str | pd.Timestamp
) -> dict[str, float | str]:
    """Calculate transparent daily metrics without claiming intraday causality."""

    event_time = pd.Timestamp(event_time_utc)
    if event_time.tzinfo is None:
        event_time = event_time.tz_localize("UTC")
    else:
        event_time = event_time.tz_convert("UTC")
    event_day = event_time.normalize()

    indexed = frame.set_index("date_utc").sort_index()
    if event_day not in indexed.index:
        raise ValueError("event day is not present in market data")
    position = indexed.index.get_loc(event_day)
    if not isinstance(position, int) or position == 0 or position + 1 >= len(indexed):
        raise ValueError("event requires previous and next daily candles")

    previous = indexed.iloc[position - 1]
    event = indexed.iloc[position]
    following = indexed.iloc[position + 1]
    seven_day_target = event_day + pd.Timedelta(days=7)

    metrics: dict[str, float | str] = {
        "token_symbol": str(event["token_symbol"]),
        "event_time_utc": event_time.isoformat(),
        "market_granularity": "1d_utc",
        "previous_close_usd": float(previous["close_usd"]),
        "event_day_open_usd": float(event["open_usd"]),
        "event_day_high_usd": float(event["high_usd"]),
        "event_day_low_usd": float(event["low_usd"]),
        "event_day_close_usd": float(event["close_usd"]),
        "event_day_close_return_pct": _pct(
            float(event["close_usd"]), float(previous["close_usd"])
        ),
        "event_day_high_vs_previous_close_pct": _pct(
            float(event["high_usd"]), float(previous["close_usd"])
        ),
        "event_day_low_vs_previous_close_pct": _pct(
            float(event["low_usd"]), float(previous["close_usd"])
        ),
        "event_day_range_vs_open_pct": (
            (float(event["high_usd"]) - float(event["low_usd"]))
            / float(event["open_usd"])
            * 100.0
        ),
        "event_day_volume_usd": float(event["volume_usd"]),
        "volume_multiple_vs_previous_day": float(event["volume_usd"])
        / float(previous["volume_usd"]),
        "next_day_close_return_pct": _pct(
            float(following["close_usd"]), float(event["close_usd"])
        ),
    }
    if seven_day_target in indexed.index:
        metrics["seven_day_close_return_pct"] = _pct(
            float(indexed.loc[seven_day_target, "close_usd"]),
            float(event["close_usd"]),
        )
    metrics["causality_limit"] = (
        "Daily candles overlap the announcement and listing times; they show "
        "coincident volatility, not a causal post-event return."
    )
    return metrics


def write_event_window(metrics: dict, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_case_timeline(
    events: pd.DataFrame, market: pd.DataFrame, token_symbol: str
) -> pd.DataFrame:
    """Place evidence events and daily market observations on one audit table."""

    token = token_symbol.upper()
    selected_events = events.loc[events["token_symbol"].str.upper() == token].copy()
    event_rows = pd.DataFrame(
        {
            "event_time_utc": selected_events["event_time_utc"],
            "track": "platform_or_media",
            "event_type": selected_events["event_type"],
            "summary": selected_events["raw_text"],
            "price_usd": pd.NA,
            "volume_usd": pd.NA,
            "evidence_status": selected_events["evidence_status"],
            "source_url": selected_events["source_url"],
        }
    )

    selected_market = market.loc[
        market["token_symbol"].str.upper() == token
    ].copy()
    market_rows = pd.DataFrame(
        {
            # A candle labelled 2026-09-09 covers that UTC day and becomes
            # complete at 2026-09-10 00:00. Using the period end avoids placing
            # the day's close before intraday announcements on the timeline.
            "event_time_utc": selected_market["date_utc"] + pd.Timedelta(days=1),
            "track": "market",
            "event_type": "daily_close",
            "summary": selected_market["date_utc"].dt.strftime(
                "UTC daily candle for %Y-%m-%d"
            ),
            "price_usd": selected_market["close_usd"],
            "volume_usd": selected_market["volume_usd"],
            "evidence_status": selected_market["evidence_status"],
            "source_url": selected_market["source_url"],
        }
    )
    return (
        pd.concat([event_rows, market_rows], ignore_index=True)
        .sort_values(["event_time_utc", "track", "event_type"])
        .reset_index(drop=True)
    )
