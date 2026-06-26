from selenium import webdriver
from selenium.webdriver.common.by import By
import time

filename=r"blinkit\htmls\blinkit_data.html"

def openFile(card):
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)

query="milk"
url=f"https://blinkit.com/s/?q={query}"

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

images=driver.find_elements(By.TAG_NAME,"img")

for image in images:
    openFile(image)





driver.quit()


