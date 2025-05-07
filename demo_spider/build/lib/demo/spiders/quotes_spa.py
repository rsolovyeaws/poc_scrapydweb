import scrapy
from scrapy.spiders import Spider

class QuotesSpaSpider(Spider):
    name = "quotes_spa"
    start_urls = ["https://quotes.toscrape.com/js/"]
    custom_settings = {
        'ITEM_PIPELINES': {
            'demo.pipelines.PostgresPipeline': 300,
        }
    }
    
    def __init__(self, *args, **kwargs):
        # Extract proxy from parameters if provided
        self.proxy = kwargs.get('proxy')
        super(QuotesSpaSpider, self).__init__(*args, **kwargs)
        
        if self.proxy:
            self.logger.info(f"Spider initialized with proxy: {self.proxy}")

    def start_requests(self):
        for url in self.start_urls:
            meta = {
                'selenium': True,   # This flag tells our middleware to use Selenium
                'wait_time': 2,     # Wait for JavaScript to load
                'current_url': url, # Track current URL for database logging
            }
            
            # Add proxy to meta if specified
            if self.proxy:
                meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
                meta['selenium_proxy'] = self.proxy  # For our custom Selenium middleware
                
            yield scrapy.Request(
                url=url, 
                callback=self.parse,
                meta=meta
            )

    def parse(self, response):
        # Store current URL for the pipeline
        self.current_url = response.url
        
        for quote in response.css("div.quote"):
            yield {
                "text": quote.css("span.text::text").get(),
                "author": quote.css("small.author::text").get(),
                "tags": quote.css("div.tags a.tag::text").getall(),
                "url": response.url,  # Include source URL in data
            }
            
        # Follow pagination links if they exist
        next_page = response.css("li.next a::attr(href)").get()
        if next_page is not None:
            next_page_url = response.urljoin(next_page)
            
            # Make sure to also include the proxy in pagination requests
            meta = {
                'selenium': True,
                'wait_time': 2,
                'current_url': next_page_url,
            }
            if hasattr(self, 'proxy') and self.proxy:
                meta['proxy'] = self.proxy
                meta['selenium_proxy'] = self.proxy
                
            yield scrapy.Request(
                url=next_page_url, 
                callback=self.parse,
                meta=meta
            )