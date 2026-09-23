import time
import os
import pandas as pd
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.matcher import cluster_products
from services.scrapers.runner import run_all_scrapers

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
            "docs": "/docs"
        }
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok", "cached_queries": list(CACHE.keys())}


@app.get("/api/demo", response_model=ComparisonResponse)
def demo_comparison():
    """
    Instantly returns comparison results using the bundled dataset.
    Ideal for frontend UI testing and demonstration without waiting for scrapers.
    """
    cache_key = "__demo_dataset__"
    if cache_key in CACHE and (time.time() - CACHE[cache_key]["timestamp"]) < CACHE_TTL_SECONDS:
        cached_result = CACHE[cache_key]["data"]
        return ComparisonResponse(query="demo (milk)", cached=True, **cached_result)

    b_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "blinkit", "blinkit_data.csv"))
    z_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "zepto", "zepto_data.csv"))
    a_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "amazon", "amazon_data.csv"))

    b_items = [
        {"store": "Blinkit", "name": row["B_Product_name"], "price": row["B_Price"], "quantity": row["B_Quantity"]}
        for _, row in b_df.iterrows()
    ]
    z_items = [
        {"store": "Zepto", "name": row["Z_Product_name"], "price": row["Z_Price"], "quantity": row["Z_Quantity"]}
        for _, row in z_df.iterrows()
    ]
    a_items = [
        {"store": "Amazon", "name": row["A_Product_name"], "price": row["A_Price"], "quantity": row["A_Quantity"]}
        for _, row in a_df.iterrows()
    ]

    result = cluster_products(b_items, z_items, a_items, query="milk")
    CACHE[cache_key] = {"data": result, "timestamp": time.time()}

    return ComparisonResponse(query="demo (milk)", cached=False, **result)


@app.get("/api/compare", response_model=ComparisonResponse)
def compare_prices(
    query: str = Query(..., min_length=2, description="Search term, e.g. 'milk', 'bread'"),
    refresh: bool = Query(False, description="Force fresh scrape and bypass cache")
):
    """
    Search and compare prices across Blinkit, Zepto, and Amazon Fresh.
    """
    norm_query = query.strip().lower()

    # Check cache
    if not refresh and norm_query in CACHE:
        cached_entry = CACHE[norm_query]
        if (time.time() - cached_entry["timestamp"]) < CACHE_TTL_SECONDS:
            return ComparisonResponse(query=query, cached=True, **cached_entry["data"])

    # 1. Run scrapers concurrently
    try:
        scraped_results = run_all_scrapers(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper pipeline error: {str(e)}")

    blinkit_items = scraped_results.get("blinkit", [])
    zepto_items = scraped_results.get("zepto", [])
    amazon_items = scraped_results.get("amazon", [])

    # 2. Cluster & match products across the 3 stores with query intent
    comparison = cluster_products(blinkit_items, zepto_items, amazon_items, query=norm_query)

    # 3. Cache result
    CACHE[norm_query] = {
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
