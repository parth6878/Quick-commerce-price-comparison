"""
Quick Commerce Price Comparison — Application Entrypoint & CLI

Usage:
    # 1. Start the FastAPI Web & API server (default)
    python main.py
    python main.py --host 0.0.0.0 --port 8000 --reload

    # 2. Compare prices directly from the terminal (Instant Catalog / Dataset Mode)
    python main.py --query "milk"
    python main.py --query "bread"

    # 3. Compare prices using live browser scrapers (Blinkit, Zepto, Amazon Fresh)
    python main.py --query "amul butter" --live

    # 4. Trigger photo pre-seeding
    python main.py --seed --stores amazon
"""
import argparse
import sys
import os

# Ensure repository root is on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def run_cli_comparison(query: str, live: bool = False):
    """Run price comparison in terminal and print a formatted summary."""
    from services.matcher import cluster_products
    from services.catalog import get_local_items

    print("\n" + "=" * 70)
    print(f" Quick Commerce Comparison: '{query}' ({'Live Scrape' if live else 'Instant Catalog'})")
    print("=" * 70)

    if live:
        print("[*] Launching headless browser scrapers (Amazon, Blinkit, Zepto)...")
        from services.scrapers.runner import run_all_scrapers
        scraped = run_all_scrapers(query, timeout_seconds=30)
        blinkit_items = scraped.get("blinkit", [])
        zepto_items = scraped.get("zepto", [])
        amazon_items = scraped.get("amazon", [])
    else:
        print("[*] Retrieving from local bundled dataset & catalog...")
        local_data = get_local_items(query)
        blinkit_items = local_data.get("blinkit", [])
        zepto_items = local_data.get("zepto", [])
        amazon_items = local_data.get("amazon", [])

    result = cluster_products(blinkit_items, zepto_items, amazon_items, query=query)
    matched = result.get("matched_deals", [])
    single = result.get("single_store_items", [])

    print(f"\n[*] Found {len(matched)} matched deals across stores | {len(single)} single-store items\n")

    if not matched:
        print("[-] No multi-store matches found for this query.")
        if single:
            print("\nAvailable individual store items:")
            for item in single[:10]:
                store_name = item.get("cheapest_store") or (list(item.get("prices", {}).keys())[0] if item.get("prices") else "Store")
                print(f"  - [{store_name}] {item.get('canonical_name')} ({item.get('quantity') or '-'}) - Rs. {item.get('lowest_price')}")
        return

    # Print table header
    header = f"{'Product':<36} | {'Pack':<10} | {'Blinkit':<9} | {'Zepto':<9} | {'Amazon':<9} | {'Best Deal':<15}"
    print(header)
    print("-" * len(header))

    for deal in matched:
        name = deal.get("canonical_name", "")[:35]
        qty = (deal.get("quantity") or "-")[:10]
        prices = deal.get("prices", {})

        b_p = f"Rs {prices['Blinkit']:.0f}" if "Blinkit" in prices else "-"
        z_p = f"Rs {prices['Zepto']:.0f}" if "Zepto" in prices else "-"
        a_p = f"Rs {prices['Amazon']:.0f}" if "Amazon" in prices else "-"

        best = f"{deal.get('cheapest_store')} (Save Rs {deal.get('savings', 0):.0f})"
        print(f"{name:<36} | {qty:<10} | {b_p:<9} | {z_p:<9} | {a_p:<9} | {best:<15}")

    print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Quick Commerce Price Comparison (FastAPI server or terminal comparison CLI)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "127.0.0.1"),
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=True,
        help="Enable auto-reload on code change (default: True in dev)",
    )
    parser.add_argument(
        "--no-reload",
        action="store_false",
        dest="reload",
        help="Disable auto-reload",
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default=None,
        help="Run terminal price comparison for the given query instead of starting the server",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="When running --query, use live browser scrapers instead of instant catalog",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Run image seeder script to scrape and index product photos",
    )
    parser.add_argument(
        "--stores",
        type=str,
        default="amazon,blinkit,zepto",
        help="Comma-separated stores to seed when --seed is passed",
    )

    args = parser.parse_args()

    # Route 1: Image Seeder
    if args.seed:
        from scripts.seed_images import main as seed_main
        sys.exit(seed_main(["--stores", args.stores]))

    # Route 2: CLI Price Comparison
    if args.query:
        run_cli_comparison(args.query, live=args.live)
        return

    # Route 3: Web Server
    import uvicorn
    print(f"\n[*] Starting QuickCompare server at http://{args.host}:{args.port}")
    print(f"[*] Interactive API docs: http://{args.host}:{args.port}/docs")
    print(f"[*] Web Application UI:  http://{args.host}:{args.port}/app\n")
    uvicorn.run("app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()