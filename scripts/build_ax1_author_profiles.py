"""Build the AX1 author-profile table from the paid X user lookup."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.x_users import build_ax1_author_profiles  # noqa: E402


RAW_USERS = (
    ROOT
    / "data"
    / "raw"
    / "x"
    / "ax1_20261118T041459Z"
    / "authors_top150.json"
)
CANDIDATES = ROOT / "data" / "processed" / "ax1_author_candidates.csv"
OUTPUT = ROOT / "data" / "processed" / "ax1_author_profiles.csv"


def main() -> None:
    frame = build_ax1_author_profiles(RAW_USERS, CANDIDATES, OUTPUT)
    profiled = int(frame["profile_evidence_status"].eq("api_collected").sum())
    print(f"Wrote {len(frame)} AX1 author candidates ({profiled} API profiles)")


if __name__ == "__main__":
    main()
