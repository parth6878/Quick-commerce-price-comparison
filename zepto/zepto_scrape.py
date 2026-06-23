from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import os


filename=r"zepto\htmls\zepto_data.html"
def openFile(card):
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)


query="milk"
url=f"https://www.zepto.com/search?query={query}"


driver=webdriver.Chrome()
driver.get(url)
time.sleep(2)


price_card=driver.find_elements(By.CLASS_NAME,"cptQT7")
for price in price_card:
   openFile(price)



productName_card=driver.find_elements(By.CSS_SELECTOR,"[data-slot-id='ProductName']")
for name in productName_card:
    openFile(name)

quantity_card=driver.find_elements(By.CSS_SELECTOR,"[data-slot-id='PackSize']")
for quantity in quantity_card:
    openFile(quantity)


driver.close()
# print(1) if os.path.exists(filename) else print(2)
# print(os.path.abspath(filename))
# print(os.path.getsize(filename))