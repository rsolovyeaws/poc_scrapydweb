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
            # Ensure our User-Agent middleware
            "demo.user_agent_middleware.UserAgentRotationMiddleware": 543,
            # Custom Selenium middleware
            "demo.custom_selenium_middleware.SeleniumMiddleware": 750,
            # Redis cookies middleware
            "demo.redis_cookies_middleware.RedisCookiesMiddleware": 751,
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
        # Selenium related timeouts
        "SELENIUM_PAGE_LOAD_TIMEOUT": 60,
        "SELENIUM_IMPLICIT_WAIT": 10,
        "SELENIUM_WAIT_TIME": 30,
        # Default credentials (can be overridden with spider args)
        "DEFAULT_USERNAME": "admin",
        "DEFAULT_PASSWORD": "admin",
    }
    # ─── ctor ────────────────────────────────────────────────────────────
    def __init__(self, *args, **kwargs):
        super(QuotesSpaSpider, self).__init__(*args, **kwargs)
        
        # Initialize tracking dictionaries
        self.user_agents_used = {}
        self.proxies_used = {}  # Dictionary to track which proxies are used for which URLs
        
        # Initialize driver storage
        self.driver = None
        self.is_logged_in = False
        
        # Track login attempts
        self.login_attempts = 0
        self.max_login_attempts = 3
        
        # Initialize cookies
        self.cookies = []
        self.spider_closed = False
        
        # Set credentials - use kwargs first, then custom_settings if available
        self.username = kwargs.get('username') or self.custom_settings.get('DEFAULT_USERNAME', 'admin')
        self.password = kwargs.get('password') or self.custom_settings.get('DEFAULT_PASSWORD', 'admin')
        
        # Authentication flag
        self.auth_enabled = kwargs.get('auth_enabled', 'false').lower() == 'true'
        
        # Set proxy from spider arguments
        self.proxy = kwargs.get('proxy')
        if self.proxy:
            self.logger.info(f"Proxy configured: {self.proxy}")
        
        # Set user agent type and custom user agent
        self.user_agent_type = kwargs.get('user_agent_type', 'desktop')
        self.user_agent = kwargs.get('user_agent')
        
        # Log authentication settings
        if self.auth_enabled:
            self.logger.info(f"Authentication enabled: {self.auth_enabled}")
        
        self.logger.info(f"Spider initialized with params: {args}, {kwargs}")
    
    # set by middleware
    def set_selenium_driver(self, driver):
        self.driver = driver
    
    # ─── entry point ─────────────────────────────────────────────────────
    def start_requests(self):
        """
        Start with the login page if authentication is enabled
        """
        if getattr(self, 'auth_enabled', False):
            # Check if we already have a valid session from Redis
            if hasattr(self, 'using_redis_session') and self.using_redis_session:
                self.logger.info("Using existing cookies from Redis → skipping login")
                return [scrapy.Request(
                    url, 
                    callback=self.parse, 
                    meta={
                        "selenium": True, 
                        "wait_time": 10,
                        "cookies": self.cookies  # Pass cookies to the driver
                    }
                ) for url in self.start_urls]
            else:
                self.logger.info("Authentication enabled → hitting login page")
                return [scrapy.Request(
                    self.login_url,
                    callback=self.perform_login,
                    meta={
                        "selenium": True,
                        "wait_time": 10,
                        # Make sure we keep the driver alive for the login process
                        "custom_driver": False,
                        "preserve_driver": True
                    },
                    dont_filter=True
                )]
        else:
            self.logger.info("Authentication disabled → going straight to quotes")
            return [scrapy.Request(
                url, 
                callback=self.parse, 
                meta={"selenium": True, "wait_time": 10}
            ) for url in self.start_urls]
    
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
        """Login to the website using Selenium"""
        try:
            # Get driver from response meta
            driver = response.meta.get("driver")
            if not driver:
                self.logger.error("No driver in response meta. The driver was likely closed prematurely.")
                self.logger.info("Creating a new driver for login attempt...")
                
                # Fall back to regular browsing since we can't login
                return scrapy.Request(
                    self.start_urls[0], 
                    callback=self.parse, 
                    meta={"selenium": True, "wait_time": 10},
                    dont_filter=True
                )
            
            # Track login session ID for debugging
            session_id = getattr(driver, 'session_id', 'unknown')
            self.logger.info(f"Attempting login with Selenium session ID: {session_id}")
            
            # Verify the driver is still active by checking current URL
            try:
                current_url = driver.current_url
                self.logger.debug(f"Driver is active at URL: {current_url}")
            except Exception as e:
                self.logger.error(f"Driver is no longer valid: {e}")
                return scrapy.Request(
                    self.start_urls[0], 
                    callback=self.parse, 
                    meta={"selenium": True, "wait_time": 10},
                    dont_filter=True
                )
            
            # Wait for login form with increased timeout
            self.logger.debug("Waiting for login form...")
            
            # Wait for username field to be present with explicit retry loop
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    username_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "username"))
                    )
                    # Clear the field first
                    username_field.clear()
                    time.sleep(0.5)  # Brief pause
                    
                    # Log credentials being used (masked password)
                    masked_password = '*' * len(self.password) if self.password else None
                    self.logger.info(f"Login attempt #{self.login_attempts+1}/{self.max_login_attempts} with username={self.username}, password={masked_password}")
                    self.login_attempts += 1
                    
                    # Fill username with typing delay to mimic human behavior
                    for char in self.username:
                        username_field.send_keys(char)
                        time.sleep(0.05)  # Small delay between characters
                    
                    # Get password field with wait
                    password_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "password"))
                    )
                    password_field.clear()
                    time.sleep(0.5)  # Brief pause
                    
                    # Type password with delay
                    for char in self.password:
                        password_field.send_keys(char)
                        time.sleep(0.05)
                    
                    # Add pause before submitting
                    time.sleep(1)
                    
                    # Click submit and wait for page to change
                    self.logger.debug("Submitting login form...")
                    submit_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))
                    )
                    submit_button.click()
                    
                    # Wait for page to change with increased timeout
                    WebDriverWait(driver, 10).until(EC.url_changes(self.login_url))
                    
                    # Additional wait to allow page to load completely
                    time.sleep(2)
                    
                    # Check if login was successful by looking for logout link
                    try:
                        logout_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Logout')]"))
                        )
                        self.is_logged_in = True
                        self.logger.info("✅ Login successful!")
                        
                        # Save cookies after successful login
                        self.cookies = driver.get_cookies()
                        self.logger.debug(f"Saved {len(self.cookies)} cookies after login")
                        
                        # Success! Break out of retry loop
                        break
                        
                    except Exception as e:
                        self.logger.warning(f"❌ Login failed - could not find logout link: {e}")
                        self.is_logged_in = False
                        
                        if attempt < max_attempts - 1:
                            self.logger.info(f"Retrying login (attempt {attempt+2}/{max_attempts})...")
                            # Refresh the page for next attempt
                            driver.get(self.login_url)
                            time.sleep(2)  # Wait for page to load
                        
                except Exception as e:
                    self.logger.error(f"Login form interaction error on attempt {attempt+1}: {e}")
                    if attempt < max_attempts - 1:
                        self.logger.info(f"Retrying login (attempt {attempt+2}/{max_attempts})...")
                        # Refresh the page for next attempt
                        driver.get(self.login_url)
                        time.sleep(2)  # Wait for page to load
                    else:
                        self.is_logged_in = False
            
            # Return to start URL for crawling
            return scrapy.Request(
                self.start_urls[0],
                callback=self.parse,
                meta={"selenium": True, "wait_time": 10},
                dont_filter=True
            )
            
        except Exception as e:
            self.logger.error(f"Login process error: {e}")
            # Fall back to non-authenticated browsing
            return scrapy.Request(
                self.start_urls[0],
                callback=self.parse,
                meta={"selenium": True, "wait_time": 10},
                dont_filter=True
            )
    
    def _is_logged_in(self, driver):
        """Check if user is logged in by looking for logout link"""
        try:
            self.logger.debug("DEBUG: Checking if logged in...")
            
            # First ensure the page is loaded
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Verify the driver is still valid
            current_url = driver.current_url
            self.logger.debug(f"Current URL: {current_url}")
            
            # Use different methods to check login status
            
            # Method 1: Look for logout link 
            try:
                logout_link = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/logout')]"))
                )
                if logout_link:
                    self.logger.info("Login verified ✅ - found logout link")
                    return True
            except (TimeoutException, NoSuchElementException):
                self.logger.debug("No logout link found")
            
            # Method 2: Check URL patterns
            if "login" not in current_url.lower() and "/js/" in current_url:
                # Some sites redirect to main page after login
                self.logger.info("Login possibly verified ✅ - not on login page")
                return True
                
            # Method 3: Check page content for authenticated elements
            try:
                WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".user-profile, .profile-link, .welcome-message"))
                )
                self.logger.info("Login verified ✅ - found user profile elements")
                return True
            except (TimeoutException, NoSuchElementException):
                pass
                
            # If none of the above checks passed, assume not logged in
            self.logger.warning("Not logged in ❌ - authentication checks failed")
            return False
            
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