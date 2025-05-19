import logging
import scrapy

class ExampleSpider(scrapy.Spider):
    name = 'example'
    # ... existing code ...
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configure logging for ELK stack
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        # Add custom fields to help with filtering
        self.logger.info(f"Spider {self.name} initialized", 
                         extra={
                             'spider_name': self.name,
                             'job_id': kwargs.get('_job', 'unknown')
                         })
    
    def parse(self, response):
        self.logger.info(f"Parsing {response.url}", 
                         extra={
                             'url': response.url,
                             'status': response.status
                         })
        # ... existing code ... 