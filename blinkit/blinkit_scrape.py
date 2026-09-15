from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import os
from selenium.webdriver.chrome.options import Options
filename=r"blinkit\htmls\blinkit_data.html"
def openFile(card):
     os.makedirs(os.path.dirname(filename), exist_ok=True)
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)

def blinkit_scrape(query):
    if os.path.exists(filename):
        os.remove(filename)
    url=f"https://blinkit.com/s/?q={query}"
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    driver = webdriver.Chrome()
    driver.get(url)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(10)

    elems=driver.find_elements(By.CLASS_NAME,"tw-font-semibold")
    for elem in elems:
        openFile(elem)

    quantity=driver.find_elements(By.CLASS_NAME,"tw-line-clamp-1")
    for q in quantity:
        openFile(q)

    images=driver.find_elements(By.CSS_SELECTOR,".tw-h-full.tw-w-full.tw-transition-opacity.tw-opacity-100")
    for img in images:
        openFile(img)

    driver.quit()
blinkit_scrape("milk")

