"""Convert the latest AX1 raw X query directory into a readable CSV."""

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.x_posts import normalize_x_post_collections  # noqa: E402
from pipeline.x_quotes import (  # noqa: E402
    merge_x_posts_with_quote_graph,
    normalize_x_quote_graph,
)


RAW_ROOT = ROOT / "data" / "raw" / "x"
OUTPUT = ROOT / "data" / "processed" / "ax1_x_posts.csv"
SUMMARY = ROOT / "data" / "processed" / "ax1_x_collection_summary.json"
QUOTE_EDGES = ROOT / "data" / "processed" / "ax1_quote_edges.csv"


def main() -> None:
    candidates = sorted(path for path in RAW_ROOT.glob("ax1_*") if path.is_dir())
    if not candidates:
        raise FileNotFoundError("no AX1 X collection directory found")
    search_paths = []
    for directory in candidates:
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("source") == "x_api_recent_search":
                search_paths.append(path)
    frame = normalize_x_post_collections(search_paths)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    base_unique_posts = len(frame)
    quote_reads = 0
    direct_quotes = 0
    downstream_amplifications = 0
    quote_post_frames = []
    quote_edge_frames = []
    for quote_path in [directory / "quote_graph.json" for directory in candidates]:
        if not quote_path.exists():
            continue
        quote_payload = json.loads(quote_path.read_text(encoding="utf-8"))
        quote_reads += int(quote_payload.get("quote_post_count", 0))
        quote_posts, quote_edges = normalize_x_quote_graph(quote_path)
        quote_post_frames.append(quote_posts)
        quote_edge_frames.append(quote_edges)
    if quote_post_frames:
        import pandas as pd

        quote_posts = pd.concat(quote_post_frames, ignore_index=True).drop_duplicates(
            subset=["post_id"], keep="first"
        )
        quote_edges = pd.concat(quote_edge_frames, ignore_index=True).drop_duplicates()
        frame = merge_x_posts_with_quote_graph(frame, quote_posts)
        frame.to_csv(OUTPUT, index=False)
        quote_edges.to_csv(QUOTE_EDGES, index=False)
        direct_quotes = int(quote_edges["propagation_level"].eq("direct_quote").sum())
        downstream_amplifications = int(
            quote_edges["propagation_level"].eq("downstream_amplification").sum()
        )
    search_payloads = []
    user_count = 0
    for directory in candidates:
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("source") == "x_api_recent_search":
                search_payloads.append(payload)
            elif payload.get("source") == "x_api_user_lookup":
                user_count += int(payload.get("user_count", 0))
    raw_rows = sum(int(payload.get("post_count", 0)) for payload in search_payloads)
    diagnostic_post_reads = 2
    summary = {
        "case_id": "ax1_base_launch",
        "raw_collection_directories": [
            str(directory.relative_to(ROOT)) for directory in candidates
        ],
        "latest_raw_collection_directory": str(candidates[-1].relative_to(ROOT)),
        "collection_runs": len(candidates),
        "query_track_reads": len(search_payloads),
        "query_tracks": len(
            {payload.get("query_id") for payload in search_payloads if payload.get("query_id")}
        ),
        "raw_post_reads": raw_rows,
        "unique_posts_before_quote_graph": base_unique_posts,
        "quote_graph_post_reads": quote_reads,
        "diagnostic_post_reads": diagnostic_post_reads,
        "unique_posts_after_quote_graph": len(frame),
        "cross_query_duplicates": raw_rows - base_unique_posts,
        "unique_authors": int(frame["author_id"].nunique()),
        "direct_quote_edges": direct_quotes,
        "downstream_amplification_edges": downstream_amplifications,
        "profile_reads": user_count,
        "collection_status": "complete",
    }
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(frame)} X posts to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
