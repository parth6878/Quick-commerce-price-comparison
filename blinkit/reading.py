from bs4 import BeautifulSoup
import re
import os 
import pandas as pd
from PIL import Image
import requests
os.chdir("quick_commerce/blinkit")


names=[]
price=[]
quantity=[]
image=[]


with open(r"htmls\data.html","r",encoding="utf-8") as f:
    r=f.read()
    soup=BeautifulSoup(r,"html.parser")

classes=soup.find_all(class_="tw-line-clamp-2")
names=[class_.text for class_ in classes]

prices=soup.find_all(class_="tw-text-200",string=re.compile(r"^₹"))
price=[price1.text for price1 in prices]

pattern=re.compile(r"^\d+")
quantitys=soup.find_all(class_="tw-text-200")
quantity=[q.get_text(strip=True) for q in quantitys if pattern.match(q.get_text(strip=True))]

images=soup.find_all("img")
image=[i["src"] for i in images]
# image = [i.get("src") for i in images ]
#if "/cms-assets/cms/product/" in i.get("src")
# for id,pic in enumerate(image,start=1):
#     im = Image.open(requests.get(pic, stream=True).raw)
#     im.show()
#     im.save(f"img{id}.png")

# print(len(image))

dict={"Name of the product":names,"Price":price,"Quantity":quantity}
df=pd.DataFrame(dict)
df.to_csv("blinkit_data.csv")
#print(df.to_string)

