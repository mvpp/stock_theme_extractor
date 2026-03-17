#!/usr/bin/env python3
"""Suggest taxonomy.yaml entries by clustering theme embeddings.

Offline developer tool — run manually to discover natural groupings
among the ~200 canonical themes, then copy proposed entries into
stock_themes/taxonomy.yaml after human review.

Usage:
    python scripts/suggest_taxonomy.py [--threshold 0.4] [--min-cluster 2]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Suggest taxonomy groupings")
    parser.add_argument(
        "--threshold", type=float, default=0.4,
        help="Cosine distance threshold for agglomerative clustering (default: 0.4)"
    )
    parser.add_argument(
        "--min-cluster", type=int, default=2,
        help="Minimum cluster size to report (default: 2)"
    )
    args = parser.parse_args()

    try:
        import numpy as np
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import pdist
    except ImportError:
        print("Install scipy: pip install scipy")
        sys.exit(1)

    from stock_themes.semantic.embedder import get_theme_embeddings
    from stock_themes.taxonomy.tree import get_theme_tree

    # Load existing tree to highlight themes not yet placed
    tree = get_theme_tree()
    placed = tree.themes_in_tree()

    # Get theme embeddings
    theme_names, theme_embeddings = get_theme_embeddings()
    embeddings_np = theme_embeddings.cpu().numpy()

    # Compute pairwise cosine distances
    distances = pdist(embeddings_np, metric="cosine")

    # Agglomerative clustering
    Z = linkage(distances, method="average", metric="cosine")
    labels = fcluster(Z, t=args.threshold, criterion="distance")

    # Group themes by cluster
    clusters: dict[int, list[str]] = {}
    for name, label in zip(theme_names, labels):
        clusters.setdefault(label, []).append(name)

    # Sort clusters by size, report only clusters >= min_cluster
    sorted_clusters = sorted(clusters.items(), key=lambda x: -len(x[1]))

    print(f"\n{'='*60}")
    print(f"Theme Clustering (threshold={args.threshold}, model=all-MiniLM-L6-v2)")
    print(f"{'='*60}")
    print(f"Total themes: {len(theme_names)}")
    print(f"Already in taxonomy.yaml: {len(placed)}")
    print(f"Clusters found: {len([c for c in sorted_clusters if len(c[1]) >= args.min_cluster])}")
    print()

    for cluster_id, members in sorted_clusters:
        if len(members) < args.min_cluster:
            continue

        # Find which members are already placed in taxonomy
        unplaced = [m for m in members if m not in placed]
        in_tree = [m for m in members if m in placed]

        marker = " (all placed)" if not unplaced else ""
        print(f"--- Cluster {cluster_id} ({len(members)} themes){marker} ---")

        # Suggest the shortest-named theme as root (heuristic for most general)
        root_candidate = min(members, key=len)

        for m in sorted(members):
            status = "  [in tree]" if m in placed else "  [NEW]"
            root_mark = " <-- suggested root" if m == root_candidate else ""
            print(f"  {m}{status}{root_mark}")

        if unplaced:
            print(f"\n  Suggested YAML:")
            print(f"  {root_candidate}:")
            for m in sorted(unplaced):
                if m != root_candidate:
                    print(f"    {m}: {{}}")
            print()
        print()


if __name__ == "__main__":
    main()
