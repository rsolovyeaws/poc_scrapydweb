"""
Prometheus metrics middleware for Scrapy.
This middleware exports Scrapy stats as Prometheus metrics.
"""

import time
from typing import Any, Dict, Optional, Type

from prometheus_client import Counter, Gauge, Histogram
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.spiders import Spider
from twisted.internet import task

# Define Prometheus metrics
SCRAPY_ITEMS_SCRAPED = Counter(
    'scrapy_items_scraped_total',
    'Total number of items scraped',
    ['spider', 'spider_type']
)

SCRAPY_ITEM_SCRAPED_LATENCY = Histogram(
    'scrapy_item_scraped_latency_seconds',
    'Latency of scraping an item',
    ['spider', 'spider_type'],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 30.0, 60.0)
)

SCRAPY_RESPONSE_STATUS = Counter(
    'scrapy_response_status_total',
    'Total response status codes',
    ['spider', 'spider_type', 'status']
)

SCRAPY_RESPONSE_SIZE = Histogram(
    'scrapy_response_size_bytes',
    'Response size in bytes',
    ['spider', 'spider_type'],
    buckets=(
        10, 100, 1000, 10000, 100000, 1000000, 10000000
    )
)

SCRAPY_REQUESTS_TOTAL = Counter(
    'scrapy_requests_total',
    'Total requests made',
    ['spider', 'spider_type', 'method']
)

SCRAPY_EXCEPTIONS_TOTAL = Counter(
    'scrapy_exceptions_total',
    'Total exceptions raised',
    ['spider', 'spider_type', 'exception_type']
)

SCRAPY_ACTIVE_SPIDERS = Gauge(
    'scrapy_active_spiders',
    'Number of active spiders',
    ['spider_type']
)

SCRAPY_SPIDER_MEMORY = Gauge(
    'scrapy_memory_usage_bytes',
    'Memory usage of the spider process',
    ['spider', 'spider_type']
)

SCRAPY_REQUEST_DEPTH = Histogram(
    'scrapy_request_depth',
    'Depth of requests',
    ['spider', 'spider_type'],
    buckets=(1, 2, 3, 4, 5, 10, 20, 50, 100)
)

SCRAPY_SCHEDULER_QUEUE_SIZE = Gauge(
    'scrapy_scheduler_queue_size',
    'Size of the scheduler queue',
    ['spider', 'spider_type']
)

class PrometheusMetricsMiddleware:
    """Middleware to collect Scrapy metrics and export them to Prometheus."""

    def __init__(self, stats, crawler: Crawler, memory_check_interval: int = 30):
        self.stats = stats
        self.crawler = crawler
        self.spider: Optional[Spider] = None
        self.spider_type: str = "unknown"
        self.memory_check_interval = memory_check_interval
        self.memory_check_task: Optional[task.LoopingCall] = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "PrometheusMetricsMiddleware":
        # Create the middleware instance
        middleware = cls(
            crawler.stats,
            crawler,
            memory_check_interval=crawler.settings.getint(
                'PROMETHEUS_MEMORY_CHECK_INTERVAL', 30
            )
        )
        
        # Connect the signals
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(middleware.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(middleware.item_error, signal=signals.item_error)
        crawler.signals.connect(middleware.response_received, signal=signals.response_received)
        crawler.signals.connect(middleware.request_scheduled, signal=signals.request_scheduled)
        
        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Handle spider opened signal."""
        self.spider = spider
        self.spider_type = getattr(spider, 'spider_type', 'default')
        
        # Increment active spiders gauge
        SCRAPY_ACTIVE_SPIDERS.labels(
            spider_type=self.spider_type
        ).inc()
        
        # Start memory check task
        self.memory_check_task = task.LoopingCall(self._check_memory_usage)
        self.memory_check_task.start(self.memory_check_interval)

    def spider_closed(self, spider: Spider) -> None:
        """Handle spider closed signal."""
        # Decrement active spiders gauge
        SCRAPY_ACTIVE_SPIDERS.labels(
            spider_type=self.spider_type
        ).dec()
        
        # Stop memory check task
        if self.memory_check_task and self.memory_check_task.running:
            self.memory_check_task.stop()

    def item_scraped(self, item: Dict, response: Response, spider: Spider) -> None:
        """Handle item scraped signal."""
        # Increment items scraped counter
        SCRAPY_ITEMS_SCRAPED.labels(
            spider=spider.name,
            spider_type=self.spider_type
        ).inc()
        
        # Record item scraped latency
        request_start_time = getattr(response.request, 'start_time', None)
        if request_start_time:
            latency = time.time() - request_start_time
            SCRAPY_ITEM_SCRAPED_LATENCY.labels(
                spider=spider.name,
                spider_type=self.spider_type
            ).observe(latency)

    def item_error(self, item: Dict, response: Response, spider: Spider, failure: Any) -> None:
        """Handle item error signal."""
        # Increment exceptions counter
        exception_type = failure.value.__class__.__name__
        SCRAPY_EXCEPTIONS_TOTAL.labels(
            spider=spider.name,
            spider_type=self.spider_type,
            exception_type=exception_type
        ).inc()

    def response_received(self, response: Response, request: Request, spider: Spider) -> None:
        """Handle response received signal."""
        # Increment response status counter
        SCRAPY_RESPONSE_STATUS.labels(
            spider=spider.name,
            spider_type=self.spider_type,
            status=str(response.status)
        ).inc()
        
        # Record response size
        SCRAPY_RESPONSE_SIZE.labels(
            spider=spider.name,
            spider_type=self.spider_type
        ).observe(len(response.body))
        
        # Record request depth
        if hasattr(request, 'meta') and 'depth' in request.meta:
            SCRAPY_REQUEST_DEPTH.labels(
                spider=spider.name,
                spider_type=self.spider_type
            ).observe(request.meta['depth'])

    def request_scheduled(self, request: Request, spider: Spider) -> None:
        """Handle request scheduled signal."""
        # Record request start time for latency calculation
        request.start_time = time.time()
        
        # Increment requests counter
        SCRAPY_REQUESTS_TOTAL.labels(
            spider=spider.name,
            spider_type=self.spider_type,
            method=request.method
        ).inc()
        
        # Update scheduler queue size
        if hasattr(self.crawler, 'engine') and hasattr(self.crawler.engine, 'slot'):
            slot = self.crawler.engine.slot
            if slot and hasattr(slot, 'scheduler'):
                queue_size = len(getattr(slot.scheduler, 'mqs', []))
                SCRAPY_SCHEDULER_QUEUE_SIZE.labels(
                    spider=spider.name,
                    spider_type=self.spider_type
                ).set(queue_size)

    def _check_memory_usage(self) -> None:
        """Check and record memory usage."""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            SCRAPY_SPIDER_MEMORY.labels(
                spider=self.spider.name if self.spider else "unknown",
                spider_type=self.spider_type
            ).set(memory_info.rss)
        except (ImportError, Exception) as e:
            # Just silently fail if psutil is not available
            pass 