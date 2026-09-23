import os
import re
import time
import pandas as pd
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def scrape_amazon(query: str, timeout: int = 15) -> List[Dict[str, Any]]:
    """
    Scrape Amazon Fresh for search query using headless Chrome.
    Returns structured list of product dicts.
    """
    url = f"https://www.amazon.in/s?k={query}&i=nowstore"
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
        time.sleep(4)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(4)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Each result card
        cards = soup.find_all("div", {"data-component-type": "s-search-result"})
        if not cards:
            cards = soup.find_all(class_="a-section a-spacing-small puis-padding-left-small puis-padding-right-small")

        for card in cards:
            # 1. Product title
            title_elem = card.find("h2")
            if not title_elem:
                continue
            title = title_elem.get_text(" ", strip=True)

            # Check if brand prefix is present
            brand_elem = card.find("span", class_="a-size-base-plus a-color-base")
            if brand_elem:
                b_text = brand_elem.get_text(strip=True)
                if b_text and not title.lower().startswith(b_text.lower()):
                    title = f"{b_text} {title}"

            # 2. Price
            price_elem = card.find(class_="a-price-whole")
            price = price_elem.get_text(strip=True) if price_elem else None

            # 3. Image
            img_elem = card.find("img", class_="s-image")
            image_url = img_elem.get("src") if img_elem else ""

            # 4. Quantity: extract from title
            qty_pattern = re.compile(r"\d+\.?\d*\s*(?:grams?|litres?|liters?|kgs?|kg|ml|l|g)\b", re.IGNORECASE)
            clean_title_text = re.sub(r"\s+", " ", title).strip()
            qty_match = qty_pattern.search(clean_title_text)
            quantity = qty_match.group() if qty_match else ""

            if title:
                products.append({
                    "store": "Amazon",
                    "name": clean_title_text,
                    "price": price,
                    "quantity": quantity,
                    "image_url": image_url
                })

    except Exception as e:
        print(f"[Amazon Scraper Error]: {e}")
        # Fallback to local CSV ONLY if user specifically queried milk/demo and live scraping failed
        is_milk_query = any(k in query.lower() for k in ["milk", "demo", "amul"])
        csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "amazon", "amazon_data.csv")
        if is_milk_query and os.path.exists(csv_path) and not products:
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    name_val = str(row.get("A_Product_name", "")).replace("\n", " ").strip()
                    products.append({
                        "store": "Amazon",
                        "name": re.sub(r"\s+", " ", name_val),
                        "price": row.get("A_Price"),
                        "quantity": row.get("A_Quantity", ""),
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
