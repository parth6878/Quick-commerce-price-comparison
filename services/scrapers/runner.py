from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any
from services.scrapers.blinkit import scrape_blinkit
from services.scrapers.zepto import scrape_zepto
from services.scrapers.amazon import scrape_amazon

def run_all_scrapers(query: str, timeout_seconds: int = 35) -> Dict[str, List[Dict[str, Any]]]:
    """
    Runs Blinkit, Zepto, and Amazon Fresh scrapers in parallel.
    Returns dictionary with store keys:
      {
         "blinkit": [...],
         "zepto": [...],
         "amazon": [...]
      }
    """
    results = {
        "blinkit": [],
        "zepto": [],
        "amazon": []
    }

    scrapers = {
        "blinkit": scrape_blinkit,
        "zepto": scrape_zepto,
        "amazon": scrape_amazon
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_store = {
            executor.submit(func, query): store_name
            for store_name, func in scrapers.items()
        }

        for future in as_completed(future_to_store, timeout=timeout_seconds):
            store = future_to_store[future]
            try:
                data = future.result()
                results[store] = data
                print(f"[{store.upper()}] Finished scraping, found {len(data)} items")
            except Exception as exc:
                print(f"[{store.upper()}] Scraper generated an exception: {exc}")
                results[store] = []

    return results
