"""
Seed static/img + data/image_index.json with REAL product photos scraped
from Blinkit, Zepto and Amazon Fresh for bundled queries.

Run from repository root:

    python scripts/seed_images.py                  # all seed queries, all stores
    python scripts/seed_images.py --stores amazon  # fast HTTP-only pass
    python scripts/seed_images.py --queries milk bread

The app (uvicorn) picks new photos up automatically: the index file's
mtime is re-checked on every lookup, and cached responses for a seeded
query are invalidated by the seeding endpoints/background jobs.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services import image_store
from services.image_scraper import (
    scrape_amazon_images,
    scrape_blinkit_multi,
    scrape_zepto_multi,
)
from services.catalog import CATALOG_DATABASE

# Every bundled dataset query: milk/dairy CSVs + the 8 catalogue categories.
DEFAULT_QUERIES = ["milk", *sorted(CATALOG_DATABASE.keys())]


def seed_amazon(queries, limit=24) -> int:
    total = 0
    for query in queries:
        try:
            candidates = scrape_amazon_images(query, limit=limit)
        except Exception as exc:
            print(f"[SEED AMAZON] {query!r} failed: {exc}")
            continue
        if candidates:
            stored = image_store.ingest_candidates("Amazon", candidates, query=query, cap=limit)
            total += stored
            print(f"[SEED AMAZON] {query!r}: stored {stored}/{len(candidates)}")
        time.sleep(1.0)  # stay polite; Amazon rate-limits aggressive clients
    return total


def seed_blinkit(queries, limit=24) -> int:
    try:
        results = scrape_blinkit_multi(queries, limit=limit)
    except Exception as exc:
        print(f"[SEED BLINKIT] browser run failed: {exc}")
        return 0
    total = 0
    for query, candidates in results.items():
        if candidates:
            stored = image_store.ingest_candidates("Blinkit", candidates, query=query, cap=limit)
            total += stored
            print(f"[SEED BLINKIT] {query!r}: stored {stored}/{len(candidates)}")
    return total


def seed_zepto(queries, limit=24) -> int:
    try:
        results = scrape_zepto_multi(queries, limit=limit)
    except Exception as exc:
        print(f"[SEED ZEPTO] browser run failed: {exc}")
        return 0
    total = 0
    for query, candidates in results.items():
        if candidates:
            stored = image_store.ingest_candidates("Zepto", candidates, query=query, cap=limit)
            total += stored
            print(f"[SEED ZEPTO] {query!r}: stored {stored}/{len(candidates)}")
    return total


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stores", default="amazon,blinkit,zepto",
        help="comma-separated subset of: amazon, blinkit, zepto",
    )
    parser.add_argument(
        "--queries", nargs="*", default=None,
        help="override the default seed query list",
    )
    parser.add_argument("--limit", type=int, default=24, help="photos per store per query")
    args = parser.parse_args(argv)

    queries = args.queries or DEFAULT_QUERIES
    wanted = [s.strip().lower() for s in args.stores.split(",") if s.strip()]
    print(f"Seeding queries={queries} stores={wanted}")

    started = time.time()
    stored_total = 0

    if "amazon" in wanted:          # fast HTTP pass first - instant visible win
        stored_total += seed_amazon(queries, limit=args.limit)
    if "blinkit" in wanted:         # one Chrome, all queries
        stored_total += seed_blinkit(queries, limit=args.limit)
    if "zepto" in wanted:           # one Chrome, location solved once
        stored_total += seed_zepto(queries, limit=args.limit)

    stats = image_store.stats()
    elapsed = time.time() - started
    print(
        f"Done in {elapsed:.0f}s: stored {stored_total} this run | "
        f"index now has {stats['photos']} photos in {stats['files']} files "
        f"across {stats['queries']} queries"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
