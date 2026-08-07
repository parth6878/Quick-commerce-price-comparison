from selenium import webdriver
from selenium.webdriver.common.by import By
import time

filename=r"zepto\htmls\zepto_data.html"
def openFile(card):
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)


def zepto_scrape(query):
    url=f"https://www.zepto.com/search?query={query}"


    driver=webdriver.Chrome()
    driver.get(url)
    driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
    time.sleep(15)


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