from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Dict, List, Any
from services.scrapers.blinkit import scrape_blinkit
from services.scrapers.zepto import scrape_zepto
from services.scrapers.amazon import scrape_amazon

def run_all_scrapers(query: str, timeout_seconds: int = 25) -> Dict[str, List[Dict[str, Any]]]:
    """
    Runs Blinkit, Zepto, and Amazon Fresh scrapers in parallel.
    Returns dictionary with store keys:
      {
         "blinkit": [...],
         "zepto": [...],
         "amazon": [...]
      }
    Scrapers that time out keep whatever they produced; the caller falls back
    to the bundled dataset for any store that returned nothing.
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

    executor = ThreadPoolExecutor(max_workers=3)
    future_to_store = {
        executor.submit(func, query): store_name
        for store_name, func in scrapers.items()
    }

    try:
        for future in as_completed(future_to_store, timeout=timeout_seconds):
            store = future_to_store[future]
            try:
                data = future.result()
                results[store] = data
                print(f"[{store.upper()}] Finished scraping, found {len(data)} items")
            except Exception as exc:
                print(f"[{store.upper()}] Scraper generated an exception: {exc}")
                results[store] = []
    except (FuturesTimeoutError, TimeoutError):
        # Don't hang the request: keep partial results and abandon stragglers.
        for future, store in future_to_store.items():
            if future.done() and not future.cancelled() and not results[store]:
                try:
                    results[store] = future.result(timeout=0) or []
                except Exception:
                    results[store] = []
        print(f"[SCRAPER RUNNER] Timed out after {timeout_seconds}s; using partial/local data")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return results
