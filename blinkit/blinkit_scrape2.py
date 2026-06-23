from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys  import Keys
import os
import time
os.chdir("quick_commerce/blinkit")


query="milk"
url=f"https://blinkit.com/s/?q={query}"
driver = webdriver.Chrome()
driver.get(url)
#driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
elems=driver.find_elements(By.CLASS_NAME,"tw-font-semibold")
for elem in elems:
     with open(r"htmls\data.html","a",encoding="utf-8") as f:
        a=elem.get_attribute("outerHTML")

        f.write(a)
quantity=driver.find_elements(By.CLASS_NAME,"tw-line-clamp-1")
for q in quantity:
    with open(r"htmls\data.html","a",encoding="utf-8") as f:
        g=q.get_attribute("outerHTML")
        f.write(g)
images=driver.find_elements(By.TAG_NAME,"img")
for image in images:
    with open(r"htmls\data.html","a",encoding="utf-8") as f:
        h=image.get_attribute("outerHTML")
        f.write(h)


driver.quit()


