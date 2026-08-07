from bs4 import BeautifulSoup
import pandas as pd
import re

filename=r"amazon/htmls/amazon_data.html"
with open(filename,"r",encoding="utf-8") as f:
    r=f.read()
    soup=BeautifulSoup(r,"html.parser")
def amazon_read():
    price=[]
    name=[]

    price_soup=soup.find_all(class_="a-price-whole")
    price=[p.text for p in price_soup]

    name_soup=soup.find_all(class_="a-section a-spacing-small puis-padding-left-small puis-padding-right-small")

    for n in name_soup:
        P_name=n.find("h2",class_='a-text-normal').text
        if n.find(("span"),class_='a-size-base-plus a-color-base'):
            name.append(f"{n.find('span',class_='a-size-base-plus a-color-base').text}-{P_name}")
        else:
            name.append(f"-{P_name}")

    qty_pattern = re.compile(r"\d+\.?\d*\s*(?:grams?|litres?|liters?|kgs?|kg|ml|l|g)\b", re.IGNORECASE)

    quantity = []
    for n in name:
        clean_n = re.sub(r"\s+", " ", n).strip()   # collapse whitespace/newlines first
        match = qty_pattern.search(clean_n)
        quantity.append(match.group() if match else None)

    data={"Product name":name,"Price":price,"Quantity":quantity}
    df=pd.DataFrame(data)
    df.to_csv(r"amazon\amazon_data.csv")
