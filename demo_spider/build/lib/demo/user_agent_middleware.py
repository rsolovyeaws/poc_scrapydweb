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
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.37',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
        ]
        
        self.logger = logging.getLogger('demo.user_agent_middleware')
        
        self.available_user_agents = {}
        
        # Connect to the rotation service if enabled
        if self.enabled:
            try:
                self.test_connection()
                self.logger.info("Connected to User-Agent rotation service")
            except Exception as e:
                self.logger.warning(f"Failed to connect to User-Agent rotation service: {e}")
                self.logger.warning("Will use fallback User-Agents")
                self.available_user_agents = {
                    'desktop': self.fallback_user_agents,
                    'mobile': self.fallback_user_agents[:3],
                    'tablet': self.fallback_user_agents[3:6],
                }
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    def test_connection(self):
        """Test connection to the UA rotation service"""
        response = requests.get(urljoin(self.ua_service_url, '/health'))
        response.raise_for_status()
        
        # Get all available user agents
        response = requests.get(urljoin(self.ua_service_url, '/api/user-agents'))
        response.raise_for_status()
        
        # Extract user agents by device type
        ua_data = response.json()
        if ua_data:
            self.available_user_agents = {
                'desktop': [],
                'mobile': [],
                'tablet': []
            }
            
            # Flatten the structure to match our expected format
            for device_type, browsers in ua_data.items():
                if device_type in self.available_user_agents:
                    for browser_agents in browsers.values():
                        self.available_user_agents[device_type].extend(browser_agents)
    
    def get_random_ua(self, ua_type='desktop'):
        """Get a random User-Agent from the specified category"""
        if not self.enabled:
            return random.choice(self.fallback_user_agents)
        
        try:
            if ua_type in self.available_user_agents and self.available_user_agents[ua_type]:
                return random.choice(self.available_user_agents[ua_type])
            
            # Request a random User-Agent from the service
            response = requests.get(urljoin(self.ua_service_url, f'/api/user-agent?type={ua_type}'))
            response.raise_for_status()
            return response.json().get('user_agent', random.choice(self.fallback_user_agents))
        except Exception as e:
            self.logger.error(f"Error getting User-Agent from rotation service: {e}")
            return random.choice(self.fallback_user_agents)
    
    def process_request(self, request, spider):
        """
        Apply User-Agent to outgoing requests
        """
        # Check if a specific user-agent is set on the spider or request
        direct_user_agent = getattr(spider, 'user_agent', None) or request.meta.get('user_agent')
        
        if direct_user_agent:
            self.logger.info(f"Request to {request.url}: Using User-Agent: {direct_user_agent}")
            request.headers['User-Agent'] = direct_user_agent.encode('utf-8')
            # Store for Selenium if needed
            request.meta['user_agent'] = direct_user_agent
            return None
        
        # Otherwise, get the User-Agent type from the spider or request meta
        ua_type = getattr(spider, 'user_agent_type', None) or request.meta.get('user_agent_type', 'desktop')
        user_agent = self.get_random_ua(ua_type)
        
        self.logger.info(f"Request to {request.url}: Using User-Agent: {user_agent}")
        
        # Apply the User-Agent to the request
        request.headers['User-Agent'] = user_agent.encode('utf-8')
        
        # Store for Selenium if needed
        request.meta['user_agent'] = user_agent
        
        return None 