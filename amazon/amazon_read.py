from bs4 import BeautifulSoup
import pandas as pd
import re

import os

filename = os.path.join(os.path.dirname(__file__), "htmls", "amazon_data.html")

def amazon_read():
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as f:
        r = f.read()
        soup = BeautifulSoup(r, "html.parser")

    price = []
    name = []

    price_soup = soup.find_all(class_="a-price-whole")
    price = [p.text.strip() for p in price_soup]

    name_soup = soup.find_all(class_="a-section a-spacing-small puis-padding-left-small puis-padding-right-small")

    for n in name_soup:
        h2 = n.find("h2", class_='a-text-normal')
        if not h2:
            continue
        P_name = h2.text.strip()
        brand_span = n.find("span", class_='a-size-base-plus a-color-base')
        if brand_span:
            name.append(f"{brand_span.text.strip()}-{P_name}")
        else:
            name.append(P_name)

    qty_pattern = re.compile(r"\d+\.?\d*\s*(?:grams?|litres?|liters?|kgs?|kg|ml|l|g)\b", re.IGNORECASE)

    quantity = []
    for n in name:
        clean_n = re.sub(r"\s+", " ", n).strip()
        match = qty_pattern.search(clean_n)
        quantity.append(match.group() if match else "")

    # Align lengths safely
    count = min(len(name), len(price)) if price else len(name)
    name = name[:count]
    price = price[:count]
    quantity = quantity[:count]

    data = {"A_Product_name": name, "A_Price": price, "A_Quantity": quantity}
    df = pd.DataFrame(data)
    out_csv = os.path.join(os.path.dirname(__file__), "amazon_data.csv")
    df.to_csv(out_csv, index=False)
#     print(len(quantity))
#     print(len(price))
#     print(len(name))
# amazon_read()