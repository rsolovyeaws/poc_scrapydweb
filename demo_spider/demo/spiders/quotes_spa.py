"""
quotes_spa spider – now respects ?auth_enabled=... and stores results in S3
"""
import time, scrapy
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
class QuotesSpaSpider(scrapy.Spider):
    name = "quotes_spa"
    start_urls = ["https://quotes.toscrape.com/js/"]
    login_url = "https://quotes.toscrape.com/login"
    custom_settings = {
        # remote Selenium hub
        "SELENIUM_COMMAND_EXECUTOR": "http://selenium-hub:4444/wd/hub",
        "SELENIUM_DRIVER_ARGUMENTS": [
            "--headless", "--disable-gpu",
            "--no-sandbox", "--disable-dev-shm-usage",
        ],
        # Reduced pool size to avoid overwhelming the hub
        "SELENIUM_DRIVER_POOL_SIZE": 1,
        # middlewares
        "DOWNLOADER_MIDDLEWARES": {
            # Disable default user-agent middleware
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            # Ensure our User-Agent middleware is used
            "demo.user_agent_middleware.UserAgentRotationMiddleware": 750,
            "demo.custom_selenium_middleware.SeleniumMiddleware": 800,
            "demo.redis_cookies_middleware.RedisCookiesMiddleware": 900,
        },
        # pipelines
        "ITEM_PIPELINES": {
            "demo.pipelines.PostgresPipeline": 300,
            "demo.pipelines.S3StoragePipeline": 400,
        },
        # S3 specific settings (can override project settings)
        "S3_FOLDER_NAME": "quotes_data",
        # Redis settings
        "REDIS_HOST": "redis",
        "REDIS_PORT": 6379,
        "REDIS_DB": 0,
        "REDIS_COOKIES_ENABLED": True,
        "REDIS_COOKIES_KEY_PREFIX": "scrapy:cookies:",
        # User-Agent settings
        "USER_AGENT_ROTATION_ENABLED": True,
        # Use DEBUG level for more verbose logging
        "LOG_LEVEL": "DEBUG",
        # misc
        "CONCURRENT_REQUESTS": 3,
        "CLOSESPIDER_PAGECOUNT": 0,
    }
    # ─── ctor ────────────────────────────────────────────────────────────
    def __init__(self, username=None, password=None, auth_enabled="true", proxy=None, user_agent_type=None, user_agent=None, *a, **kw):
        super().__init__(*a, **kw)
        self.username = username or "admin"
        self.password = password or "admin"
        self.auth_enabled = str(auth_enabled).lower() != "false"
        self.proxy = proxy  # Store proxy parameter
        if self.proxy:
            self.logger.info(f"Proxy configured: {self.proxy}")
        
        # Debug log all parameters
        self.logger.info(f"Spider initialized with params: {a}, {kw}")
        
        # Store user agent parameters
        self.user_agent = user_agent
        if self.user_agent:
            self.logger.info(f"Custom User-Agent configured: {self.user_agent}")
        
        # Only use user_agent_type if no direct user_agent is specified
        self.user_agent_type = None if self.user_agent else user_agent_type
        if self.user_agent_type:
            self.logger.info(f"User-Agent type configured: {self.user_agent_type}")
        
        self.cookies, self.selenium_driver = [], None
        self.is_logged_in = False
        self.current_url = self.start_urls[0]  # Initialize with start URL
        
        # Dictionary to track proxies used for each URL
        self.proxies_used = {}
        
        # Dictionary to track User-Agents used for each URL (populated by UserAgentRotationMiddleware)
        self.user_agents_used = {}
    
    # set by middleware
    def set_selenium_driver(self, driver):
        self.selenium_driver = driver
    
    # ─── entry point ─────────────────────────────────────────────────────
    def start_requests(self):
        # Prepare meta with common settings
        meta = {"selenium": True, "wait_time": 2}  # Increased wait time
        
        # Add proxy to meta if specified
        if self.proxy:
            meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
            # Track this proxy for the start URL
            self.proxies_used[self.start_urls[0]] = self.proxy
        
        # Add User-Agent type to meta if specified
        if self.user_agent_type:
            meta['user_agent_type'] = self.user_agent_type
        
        # Add custom User-Agent to meta if specified
        if self.user_agent:
            meta['user_agent'] = self.user_agent
        
        if self.auth_enabled:
            self.logger.info("Authentication enabled → hitting login page")
            yield scrapy.Request(
                self.login_url,
                self.perform_login,
                meta=meta,
                dont_filter=True,
                errback=self.handle_error
            )
        else:
            self.logger.info("Authentication disabled → going straight to quotes")
            yield scrapy.Request(
                self.start_urls[0],
                self.parse,
                meta=meta,
                dont_filter=True,
                errback=self.handle_error
            )
    
    # Error handling callback
    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
        # Extract request information for logging
        request = failure.request
        self.logger.error(f"Failed URL: {request.url}")
        if 'selenium_session_id' in request.meta:
            self.logger.error(f"Session ID: {request.meta['selenium_session_id']}")
        # We're not retrying here, but you could if needed
    
    # ─── login flow (only when auth_enabled) ─────────────────────────────
    def perform_login(self, response):
        driver = response.meta.get("driver")
        if not driver:
            self.logger.error("No driver in response meta!")
            return None
            
        self.logger.debug(f"Login with driver session ID: {getattr(driver, 'session_id', 'unknown')}")
            
        # cookies from previous run?
        if self.cookies:
            self.logger.debug(f"DEBUG: Found {len(self.cookies)} cookies: {self.cookies}")
            try:
                self.is_logged_in = self._is_logged_in(driver)
                if self.is_logged_in:
                    self.logger.info("Cookie jar already logged in")
            except WebDriverException as e:
                self.logger.error(f"Error checking login state: {e}")
                self.is_logged_in = False
                
        # else try form login
        if not self.is_logged_in:
            try:
                # Wait for login form with increased timeout
                self.logger.debug("Waiting for login form...")
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                
                # Fill login form
                self.logger.debug(f"DEBUG: Logging in with username={self.username}, password={self.password}")
                driver.find_element(By.ID, "username").send_keys(self.username)
                driver.find_element(By.ID, "password").send_keys(self.password)
                
                # Click submit and wait for page to change
                self.logger.debug("Submitting login form...")
                driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                
                # Wait for page to change with increased timeout
                WebDriverWait(driver, 10).until(EC.url_changes(self.login_url))
                
                # Additional wait to allow page to load completely
                time.sleep(2)
                
                # Check if login was successful
                self.is_logged_in = self._is_logged_in(driver)
                
            except Exception as e:
                self.logger.error(f"Login automation error: {e}")
                self.is_logged_in = False
        
        # Get cookies from driver and save them immediately to ensure they're not lost
        try:
            self.cookies = driver.get_cookies()
            self.logger.debug(f"DEBUG: After login, collected {len(self.cookies)} cookies: {self.cookies}")
        except WebDriverException as e:
            self.logger.error(f"Failed to get cookies: {e}")
        
        # Manually save cookies to Redis to ensure they're not lost when the driver closes
        try:
            if self.cookies and hasattr(self, 'crawler') and hasattr(self.crawler, 'engine'):
                # Get the Redis middleware instance
                for middleware in self.crawler.engine.downloader.middleware.middlewares:
                    if hasattr(middleware, 'redis_client') and hasattr(middleware, '_get_key'):
                        key = middleware._get_key(self)
                        import json
                        middleware.redis_client.set(key, json.dumps(self.cookies))
                        self.logger.debug(f"DEBUG: Manually saved {len(self.cookies)} cookies to Redis with key {key}")
                        break
        except Exception as e:
            self.logger.error(f"DEBUG: Failed to manually save cookies: {e}")
        
        # Prepare meta with common settings
        meta = {"selenium": True, "wait_time": 2}
        
        # Add proxy to meta if specified
        if self.proxy:
            meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
            # Track the proxy for this URL
            self.proxies_used[self.start_urls[0]] = self.proxy
        
        # Add User-Agent type to meta if specified
        if self.user_agent_type:
            meta['user_agent_type'] = self.user_agent_type
            
        # Add custom User-Agent to meta if specified
        if self.user_agent:
            meta['user_agent'] = self.user_agent
        
        yield scrapy.Request(
            self.start_urls[0],
            self.parse,
            meta=meta,
            dont_filter=True,
            errback=self.handle_error
        )
    
    def _is_logged_in(self, driver):
        """Check if user is logged in by looking for logout link"""
        try:
            self.logger.debug("DEBUG: Checking if logged in...")
            
            # Verify the driver is still valid
            current_url = driver.current_url
            self.logger.debug(f"Current URL: {current_url}")
            
            # Look for logout link with increased timeout
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/logout')]"))
            )
            self.logger.info("Login verified - found logout link")
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.warning(f"Not logged in: {e}")
            return False
            
        except WebDriverException as e:
            self.logger.error(f"WebDriver error checking login status: {e}")
            # Indicate that login check failed due to driver error
            raise
    
    # ─── parse quotes pages ──────────────────────────────────────────────
    def parse(self, response):
        # Update current URL (used by S3 pipeline for filename)
        self.current_url = response.url
        
        # Get the current page's User-Agent and proxy for each item
        current_user_agent = response.request.headers.get('User-Agent', b'').decode('utf-8')
        current_proxy = self.proxy if self.proxy else None
        
        # Update tracking dictionaries
        if current_user_agent:
            self.user_agents_used[response.url] = current_user_agent
            self.logger.info(f"Using User-Agent for {response.url}: {current_user_agent}")
        if current_proxy:
            self.proxies_used[response.url] = current_proxy
        
        for q in response.css("div.quote"):
            yield {
                "text": q.css("span.text::text").get(),
                "author": q.css("small.author::text").get(),
                "tags": q.css("div.tags a.tag::text").getall(),
                "url": response.url,
                "user_agent": current_user_agent,
                "proxy": current_proxy
            }
        
        next_rel = response.css("li.next a::attr(href)").get()
        if next_rel:
            # Prepare meta with common settings
            meta = {"selenium": True, "wait_time": 2}
            
            # Add proxy to meta if specified
            if self.proxy:
                meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
                # Track this proxy for the next URL
                next_url = response.urljoin(next_rel)
                self.proxies_used[next_url] = self.proxy
            
            # Add User-Agent type to meta if specified
            if self.user_agent_type:
                meta['user_agent_type'] = self.user_agent_type
                
            # Add custom User-Agent to meta if specified
            if self.user_agent:
                meta['user_agent'] = self.user_agent
            
            yield scrapy.Request(
                response.urljoin(next_rel),
                self.parse,
                meta=meta,
                errback=self.handle_error
            )

    def closed(self, reason):
        """Cleanup when spider is closed"""
        self.logger.info(f"Spider closing: {reason}")
        
        # Ensure driver is properly closed
        if hasattr(self, 'selenium_driver') and self.selenium_driver:
            try:
                self.logger.info(f"Closing Selenium driver in spider closed callback")
                self.selenium_driver.quit()
            except Exception as e:
                self.logger.error(f"Error closing Selenium driver: {e}")
        
        # Fetch the Redis client if available
        try:
            if hasattr(self, 'crawler') and hasattr(self.crawler, 'engine'):
                for middleware in self.crawler.engine.downloader.middleware.middlewares:
                    # If this is a SeleniumMiddleware, clear its session counter
                    if hasattr(middleware, 'pool') and middleware.pool:
                        self.logger.info("Spider shutting down, clearing active Selenium sessions")
                        try:
                            # Try to access Redis through the SeleniumMiddleware
                            endpoint = "/selenium/reset"
                            import requests
                            response = requests.get(f"http://api-gateway:5000{endpoint}")
                            self.logger.info(f"Called API gateway to reset sessions: {response.status_code}")
                        except Exception as e:
                            self.logger.error(f"Error calling API gateway: {e}")
                        break
        except Exception as e:
            self.logger.error(f"Error in Spider.closed cleanup: {e}")
            
        self.logger.info("Spider closed successfully")