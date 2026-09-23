import os
import time
import pandas as pd
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def scrape_zepto(query: str, timeout: int = 15) -> List[Dict[str, Any]]:
    """
    Scrape Zepto for search query using headless Chrome.
    Returns structured list of product dicts.
    """
    url = f"https://www.zepto.com/search?query={query}"
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

        # In Zepto, cards often contain data-slot-id elements or specific classes
        name_tags = soup.select("[data-slot-id='ProductName']")
        names = [n.get_text(" ", strip=True) for n in name_tags]

        price_tags = soup.find_all(class_="cptQT7") or soup.select("[data-testid='product-card-price']")
        prices = [p.get_text(strip=True) for p in price_tags]

        qty_tags = soup.select("[data-slot-id='PackSize']")
        quantities = [q.get_text(strip=True) for q in qty_tags]

        # Extract images
        img_tags = soup.select("[data-slot-id='ProductImage'] img, img[alt]")
        img_urls = [img.get("src") for img in img_tags if img.get("src")]

        limit = min(len(names), len(prices)) if prices else len(names)
        for i in range(limit):
            products.append({
                "store": "Zepto",
                "name": names[i],
                "price": prices[i] if i < len(prices) else None,
                "quantity": quantities[i] if i < len(quantities) else "",
                "image_url": img_urls[i] if i < len(img_urls) else ""
            })

    except Exception as e:
        print(f"[Zepto Scraper Error]: {e}")
        # Fallback to local CSV ONLY if user specifically queried milk/demo and live scraping failed
        is_milk_query = any(k in query.lower() for k in ["milk", "demo", "amul"])
        csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "zepto", "zepto_data.csv")
        if is_milk_query and os.path.exists(csv_path) and not products:
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    products.append({
                        "store": "Zepto",
                        "name": row.get("Z_Product_name", ""),
                        "price": row.get("Z_Price"),
                        "quantity": row.get("Z_Quantity", ""),
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
