import scrapy
from scrapy.spiders import Spider

class QuotesSpaSpider(Spider):
    name = "quotes_spa"
    start_urls = ["https://quotes.toscrape.com/js/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url, 
                callback=self.parse,
                meta={
                    'selenium': True,  # This flag tells our middleware to use Selenium
                    'wait_time': 2,    # Wait for JavaScript to load
                }
            )

    def parse(self, response):
        for quote in response.css("div.quote"):
            yield {
                "text": quote.css("span.text::text").get(),
                "author": quote.css("small.author::text").get(),
                "tags": quote.css("div.tags a.tag::text").getall(),
            }
            
        # Follow pagination links if they exist
        next_page = response.css("li.next a::attr(href)").get()
        if next_page is not None:
            next_page_url = response.urljoin(next_page)
            yield scrapy.Request(
                url=next_page_url, 
                callback=self.parse,
                meta={
                    'selenium': True,
                    'wait_time': 2,
                }
            )