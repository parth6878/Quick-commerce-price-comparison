from bs4 import BeautifulSoup
import pandas as pd



names=[]
prices=[]
quantities=[]


filename=r"zepto\htmls\zepto_data.html"
with open(filename,"r",encoding="utf-8") as f:
    r=f.read()
    soup=BeautifulSoup(r,"html.parser")


names_soup=soup.select("[data-slot-id='ProductName']")
names=[name.text for name in names_soup]


prices_soup=soup.find_all(class_="cptQT7")
prices=[price.text for price in prices_soup]


quantity_soup=soup.select("[data-slot-id='PackSize']")
quantities=[quantity.text for quantity in quantity_soup]


data={"Name of the product":names,"Price":prices,"Quantity":quantities}
df=pd.DataFrame(data)
df.to_csv(r"zepto\zepto_data_csv")
