"""Read event data and normalize its basic types."""

from pathlib import Path

import pandas as pd


BOOLEAN_COLUMNS = ["has_referral_link", "is_duplicate"]
DATETIME_COLUMNS = ["event_time_utc", "collected_at_utc"]
NUMERIC_COLUMNS = [
    "usd_value",
    "price_usd",
    "market_cap_usd",
    "volume_5m_usd",
    "liquidity_usd",
    "dex_boost_amount",
]


def load_events(path: str | Path) -> pd.DataFrame:
    """Load a CSV event table and convert known columns to useful types.

    Parameters
    ----------
    path:
        Location of the CSV file on disk.

    Returns
    -------
    pandas.DataFrame
        A table in memory. The source CSV is never modified.
    """

    frame = pd.read_csv(path)

    for column in DATETIME_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_datetime(
                frame[column], utc=True, errors="coerce", format="mixed"
            )

    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in BOOLEAN_COLUMNS:
        if column in frame.columns:
            frame[column] = (
                frame[column]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({"true": True, "false": False})
            )

    return frame

