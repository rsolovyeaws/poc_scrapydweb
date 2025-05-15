"""
Proxy rotation middleware for Scrapy
─────────────────────────────────────────────────────────────────────────
- Communicates with the proxy-rotator service to get rotating proxies
- Applies proxies to both regular requests and Selenium sessions
"""

import json
import logging
import requests
from urllib.parse import urljoin

from scrapy.exceptions import NotConfigured


class ProxyRotationMiddleware:
    """Middleware for rotating proxies from the proxy-rotator service"""
    
    def __init__(self, settings):
        self.proxy_service_url = settings.get('PROXY_SERVICE_URL', 'http://proxy-rotator:5000')
        self.enabled = settings.getbool('PROXY_ROTATION_ENABLED', True)
        self.fallback_proxy = settings.get('PROXY', 'http://tinyproxy1:8888')
        self.logger = logging.getLogger(__name__)
        
        if not self.enabled:
            raise NotConfigured("Proxy rotation is disabled")
            
        # Test connection to proxy service on startup
        self.test_connection()
        
    def test_connection(self):
        """Test connection to the proxy service on startup"""
        try:
            response = requests.get(urljoin(self.proxy_service_url, '/status'), timeout=2)
            if response.status_code == 200:
                self.logger.info("Connected to proxy rotation service")
                return True
        except Exception as e:
            self.logger.warning(f"Cannot connect to proxy rotation service: {e}")
            self.logger.warning(f"Will use fallback proxy: {self.fallback_proxy}")
        return False
        
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler.settings)
        return middleware
        
    def get_proxy(self):
        """Get a proxy from the rotation service or use fallback"""
        try:
            url = urljoin(self.proxy_service_url, '/proxy')
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                proxy = data.get('proxy')
                self.logger.debug(f"Got proxy from service: {proxy}")
                return proxy
        except Exception as e:
            self.logger.debug(f"Error getting proxy from service: {e}")
            
        # Fallback to default proxy if service unavailable
        self.logger.debug(f"Using fallback proxy: {self.fallback_proxy}")
        return self.fallback_proxy
        
    def process_request(self, request, spider):
        """
        Apply proxy to outgoing requests
        """
        # Check if a specific proxy is specified in request meta or spider
        specified_proxy = request.meta.get('proxy') or getattr(spider, 'proxy', None)
        
        if specified_proxy:
            self.logger.debug(f"Using specified proxy: {specified_proxy}")
            request.meta['proxy'] = specified_proxy
        else:
            # Get a proxy from rotation service
            proxy = self.get_proxy()
            request.meta['proxy'] = proxy
            
            # Log detailed information about the selected proxy
            self.logger.info(f"Request to {request.url}: Using proxy: {proxy}")
        
        # Log proxy for each request in a standardized format that's easy to find in logs
        spider.logger.info(f"🔄 PROXY: {request.meta['proxy']} - URL: {request.url}")
        
        # Store for Selenium if needed
        request.meta['selenium_proxy'] = request.meta['proxy']
        
        # Store the proxy in spider for later access by pipelines
        if not hasattr(spider, 'proxies_used'):
            spider.proxies_used = {}
        
        # Track proxy by URL
        spider.proxies_used[request.url] = request.meta['proxy']
        
        return None 