import time
import os
import hashlib
import html
import threading
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from services.matcher import cluster_products, analyze_query, is_relevant_to_query
from services.catalog import get_local_items, get_query_terms, synthesize_items
from services.scrapers.runner import run_all_scrapers
from services import image_store

# Initialize FastAPI application
app = FastAPI(
    title="Quick Commerce Price Comparison API",
    description="Compare prices across Blinkit, Zepto, and Amazon Fresh with normalized matching and best-deal finder.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static web application assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.middleware("http")
async def never_cache_dev_assets(request: Request, call_next):
    """
    Dev-friendly caching: HTML and static assets are always revalidated so a
    redesign is visible on a normal refresh (no Ctrl+Shift+R needed).
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path in ("/", "/app"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

# Simple In-Memory Cache: query -> {"data": ..., "timestamp": ...}
CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes


class StoreDetail(BaseModel):
    raw_name: str
    price: Optional[float] = None
    quantity: Optional[str] = ""
    unit_price: Optional[float] = None
    image_url: Optional[str] = ""


class MatchedDeal(BaseModel):
    canonical_name: str
    brand: Optional[str] = ""
    quantity: Optional[str] = ""
    prices: Dict[str, float]
    images: Dict[str, str] = {}
    representative_image: Optional[str] = ""
    lowest_price: float
    highest_price: float
    savings: float
    savings_percentage: float
    cheapest_store: str
    cheapest_stores: List[str]
    store_count: int
    store_details: Dict[str, StoreDetail]


class ComparisonSummary(BaseModel):
    total_matched: int
    total_single_store: int
    total_products: int


class ComparisonResponse(BaseModel):
    query: str
    cached: bool
    matched_deals: List[MatchedDeal]
    single_store_items: List[Dict[str, Any]]
    summary: ComparisonSummary


@app.get("/")
def root(request: Request):
    """
    Serves the QuickCompare web application to web browsers, 
    and API endpoints directory to programmatic API clients.
    """
    accept = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "")
    
    is_browser = "text/html" in accept or "Mozilla" in user_agent or "Chrome" in user_agent
    if is_browser and "application/json" not in accept:
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

    return {
        "name": "Quick Commerce Price Comparison API",
        "version": "1.0.0",
        "endpoints": {
            "web": "/app",
            "compare": "/api/compare?query={query}",
            "demo": "/api/demo",
            "health": "/api/health",
            "image": "/api/image?name={product}",
            "image_stats": "/api/images/stats",
            "image_seed": "POST /api/images/seed?query={query}",
            "docs": "/docs"
        }
    }


@app.get("/app")
def web_app():
    """Direct route to the QuickCompare web application UI."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend web app index.html not found"}


@app.get("/api/info")
def api_info():
    """API metadata and endpoints directory."""
    return {
        "name": "Quick Commerce Price Comparison API",
        "version": "1.0.0",
        "endpoints": {
            "compare": "/api/compare?query={query}",
            "demo": "/api/demo",
            "health": "/api/health",
            "image": "/api/image?name={product}",
            "image_stats": "/api/images/stats",
            "image_seed": "POST /api/images/seed?query={query}",
            "docs": "/docs"
        }
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok", "cached_queries": list(CACHE.keys()), "images": image_store.stats()}


@app.get("/health")
def health_alias():
    """Alias for monitors/stale tabs that poll /health instead of /api/health."""
    return health_check()


@app.get("/api/image")
def product_image(
    name: str = Query(..., min_length=1, description="Product title used to generate the artwork"),
    store: str = Query("", description="Optional store label rendered on the tile")
):
    """
    Generated product artwork (SVG) used wherever we don't have a real photo.
    Deterministic: the same product always gets the same tile.
    """
    svg = _product_svg(name[:120], store[:40])
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/images/stats")
def images_stats():
    """How many real product photos we've scraped and indexed so far."""
    return {"status": "ok", **image_store.stats()}


@app.post("/api/images/seed")
def seed_images_endpoint(
    query: str = Query(..., min_length=2, description="Query to scrape photos for"),
    stores: str = Query("amazon,blinkit,zepto", description="Comma-separated store keys"),
):
    """
    Queue a background photo scrape from the quick-commerce sites.
    Returns immediately; photos land in static/img and cached responses for
    this query are dropped when the scrape finishes, so the next search
    renders the real product pictures.
    """
    norm_query = query.strip().lower()
    wanted = [s.strip().lower() for s in stores.split(",") if s.strip()]
    allowed = [s for s in wanted if s in _STORE_KEY_TO_LABEL]
    if not allowed:
        return {"status": "error", "detail": f"no valid stores in {stores!r}"}

    with _SEED_LOCK:
        _SEED_ATTEMPTED[norm_query] = time.time()
    _spawn(_background_seed_stores, norm_query, allowed)
    return {"status": "queued", "query": norm_query, "stores": allowed}


STORE_KEYS = ("blinkit", "zepto", "amazon")


def _build_instant_items(norm_query: str) -> Dict[str, List[Dict[str, Any]]]:
    """Scraper-free dataset lookup (bundled catalog + CSVs) for any query."""
    items = get_local_items(norm_query)
    return {key: items.get(key, []) for key in STORE_KEYS}


# ---------------------------------------------------------------------------
# Product imagery: every row gets a picture, real (scraped) or generated
# ---------------------------------------------------------------------------
_EMOJI_RULES = (
    (("milk", "dairy", "curd", "paneer", "yogurt", "cheese", "butter", "cream"), "\U0001F95B"),
    (("bread", "bakery", "pav", "bun", "loaf"), "\U0001F35E"),
    (("coke", "coca", "pepsi", "sprite", "thums", "soda", "soft drink", "cold drink", "can of"), "\U0001F964"),
    (("atta", "flour", "wheat", "chakki"), "\U0001F33E"),
    (("oil", "sunflower", "mustard", "saffola", "fortune oil"), "\U0001FAD0"),
    (("chips", "crisps", "kurkure", "doritos", "pringles", "namkeen", "snack"), "\U0001F954"),
    (("soap", "bathing", "handwash", "body wash"), "\U0001F9FC"),
    (("toothpaste", "colgate", "sensodyne", "close up", "teeth"), "\U0001FAA5"),
    (("coffee", "nescafe", "bru ", "espresso", "cappuccino"), "☕"),
    (("tea", "tulsi", "green tea"), "\U0001F375"),
    (("egg",), "\U0001F95A"),
    (("rice",), "\U0001F35A"),
    (("sugar", "salt", "spice", "masala"), "\U0001F9C2"),
    (("biscuit", "cookie"), "\U0001F36A"),
    (("chocolate", "cadbury", "kitkat", "oreo"), "\U0001F36B"),
    (("juice", "water", "mango", "frooti"), "\U0001F9C3"),
    (("noodle", "maggi", "pasta", "instant food"), "\U0001F35C"),
    (("fruit", "apple", "banana", "orange"), "\U0001F34E"),
    (("vegetable", "tomato", "onion", "potato", "greens"), "\U0001F96C"),
    (("detergent", "surf", "ariel", "cleaning", "floor"), "\U0001F9F9"),
)

_SKIP_INITIAL_WORDS = {"the", "a", "an", "of", "and", "with", "for", "pack", "pure"}


def _category_emoji(name: str) -> str:
    lowered = name.lower()
    for keywords, emoji in _EMOJI_RULES:
        for keyword in keywords:
            if keyword in lowered:
                return emoji
    return "\U0001F6D2"


def _initials(name: str, limit: int = 2) -> str:
    words = [w for w in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in name).split()
             if w and w.lower() not in _SKIP_INITIAL_WORDS]
    return "".join(w[0] for w in words[:limit]).upper() or "QC"


def _wrap_text(name: str, max_chars: int = 24, max_lines: int = 3) -> List[str]:
    words = str(name).split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and words and " ".join(words) != " ".join(lines):
        lines[-1] = lines[-1].rstrip(".…") + "…"
    return lines or ["Product"]


def product_image_url(name: str, store: str = "") -> str:
    """Relative URL of the generated product artwork."""
    return f"/api/image?name={quote_plus(str(name or 'Product'))}&store={quote_plus(str(store or ''))}"


def _with_images(items: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    """
    Guarantee every item carries a REAL product photo whenever one exists.

    Resolution order:
      1. locally scraped photo for this store + product (static/img, fastest,
         immune to CDN hot-link blocks)
      2. the item's own remote image_url (fresh live scrape / bundled URL)
      3. the same product's photo scraped from ANOTHER store
      4. anything we scraped while searching for this query
      5. generated SVG artwork (genuinely unknown product only)
    """
    enriched = []
    for item in items:
        item = dict(item)
        name = str(item.get("name") or "")
        store = str(item.get("store") or "")
        remote = str(item.get("image_url") or "").strip()

        photo = image_store.lookup(store, name)
        if not photo and remote.startswith("http"):
            photo = remote
        if not photo:
            photo = image_store.lookup_any(name)
        if not photo and query:
            photo = image_store.lookup_query(query, name)

        item["image_url"] = photo or product_image_url(name, store)
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Lazy photo enrichment: unknown queries trigger a background scrape so the
# NEXT search for that query shows real photos instead of generated art.
# ---------------------------------------------------------------------------
_SEED_LOCK = threading.Lock()
_SEED_ATTEMPTED: Dict[str, float] = {}
AUTOSEED_COOLDOWN_SECONDS = 600  # one attempt per query per 10 minutes
AUTOSEED_MIN_MISSING = 2         # only bother when several rows lack photos

_STORE_KEY_TO_LABEL = {"amazon": "Amazon", "blinkit": "Blinkit", "zepto": "Zepto"}


def _invalidate_query_cache(norm_query: str) -> None:
    """Drop cached responses so the next request re-renders with new photos."""
    for key in list(CACHE):
        if key == norm_query or key.endswith("::" + norm_query):
            CACHE.pop(key, None)


def _background_autoseed(norm_query: str) -> None:
    """Fast path: Amazon photos over plain HTTP (no browser, ~2-4 s)."""
    try:
        from services.image_scraper import scrape_amazon_images

        candidates = scrape_amazon_images(norm_query, limit=20)
        stored = image_store.ingest_candidates("Amazon", candidates, query=norm_query, cap=20) \
            if candidates else 0
        if stored:
            _invalidate_query_cache(norm_query)
        print(f"[AUTO IMAGE SEED] {norm_query!r}: stored {stored} photo(s)")
    except Exception as exc:
        print(f"[AUTO IMAGE SEED] {norm_query!r} failed: {exc}")


def _background_seed_stores(norm_query: str, store_keys: List[str]) -> None:
    """Full path: scrape photos for every requested store, then refresh cache."""
    from services.image_scraper import scrape_store_images

    for key in store_keys:
        label = _STORE_KEY_TO_LABEL.get(key, key)
        try:
            candidates = scrape_store_images(key, norm_query, limit=24)
            stored = image_store.ingest_candidates(label, candidates, query=norm_query, cap=24) \
                if candidates else 0
            print(f"[IMAGE SEED] {norm_query!r} @ {label}: stored {stored} photo(s)")
        except Exception as exc:
            print(f"[IMAGE SEED] {norm_query!r} @ {label} failed: {exc}")
    _invalidate_query_cache(norm_query)


def _spawn(target, *args) -> bool:
    """Fire-and-forget daemon thread (never blocks the request path)."""
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return True


def _maybe_autoseed_images(norm_query: str, items: Dict[str, List[Dict[str, Any]]]) -> None:
    """Kick off a background Amazon photo scrape when rows fell back to SVG art."""
    if not norm_query or os.environ.get("QC_AUTO_IMAGE_SEED", "1") == "0":
        return
    missing = sum(
        1
        for rows in items.values()
        for item in rows
        if str(item.get("image_url") or "").startswith("/api/image?")
    )
    if missing < AUTOSEED_MIN_MISSING:
        return
    now = time.time()
    with _SEED_LOCK:
        last = _SEED_ATTEMPTED.get(norm_query, 0.0)
        if now - last < AUTOSEED_COOLDOWN_SECONDS:
            return
        _SEED_ATTEMPTED[norm_query] = now
    _spawn(_background_autoseed, norm_query)


def _product_svg(name: str, store: str) -> str:
    """Render a deterministic, good-looking product tile as SVG."""
    safe_name = (name or "Product").strip()
    seed = hashlib.md5(safe_name.lower().encode("utf-8")).hexdigest()
    hue_a = int(seed[0:4], 16) % 360
    hue_b = (hue_a + 30 + int(seed[4:6], 16) % 45) % 360
    emoji = _category_emoji(safe_name)
    initials = _initials(safe_name)
    lines = _wrap_text(safe_name)
    esc = lambda value: html.escape(str(value), quote=True)

    line_svg = []
    for index, line in enumerate(lines):
        y = 268 + index * 34
        line_svg.append(
            f'<text x="200" y="{y}" font-size="24" font-weight="600" fill="#ffffff" '
            f'text-anchor="middle" opacity="0.96">{esc(line)}</text>'
        )

    store_svg = ""
    if store:
        store_svg = (
            f'<text x="200" y="372" font-size="17" font-weight="700" fill="#ffffff" '
            f'text-anchor="middle" opacity="0.72" letter-spacing="2">{esc(store.upper())}</text>'
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400" '
        f'role="img" aria-label="{esc(safe_name)}">'
        "<defs>"
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="hsl({hue_a},72%,46%)"/>'
        f'<stop offset="100%" stop-color="hsl({hue_b},70%,26%)"/>'
        "</linearGradient>"
        '<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.22"/>'
        '<stop offset="55%" stop-color="#ffffff" stop-opacity="0"/>'
        "</linearGradient>"
        "</defs>"
        '<rect width="400" height="400" rx="30" fill="url(#bg)"/>'
        '<rect width="400" height="400" rx="30" fill="url(#shine)"/>'
        '<circle cx="332" cy="66" r="86" fill="#ffffff" opacity="0.10"/>'
        '<circle cx="54" cy="342" r="74" fill="#ffffff" opacity="0.07"/>'
        '<rect x="22" y="22" width="62" height="40" rx="13" fill="#000000" opacity="0.28"/>'
        f'<text x="53" y="49" font-size="19" font-weight="800" fill="#ffffff" text-anchor="middle">{esc(initials)}</text>'
        f'<text x="200" y="186" font-size="104" text-anchor="middle">{emoji}</text>'
        + "".join(line_svg)
        + store_svg
        + "</svg>"
    )


def _run_comparison(items: Dict[str, List[Dict[str, Any]]], norm_query: str) -> Dict[str, Any]:
    """
    Cluster items across the 3 stores for a query.
    Guarantees a non-empty answer: falls back to synthesized rows if the
    dataset has nothing relevant (e.g. a brand we don't carry).
    """
    items = {key: _with_images(value, norm_query) for key, value in items.items()}
    _maybe_autoseed_images(norm_query, items)
    extra_terms = get_query_terms(norm_query)
    comparison = cluster_products(
        items["blinkit"], items["zepto"], items["amazon"],
        query=norm_query,
        extra_terms=extra_terms
    )
    if comparison["summary"]["total_products"] == 0:
        fallback = {key: _with_images(value, norm_query) for key, value in synthesize_items(norm_query).items()}
        comparison = cluster_products(
            fallback["blinkit"], fallback["zepto"], fallback["amazon"],
            query=norm_query,
            extra_terms=extra_terms
        )
        if comparison["summary"]["total_products"] == 0:
            # Last resort: cluster the synthesized rows without query filtering.
            comparison = cluster_products(
                fallback["blinkit"], fallback["zepto"], fallback["amazon"]
            )
    return comparison


@app.get("/api/demo", response_model=ComparisonResponse)
def demo_comparison(
    query: str = Query("milk", description="Query answered instantly from the bundled dataset")
):
    """
    Instantly returns comparison results using the bundled dataset.
    Ideal for frontend UI testing and demonstration without waiting for scrapers.
    """
    norm_query = (query or "milk").strip().lower()
    cache_key = f"__demo_dataset__::{norm_query}"
    if cache_key in CACHE and (time.time() - CACHE[cache_key]["timestamp"]) < CACHE_TTL_SECONDS:
        cached_result = CACHE[cache_key]["data"]
        return ComparisonResponse(query=f"demo ({norm_query})", cached=True, **cached_result)

    result = _run_comparison(_build_instant_items(norm_query), norm_query)
    CACHE[cache_key] = {"data": result, "timestamp": time.time()}

    return ComparisonResponse(query=f"demo ({norm_query})", cached=False, **result)


@app.get("/api/compare", response_model=ComparisonResponse)
def compare_prices(
    query: str = Query(..., min_length=2, description="Search term, e.g. 'milk', 'bread'"),
    refresh: bool = Query(False, description="Force fresh compute and bypass cache"),
):
    """
    Search and compare prices across Blinkit, Zepto, and Amazon Fresh.
    Always fetches live from the real sites via the scraper pipeline;
    the bundled dataset is the per-store fallback when a scraper fails
    or returns nothing, so a search never comes back empty.
    """
    norm_query = query.strip().lower()
    extra_terms = get_query_terms(norm_query)
    cache_key = f"live::{norm_query}"

    # Check cache
    if not refresh and cache_key in CACHE:
        cached_entry = CACHE[cache_key]
        if (time.time() - cached_entry["timestamp"]) < CACHE_TTL_SECONDS:
            return ComparisonResponse(query=query, cached=True, **cached_entry["data"])

    items = _build_instant_items(norm_query)

    # 1. Run the scrapers and prefer fresh, relevant rows per store
    try:
        scraped_results = run_all_scrapers(norm_query)
    except Exception as e:
        print(f"[COMPARE] Scraper pipeline error (using local dataset): {e}")
        scraped_results = {}

    query_info = analyze_query(norm_query, extra_terms)
    for store_key in STORE_KEYS:
        live_items = [
            item for item in (scraped_results.get(store_key) or [])
            if item.get("name") and is_relevant_to_query(str(item["name"]), query_info)
        ]
        if live_items:
            items[store_key] = live_items

    # 2. Cluster & match products across the 3 stores with query intent
    comparison = _run_comparison(items, norm_query)

    # 3. Cache result
    CACHE[cache_key] = {
        "data": comparison,
        "timestamp": time.time()
    }

    return ComparisonResponse(
        query=query,
        cached=False,
        **comparison
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
