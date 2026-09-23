import os
import re
import time
import pandas as pd
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def scrape_blinkit(query: str, timeout: int = 15) -> List[Dict[str, Any]]:
    """
    Scrape Blinkit for search query using headless Chrome.
    Returns structured list of product dicts.
    """
    url = f"https://blinkit.com/s/?q={query}"
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = None
    products = []
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Extract names, prices, and quantities
        name_tags = soup.find_all(class_="tw-line-clamp-2")
        names = [t.get_text(strip=True) for t in name_tags]

        price_tags = soup.find_all(class_="tw-text-200", string=re.compile(r"^₹"))
        prices = [p.get_text(strip=True) for p in price_tags]

        qty_pattern = re.compile(r"^\d+")
        qty_candidates = soup.find_all(class_="tw-text-200")
        quantities = [q.get_text(strip=True) for q in qty_candidates if qty_pattern.match(q.get_text(strip=True))]

        # Extract image URLs
        img_tags = soup.select(".tw-h-full.tw-w-full.tw-transition-opacity.tw-opacity-100, img[alt]")
        img_urls = [img.get("src") for img in img_tags if img.get("src")]

        # Pair up data safely
        limit = min(len(names), len(prices)) if prices else len(names)
        for i in range(limit):
            products.append({
                "store": "Blinkit",
                "name": names[i],
                "price": prices[i] if i < len(prices) else None,
                "quantity": quantities[i] if i < len(quantities) else "",
                "image_url": img_urls[i] if i < len(img_urls) else ""
            })

    except Exception as e:
        print(f"[Blinkit Scraper Error]: {e}")
        # Fallback to local CSV ONLY if user specifically queried milk/demo and live scraping failed
        is_milk_query = any(k in query.lower() for k in ["milk", "demo", "amul"])
        csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "blinkit", "blinkit_data.csv")
        if is_milk_query and os.path.exists(csv_path) and not products:
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    products.append({
                        "store": "Blinkit",
                        "name": row.get("B_Product_name", ""),
                        "price": row.get("B_Price"),
                        "quantity": row.get("B_Quantity", ""),
                        "image_url": ""
                    })
            except Exception:
                pass
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return products
