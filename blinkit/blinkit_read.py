from bs4 import BeautifulSoup
import re
import os 
import pandas as pd
from PIL import Image
import requests

def blinkit_read():
    names=[]
    price=[]
    quantity=[]
    filename = os.path.join(os.path.dirname(__file__), "htmls", "blinkit_data.html")
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as f:
        r = f.read()
        soup = BeautifulSoup(r, "html.parser")

    classes = soup.find_all(class_="tw-line-clamp-2")
    names = [c.get_text(strip=True) for c in classes]

    prices = soup.find_all(class_="tw-text-200", string=re.compile(r"^₹"))
    price = [p.get_text(strip=True) for p in prices]

    pattern = re.compile(r"^\d+")
    quantitys = soup.find_all(class_="tw-text-200")
    quantity = [q.get_text(strip=True) for q in quantitys if pattern.match(q.get_text(strip=True))]

    count = min(len(names), len(price)) if price else len(names)
    names = names[:count]
    price = price[:count]
    quantity = quantity[:count] if len(quantity) >= count else quantity + [""] * (count - len(quantity))

    data = {"B_Product_name": names, "B_Price": price, "B_Quantity": quantity}
    df = pd.DataFrame(data)
    out_csv = os.path.join(os.path.dirname(__file__), "blinkit_data.csv")
    df.to_csv(out_csv, index=False)
    

