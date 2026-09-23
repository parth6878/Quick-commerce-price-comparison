from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import os 

filename=r"amazon/htmls/amazon_data.html"



def openFile(card):
     os.makedirs(os.path.dirname(filename), exist_ok=True)
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)


def amazon_scrape(query):
        if os.path.exists(filename):
              os.remove(filename)
        url = f"https://www.amazon.in/s?k={query}&i=nowstore"
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 

        driver=webdriver.Chrome(options=chrome_options)
        driver.get(url)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        name_card=driver.find_elements(By.CLASS_NAME,"a-section.a-spacing-small.puis-padding-left-small.puis-padding-right-small")
        for name in name_card:
                openFile(name)

        # price_card=driver.find_elements(By.CLASS_NAME,'a-price-whole')
        # for price in price_card:
        #         openFile(price)


        