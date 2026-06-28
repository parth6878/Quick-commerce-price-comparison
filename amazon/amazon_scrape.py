from selenium import webdriver
from selenium.webdriver.common.by import By


filename=r"amazon/htmls/amazon_data.html"


def openFile(card):
     with open(filename,"a",encoding="utf-8") as f:
        htmlElement=card.get_attribute("outerHTML")
        f.write(htmlElement)


query="milk"
url=f"https://www.amazon.in/s?k={query}&i=nowstore&rh=n%3A16392737031&crid=8Q14QYSWTQL5&sprefix=m%2Cnowstore%2C533&ref=nb_sb_noss_2"

driver=webdriver.Chrome()
driver.get(url)

driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

name_card=driver.find_elements(By.CLASS_NAME,"a-section.a-spacing-small.puis-padding-left-small.puis-padding-right-small")
for name in name_card:
    openFile(name)
print(name_card)

