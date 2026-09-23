from bs4 import BeautifulSoup
import pandas as pd


import os

def read_zepto():
    names = []
    prices = []
    quantities = []

    filename = os.path.join(os.path.dirname(__file__), "htmls", "zepto_data.html")
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as f:
        r = f.read()
        soup = BeautifulSoup(r, "html.parser")

    names_soup = soup.select("[data-slot-id='ProductName']")
    names = [name.get_text(" ", strip=True) for name in names_soup]

    prices_soup = soup.find_all(class_="cptQT7")
    prices = [price.text.strip() for price in prices_soup]

    quantity_soup = soup.select("[data-slot-id='PackSize']")
    quantities = [quantity.text.strip() for quantity in quantity_soup]

    count = min(len(names), len(prices)) if prices else len(names)
    names = names[:count]
    prices = prices[:count]
    quantities = quantities[:count] if len(quantities) >= count else quantities + [""] * (count - len(quantities))

    data = {"Z_Product_name": names, "Z_Price": prices, "Z_Quantity": quantities}
    df = pd.DataFrame(data)
    out_csv = os.path.join(os.path.dirname(__file__), "zepto_data.csv")
    df.to_csv(out_csv, index=False)
