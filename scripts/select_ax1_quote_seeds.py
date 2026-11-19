"""Select AX1 posts that X reports as having one or more quote posts."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data" / "processed" / "ax1_x_posts.csv"
SEEDS = ROOT / "data" / "processed" / "ax1_quote_seeds.csv"
IDS = ROOT / "data" / "processed" / "ax1_quote_seed_ids.txt"


def main() -> None:
    posts = pd.read_csv(POSTS, dtype={"post_id": "string"})
    seeds = (
        posts.loc[posts["quote_count"].fillna(0).gt(0)]
        .sort_values(["quote_count", "post_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    seeds.to_csv(SEEDS, index=False)
    IDS.write_text("\n".join(seeds["post_id"].astype(str)) + "\n", encoding="utf-8")
    print(
        f"Selected {len(seeds)} quote seeds with "
        f"{int(seeds['quote_count'].sum())} reported quote posts"
    )


if __name__ == "__main__":
    main()
