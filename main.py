from blinkit.blinkit_read import blinkit_read
from blinkit.blinkit_scrape import blinkit_scrape
from amazon.amazon_read import amazon_read
from amazon.amazon_scrape import amazon_scrape
from zepto.zepto_read import read_zepto
from zepto.zepto_scrape import zepto_scrape

query=input("Enter your query: ")
blinkit_scrape(query)
zepto_scrape(query)
amazon_scrape(query)

blinkit_read()
read_zepto()
amazon_read()