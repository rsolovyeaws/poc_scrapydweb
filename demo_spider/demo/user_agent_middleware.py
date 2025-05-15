"""
User-Agent rotation middleware for Scrapy
─────────────────────────────────────────────────────────────────────────
- Communicates with the ua-rotator service to get random User-Agents
- Applies User-Agents to both regular requests and Selenium sessions
"""

import json
import logging
import random
import requests
from urllib.parse import urljoin

from scrapy.exceptions import NotConfigured


class UserAgentRotationMiddleware:
    """Middleware for rotating User-Agents from the ua-rotator service"""
    
    def __init__(self, settings):
        self.ua_service_url = settings.get('USER_AGENT_SERVICE_URL', 'http://ua-rotator:5000')
        self.enabled = settings.getbool('USER_AGENT_ROTATION_ENABLED', True)
        self.fallback_user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        self.logger = logging.getLogger(__name__)
        
        if not self.enabled:
            raise NotConfigured("User-Agent rotation is disabled")
            
        # Test connection to UA service on startup
        self.test_connection()
        
    def test_connection(self):
        """Test connection to the UA service on startup"""
        try:
            response = requests.get(urljoin(self.ua_service_url, '/health'), timeout=2)
            if response.status_code == 200:
                self.logger.info("Connected to User-Agent rotation service")
                return True
        except Exception as e:
            self.logger.warning(f"Cannot connect to User-Agent rotation service: {e}")
            self.logger.warning("Will use fallback User-Agents")
        return False
        
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler.settings)
        return middleware
        
    def get_random_user_agent(self, ua_type=None):
        """Get a random User-Agent from the service or fallback list"""
        try:
            url = urljoin(self.ua_service_url, '/api/user-agent')
            if ua_type:
                url = f"{url}?type={ua_type}"
                
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                user_agent = data.get('user_agent')
                self.logger.debug(f"Got User-Agent from service: {user_agent}")
                return user_agent
        except Exception as e:
            self.logger.debug(f"Error getting User-Agent from service: {e}")
            
        # Fallback to local list if service unavailable
        user_agent = random.choice(self.fallback_user_agents)
        self.logger.debug(f"Using fallback User-Agent: {user_agent}")
        return user_agent
        
    def process_request(self, request, spider):
        """
        Apply User-Agent to outgoing requests
        """
        # First check if the request or spider has a specific user-agent
        direct_user_agent = getattr(spider, 'user_agent', None) or request.meta.get('user_agent')
        
        if direct_user_agent:
            self.logger.info(f"Using specified User-Agent: {direct_user_agent}")
            request.headers['User-Agent'] = direct_user_agent.encode('utf-8')
            # Store for Selenium if needed
            request.meta['user_agent'] = direct_user_agent
            return None
            
        # Get User-Agent type from spider or request meta
        ua_type = getattr(spider, 'user_agent_type', None) or request.meta.get('user_agent_type')
        
        # Always set a User-Agent regardless of whether one is already set
        # This ensures our User-Agent takes precedence over any default ones
        user_agent = self.get_random_user_agent(ua_type)
        
        # Apply the User-Agent as bytes (Scrapy headers expect bytes)
        request.headers['User-Agent'] = user_agent.encode('utf-8')
        
        # Store for Selenium if needed
        request.meta['user_agent'] = user_agent
        
        # Log detailed information about the selected User-Agent
        self.logger.info(f"Request to {request.url}: Using User-Agent: {user_agent}")
        
        # Store the User-Agent in spider for later access by pipelines
        if not hasattr(spider, 'user_agents_used'):
            spider.user_agents_used = {}
        
        # Track User-Agent by URL
        spider.user_agents_used[request.url] = user_agent
        
        return None 