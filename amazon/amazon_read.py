from bs4 import BeautifulSoup
import pandas as pd


filename=r"amazon/htmls/amazon_data.html"
with open(filename,"r",encoding="utf-8") as f:
    r=f.read()
    soup=BeautifulSoup(r,"html.parser")

price=[]
name=[]

price_soup=soup.find_all(class_="a-price-whole")
price=[p.text for p in price_soup]

name_soup=soup.find_all(class_="a-section a-spacing-small puis-padding-left-small puis-padding-right-small")

for n in name_soup:
    P_name=n.find("h2",class_='a-text-normal').text
    if n.find("span",class_='a-size-base-plus a-color-base'):
        name.append(f"{n.find("span",class_='a-size-base-plus a-color-base').text}-{P_name}")
    else:
        name.append(f"-{P_name}")

data={"Product name":name,"Price":price}
df=pd.DataFrame(data)
df.to_csv(r"amazon\amazon_data.csv")