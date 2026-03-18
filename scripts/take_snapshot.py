#!/usr/bin/env python3
"""CLI script to take a daily theme snapshot for the dashboard."""

import argparse
import sys
from pathlib import Path

# Add api/ directory to path so themes_api is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from themes_api.services.snapshot import take_snapshot


def main():
    parser = argparse.ArgumentParser(description="Take a daily theme snapshot")
    parser.add_argument("--db", default="stock_themes.db", help="Path to SQLite database")
    parser.add_argument("--date", default=None, help="Snapshot date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    result = take_snapshot(args.db, args.date)
    print(f"Snapshot {result['snapshot_date']}: "
          f"{result['themes']} themes, {result['stock_theme_pairs']} stock-theme pairs")


if __name__ == "__main__":
    main()
