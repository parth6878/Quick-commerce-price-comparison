"""
Real product-photo scrapers for the three quick-commerce sites.

  * Amazon  : plain HTTP + BeautifulSoup (search HTML ships with <img class="s-image">)
  * Blinkit : headless Chrome (search page is a JS shell), card-walk pairs
              product name -> price -> cdn.grofers.com photo
  * Zepto   : headless Chrome; solves the location gate first (products only
              render after a locality is chosen), then parses product cards

Every scraper returns a list of candidates:
    [{"name": str, "price": str|None, "image_url": str, "image_urls": [alt urls]}]

Callers push them through services.image_store.ingest_candidates() which
downloads, resizes and indexes them locally (static/img).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PRICE_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _price_from(text: str) -> Optional[str]:
    m = PRICE_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _chrome_options():
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=en-IN")
    opts.add_argument(f"user-agent={USER_AGENT}")
    return opts


def _new_driver(page_load_timeout: int = 35):
    from selenium import webdriver

    driver = webdriver.Chrome(options=_chrome_options())
    driver.set_page_load_timeout(page_load_timeout)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
        )
    except Exception:
        pass
    return driver


def _quit(driver) -> None:
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass


_JUNK_NAME_PARTS = (
    "showing results", "results for", "no products", "search results",
    "min delivery", "sort by", "filter",
)


def _bad_name(name: str) -> bool:
    """Reject headers/ads/labels scraped alongside real product titles."""
    lowered = (name or "").strip().lower()
    if len(lowered) < 5:
        return True
    if '"' in lowered or "₹" in lowered:
        return True
    return any(junk in lowered for junk in _JUNK_NAME_PARTS)


def _img_src(img) -> str:
    """http src from src/data-src/srcset (lazy-loaded cards use any of them)."""
    src = (img.get("src") or img.get("data-src") or "").strip()
    if src.startswith("http"):
        return src
    for part in (img.get("srcset") or "").split(","):
        candidate = part.strip().split(" ")[0]
        if candidate.startswith("http"):
            return candidate
    return ""


def _climb_for_product(node, img_predicate, levels: int = 6):
    """
    Walk up from a name/price element until we reach the card that also
    contains a product image. Returns (img_src, card_text) or (None, None).
    """
    current = node
    for _ in range(levels):
        current = current.parent
        if current is None:
            return None, None
        for img in current.find_all("img"):
            src = _img_src(img)
            if src and img_predicate(src):
                return src, current.get_text(" ", strip=True)
    return None, None


def _upgrade_grofers_url(url: str) -> str:
    """Blinkit CDN thumbnails ship w=90; ask the transform for a bigger crop."""
    return re.sub(r"w=\d+", "w=480", url)


def _amazon_full_size(url: str) -> List[str]:
    """Return [large_variant, original_url] - image_store tries them in order."""
    stripped = re.sub(r"\._[A-Z]{2}_[A-Za-z0-9_]+_\.", ".", url)
    stripped = re.sub(r"\._[A-Z]{2}\d{2,}_\.", ".", stripped)
    if stripped != url:
        return [stripped, url]
    return [url]


_JUNK = ("logo", "icon", "sprite", "banner", "placeholder", "not-found",
         "arrow", "favicon", "category", ".svg")


def _is_product_img(src: str) -> bool:
    lowered = src.lower()
    return not any(j in lowered for j in _JUNK)


# ---------------------------------------------------------------------------
# Amazon (fast path - plain HTTP)
# ---------------------------------------------------------------------------

def scrape_amazon_images(query: str, limit: int = 24) -> List[Dict[str, Any]]:
    """Parse Amazon search HTML for (title, photo) pairs. ~1-3 s, no browser."""
    url = f"https://www.amazon.in/s?k={quote_plus(query)}"
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        body = resp.text
        if "captcha" in body.lower() or body.count("Robot Check") > 0:
            return []
    except Exception as exc:
        print(f"[IMG AMAZON] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(body, "lxml")
    cards = soup.find_all("div", {"data-component-type": "s-search-result"})
    out: List[Dict[str, Any]] = []
    seen: set = set()

    def _push(title: str, src: str, price: Optional[str]) -> None:
        key = title.lower()
        if _bad_name(title) or key in seen:
            return
        seen.add(key)
        out.append({
            "name": title,
            "price": price,
            "image_url": src,
            "image_urls": _amazon_full_size(src),
        })

    for card in cards:
        img = card.find("img", class_="s-image")
        if img is None or not img.get("src"):
            continue
        heading = card.find("h2")
        title = (heading.get_text(" ", strip=True) if heading else "") or (img.get("alt") or "").strip()
        price_el = card.find(class_="a-price-whole")
        _push(title, img["src"], price_el.get_text(strip=True) if price_el else None)
        if len(out) >= limit:
            break

    # Layout-drift fallback: every s-image carries the full title in alt.
    if len(out) < limit:
        for img in soup.select("img.s-image"):
            src = img.get("src")
            if not src:
                continue
            alt = (img.get("alt") or "").strip()
            price = None
            try:
                holder = img.find_parent("div", {"data-component-type": "s-search-result"}) \
                    or img.find_parent(attrs={"class": re.compile(r"puis|search-result")})
                if holder:
                    price_el = holder.find(class_="a-price-whole")
                    price = price_el.get_text(strip=True) if price_el else None
            except Exception:
                pass
            _push(alt, src, price)
            if len(out) >= limit:
                break
    print(f"[IMG AMAZON] {query!r}: {len(out)} photos")
    return out


# ---------------------------------------------------------------------------
# Blinkit (headless Chrome)
# ---------------------------------------------------------------------------

def _parse_blinkit_soup(soup, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for name_el in soup.select(".tw-line-clamp-2"):
        name = name_el.get_text(" ", strip=True)
        if _bad_name(name) or name.lower() in seen:
            continue
        img_src, card_text = _climb_for_product(
            name_el, lambda s: "grofers" in s and _is_product_img(s)
        )
        if not img_src:
            continue
        seen.add(name.lower())
        out.append({
            "name": name,
            "price": _price_from(card_text or ""),
            "image_url": _upgrade_grofers_url(img_src),
        })
        if len(out) >= limit:
            break
    return out


def _blinkit_run(driver, query: str, limit: int) -> List[Dict[str, Any]]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        driver.get(f"https://blinkit.com/s/?q={quote_plus(query)}")
    except Exception:
        # Page-load timeout: the DOM keeps rendering; fall through to waits.
        pass
    try:
        WebDriverWait(driver, 18).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".tw-line-clamp-2"))
        )
    except Exception:
        pass
    try:
        driver.execute_script("window.scrollTo(0, 800);")
    except Exception:
        pass
    time.sleep(3)
    return _parse_blinkit_soup(BeautifulSoup(driver.page_source, "lxml"), limit)


def scrape_blinkit_images(query: str, limit: int = 24, timeout: int = 40) -> List[Dict[str, Any]]:
    """Headless-Chrome scrape of blinkit.com search results (single query)."""
    driver = None
    try:
        driver = _new_driver()
        out = _blinkit_run(driver, query, limit)
        print(f"[IMG BLINKIT] {query!r}: {len(out)} photos")
        return out
    except Exception as exc:
        print(f"[IMG BLINKIT] {query!r} failed: {exc}")
        return []
    finally:
        _quit(driver)


def scrape_blinkit_multi(queries: List[str], limit: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """Many queries through ONE browser (driver startup dominates per-query cost)."""
    results: Dict[str, List[Dict[str, Any]]] = {}
    driver = None
    try:
        driver = _new_driver()
        for query in queries:
            try:
                results[query] = _blinkit_run(driver, query, limit)
            except Exception as exc:
                print(f"[IMG BLINKIT] {query!r} failed: {exc}")
                results[query] = []
            print(f"[IMG BLINKIT] {query!r}: {len(results[query])} photos")
    finally:
        _quit(driver)
    return results


# ---------------------------------------------------------------------------
# Zepto (headless Chrome + location gate)
# ---------------------------------------------------------------------------

_ZEPTO_INPUT_SELECTORS = (
    "input[placeholder*='delivery' i]",
    "input[placeholder*='location' i]",
    "input[placeholder*='area' i]",
    "input[placeholder*='locality' i]",
    "input[placeholder*='ocal' i]",
    "input[placeholder*='pin' i]",
    "input[type='text']",
)

_ZEPTO_SUGGESTION_SELECTORS = (
    "[role='option']",
    "[data-slot-id*='uggestion' i]",
    "li[class*='result' i]",
    "ul li",
)


def _zepto_pick_location(driver, city: str = "Mumbai") -> bool:
    """Best-effort: type a city into the location gate and choose a suggestion."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    input_el = None
    for sel in _ZEPTO_INPUT_SELECTORS:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed() and el.is_enabled():
                    input_el = el
                    break
        except Exception:
            continue
        if input_el is not None:
            break
    if input_el is None:
        return False

    try:
        input_el.click()
        input_el.send_keys(Keys.CONTROL, "a")
        input_el.send_keys(Keys.DELETE)
        input_el.send_keys(city)
        time.sleep(2.5)

        for sel in _ZEPTO_SUGGESTION_SELECTORS:
            clicked = False
            try:
                items = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                continue
            for item in items:
                try:
                    if item.is_displayed() and item.text.strip():
                        item.click()
                        clicked = True
                        break
                except Exception:
                    continue
            if clicked:
                time.sleep(2.5)
                return True

        input_el.send_keys(Keys.ENTER)
        time.sleep(2.5)
        return True
    except Exception as exc:
        print(f"[IMG ZEPTO] location pick failed: {exc}")
        return False


def _parse_zepto_soup(soup, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set = set()

    name_els = soup.select("[data-slot-id='ProductName']")
    if name_els:
        for name_el in name_els:
            name = name_el.get_text(" ", strip=True)
            if _bad_name(name) or name.lower() in seen:
                continue
            img_src, card_text = _climb_for_product(name_el, _is_product_img)
            if not img_src:
                continue
            seen.add(name.lower())
            out.append({
                "name": name,
                "price": _price_from(card_text or ""),
                "image_url": img_src,
            })
            if len(out) >= limit:
                break
        return out

    # Layout drift fallback: walk up from every price text node.
    for text_node in soup.find_all(string=PRICE_RE):
        price = _price_from(str(text_node))
        img_src, card_text = _climb_for_product(text_node.parent, _is_product_img)
        if not img_src or not card_text or len(card_text) < 8:
            continue
        guess = PRICE_RE.sub("", card_text).strip()
        guess = re.sub(r"\b(ADD|BUY|OFF)\b", "", guess, flags=re.I).strip(" -|")
        if _bad_name(guess) or guess.lower() in seen:
            continue
        seen.add(guess.lower())
        out.append({"name": guess, "price": price, "image_url": img_src})
        if len(out) >= limit:
            break
    return out


def _zepto_run(driver, query: str, limit: int) -> List[Dict[str, Any]]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        driver.get(f"https://www.zeptonow.com/search?query={quote_plus(query)}")
    except Exception:
        pass
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-slot-id='ProductName'], [data-testid*='product' i]")
            )
        )
    except Exception:
        pass
    try:
        driver.execute_script("window.scrollTo(0, 800);")
    except Exception:
        pass
    time.sleep(3)
    return _parse_zepto_soup(BeautifulSoup(driver.page_source, "lxml"), limit)


def scrape_zepto_images(query: str, limit: int = 24, timeout: int = 45) -> List[Dict[str, Any]]:
    """
    Headless-Chrome scrape of Zepto search results.
    Zepto only renders products after a locality is chosen, so we walk:
      homepage -> location gate -> search page -> cards.
    """
    driver = None
    try:
        driver = _new_driver()

        # 1. Location gate (products are hidden until this succeeds)
        try:
            driver.get("https://www.zeptonow.com/")
        except Exception:
            pass
        time.sleep(3)
        _zepto_pick_location(driver)

        # 2. Search page
        out = _zepto_run(driver, query, limit)
        if not out:
            # Gate may have reappeared between pages - re-pick and retry once.
            _zepto_pick_location(driver)
            out = _zepto_run(driver, query, limit)

        print(f"[IMG ZEPTO] {query!r}: {len(out)} photos")
        return out
    except Exception as exc:
        print(f"[IMG ZEPTO] {query!r} failed: {exc}")
        return []
    finally:
        _quit(driver)


def scrape_zepto_multi(queries: List[str], limit: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """Many queries through ONE browser; location gate solved once up front."""
    results: Dict[str, List[Dict[str, Any]]] = {}
    driver = None
    try:
        driver = _new_driver()
        try:
            driver.get("https://www.zeptonow.com/")
        except Exception:
            pass
        time.sleep(3)
        location_ok = _zepto_pick_location(driver)

        for query in queries:
            try:
                out = _zepto_run(driver, query, limit)
                if not out and location_ok:
                    _zepto_pick_location(driver)  # gate drifted back mid-run
                    out = _zepto_run(driver, query, limit)
                results[query] = out
            except Exception as exc:
                print(f"[IMG ZEPTO] {query!r} failed: {exc}")
                results[query] = []
            print(f"[IMG ZEPTO] {query!r}: {len(results[query])} photos")
    finally:
        _quit(driver)
    return results


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------

def scrape_store_images(store_key: str, query: str, limit: int = 24) -> List[Dict[str, Any]]:
    """Dispatch to one store's photo scraper by store key."""
    if store_key == "amazon":
        return scrape_amazon_images(query, limit=limit)
    if store_key == "blinkit":
        return scrape_blinkit_images(query, limit=limit)
    if store_key == "zepto":
        return scrape_zepto_images(query, limit=limit)
    return []


def scrape_all_images(query: str, limit: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """
    Run all three photo scrapers. Amazon first (fast, HTTP-only), then the two
    browser-based stores sequentially so we never run 3 Chromes at once.
    """
    results: Dict[str, List[Dict[str, Any]]] = {}
    results["amazon"] = scrape_amazon_images(query, limit=limit)
    results["blinkit"] = scrape_blinkit_images(query, limit=limit)
    results["zepto"] = scrape_zepto_images(query, limit=limit)
    return results


if __name__ == "__main__":
    import json
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "milk"
    for store in ("amazon", "blinkit", "zepto"):
        found = scrape_store_images(store, q, limit=5)
        print(f"--- {store} ({len(found)}) ---")
        print(json.dumps(found[:3], indent=2, ensure_ascii=False))
