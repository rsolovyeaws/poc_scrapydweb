"""
Selenium middleware (remote-hub friendly) with driver pool ✔
"""
import queue
import time
import random
import threading
from urllib.parse import urlparse
from scrapy import signals
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchDriverException, 
    WebDriverException, 
    SessionNotCreatedException,
    TimeoutException
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import RemoteConnection
from selenium.webdriver.remote.webdriver import WebDriver

# ───────── helpers ─────────────────────────────────────────────────────────
def _inject_cookies(driver, cookies, domain, log):
    if not cookies:
        return
    try:
        log.debug(f"Loading domain {domain} for cookie injection")
        driver.get(f"https://{domain}")
        time.sleep(1)  # Give more time for page to load properly
        
        added = 0
        for c in cookies:
            try:
                log.debug(f"Adding cookie: {c['name']}")
                driver.add_cookie(
                    {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": domain,
                        "path": c.get("path", "/"),
                    }
                )
                added += 1
            except Exception as exc:  # noqa: BLE001
                log.debug(f"Cookie inject failed {c['name']}: {exc}")
        log.info(f"SeleniumMiddleware: injected {added} cookies")
        
        # Refresh page after cookies are added
        driver.refresh()
        time.sleep(0.5)
    except WebDriverException as e:
        log.error(f"Cookie injection error: {e}")

# Thread-safe counter for active sessions
class _SessionCounter:
    def __init__(self, max_sessions):
        self.max_sessions = max_sessions
        self.current = 0
        self.lock = threading.Lock()
        
    def acquire(self):
        with self.lock:
            if self.current < self.max_sessions:
                self.current += 1
                return True
            return False
            
    def release(self):
        with self.lock:
            if self.current > 0:
                self.current -= 1
                
    def get_count(self):
        with self.lock:
            return self.current

class _DriverPool:
    """Thread-safe pool."""
    def __init__(self, size, make_driver, spider):
        self._size = size
        self._make = make_driver
        self._spider = spider
        self._q = queue.Queue(maxsize=size)
        self._all = []
        
        # Initialize session counter
        self._session_counter = _SessionCounter(size)
        
        # We'll create drivers on demand instead of all at once
        # This prevents overwhelming the Selenium hub
    
    def _spawn(self, max_retries=3, retry_delay=2):
        """Create a new driver with retry logic"""
        for attempt in range(max_retries):
            try:
                self._spider.logger.debug(f"Creating driver (attempt {attempt+1}/{max_retries})")
                d = self._make()
                
                # Test that the driver works
                d.current_url
                
                if getattr(self._spider, "cookies", None):
                    dom = urlparse(self._spider.start_urls[0]).netloc
                    _inject_cookies(d, self._spider.cookies, dom, self._spider.logger)
                
                self._all.append(d)
                return d
                
            except (SessionNotCreatedException, WebDriverException) as e:
                self._spider.logger.warning(f"Driver creation failed (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    # Add jitter to retry delay
                    jitter = random.uniform(0.5, 2.0)
                    sleep_time = retry_delay * (attempt + 1) * jitter
                    self._spider.logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    self._spider.logger.error(f"Failed to create driver after {max_retries} attempts")
                    # Release the session counter as we're giving up
                    self._session_counter.release()
                    raise
    
    def acquire(self, max_retries=3, retry_delay=2):
        """Acquire a driver from the pool or create a new one with retries"""
        # First try to get from the queue
        try:
            # Non-blocking check of the queue
            return self._q.get_nowait()
        except queue.Empty:
            # If no drivers in queue, check if we can create a new one
            if not self._session_counter.acquire():
                # If we're at max capacity, wait for a driver to be returned
                self._spider.logger.info("Waiting for Selenium session to become available...")
                try:
                    # Blocking wait for a driver
                    return self._q.get(timeout=60)  # 1 minute timeout
                except queue.Empty:
                    self._spider.logger.error("Timed out waiting for available Selenium session")
                    raise SessionNotCreatedException("Timeout waiting for available Selenium session")
            
            # We acquired a session counter, create a driver
            try:
                return self._spawn(max_retries, retry_delay)
            except Exception as e:
                # Release session on failure
                self._session_counter.release()
                raise e
    
    def release(self, d):
        try:
            # Check if driver is still valid before returning to pool
            d.current_url  # This will raise if driver is invalid
            self._q.put(d)
        except WebDriverException:
            # If driver is invalid, release the session counter
            self._spider.logger.debug("Driver is invalid, releasing session")
            self._session_counter.release()
            # Driver is invalid, remove from our list
            if d in self._all:
                self._all.remove(d)
            
    def shutdown(self):
        self._spider.logger.info(f"Shutting down Selenium driver pool ({len(self._all)} drivers)")
        for d in self._all:
            try:
                d.quit()
            except Exception as e:  # noqa: BLE001
                self._spider.logger.error(f"Error quitting driver: {e}")
                pass
        self._all.clear()
        
    def get_active_count(self):
        return self._session_counter.get_count()

# ───────── middleware ─────────────────────────────────────────────────────
class SeleniumMiddleware:
    def __init__(
        self,
        crawler,
        command_executor,
        driver_args,
        pool_size,
    ):
        self.crawler = crawler
        self.command_executor = command_executor
        self.driver_args = driver_args or []
        self.pool_size = pool_size
        self.pool = None
        
        # Track requests that are waiting for a driver
        self._waiting_requests = set()
    
    # ---- driver factory --------------------------------------------------
    def _make_options(self, spider=None, user_agent=None):
        o = ChromeOptions()
        for a in self.driver_args:
            o.add_argument(a)
        o.add_argument("--no-sandbox")
        o.add_argument("--disable-dev-shm-usage")
        
        # Add User-Agent if provided
        if user_agent:
            o.add_argument(f'--user-agent={user_agent}')
            spider.logger.debug(f"Selenium using User-Agent: {user_agent}")
        
        # Add proxy if provided in request meta, spider attributes, or settings
        selenium_proxy = None
        if spider:
            # Check for proxy in request meta (highest priority)
            if hasattr(spider, 'current_request') and getattr(spider.current_request, 'meta', {}).get('selenium_proxy'):
                selenium_proxy = spider.current_request.meta.get('selenium_proxy')
                spider.logger.debug(f"Using proxy from request meta: {selenium_proxy}")
            # Check for proxy in spider attributes (medium priority)
            elif hasattr(spider, 'proxy') and spider.proxy:
                selenium_proxy = spider.proxy
                spider.logger.debug(f"Using proxy from spider attribute: {selenium_proxy}")
            # Check for proxy in settings (lowest priority)
            elif hasattr(self.crawler.settings, 'get') and self.crawler.settings.get('PROXY'):
                selenium_proxy = self.crawler.settings.get('PROXY')
                spider.logger.debug(f"Using proxy from settings: {selenium_proxy}")
                
            # Apply proxy if found
            if selenium_proxy:
                o.add_argument(f'--proxy-server={selenium_proxy}')
                spider.logger.debug(f"Selenium using proxy: {selenium_proxy}")
                # Add a prominent log entry for the proxy being used with Selenium
                spider.logger.info(f"🌐 SELENIUM PROXY: {selenium_proxy}")
        
        return o
    
    def _spawn_driver(self, spider=None, user_agent=None):
        spider.logger.debug("Creating new Selenium driver")
        
        # Add keep-alive options to prevent session termination
        options = self._make_options(spider, user_agent)
        
        # Add timeouts and other capabilities through the options object
        # This is the Selenium 4 compatible way (no separate desired_capabilities)
        options.set_capability("pageLoadStrategy", "normal")
        
        # Set timeouts using the options
        options.set_capability("timeouts", {
            "implicit": 0,
            "pageLoad": 300000,  # 5 minutes
            "script": 60000      # 1 minute
        })
        
        # Create WebDriver with extended timeouts - Selenium 4 compatible
        driver = webdriver.Remote(
            command_executor=self.command_executor,
            options=options
        )
        
        # After creating the driver, add window management to avoid issues
        try:
            # Set a reasonable window size
            driver.set_window_size(1366, 768)
            # Initial navigation to about:blank to ensure driver is working
            driver.get("about:blank")
        except Exception as e:
            spider.logger.error(f"Error setting up driver: {e}")
            try:
                driver.quit()
            except:
                pass
            raise
        
        spider.logger.debug(f"Driver created with session ID: {driver.session_id}")
        return driver
    
    # ---- Scrapy plumbing -------------------------------------------------
    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        cmd_exec = s.get("SELENIUM_COMMAND_EXECUTOR")
        if not cmd_exec:
            raise NotConfigured("SELENIUM_COMMAND_EXECUTOR missing")
        pool_size = int(s.get("SELENIUM_DRIVER_POOL_SIZE", 1))
        driver_args = s.getlist("SELENIUM_DRIVER_ARGUMENTS")
        obj = cls(crawler, cmd_exec, driver_args, pool_size)
        crawler.signals.connect(obj._on_spider_closed, signals.spider_closed)
        return obj
    
    # Pool helper
    def _pool(self, spider):
        if self.pool is None:
            # Pass spider to driver creation for proxy access
            def driver_factory():
                return self._spawn_driver(spider)
            
            self.pool = _DriverPool(self.pool_size, driver_factory, spider)
        return self.pool
    
    # ---- request / response hooks ---------------------------------------
    def process_request(self, request, spider):
        if not request.meta.get("selenium"):
            return None
        
        # Add request to waiting set
        self._waiting_requests.add(id(request))
        
        # Get or create pool
        pool = self._pool(spider)
        
        # Store current request in spider for access in driver creation
        spider.current_request = request
        
        # Increased wait time from 10 seconds default
        wait_time = request.meta.get("wait_time", 30)
        
        # Log active sessions
        active_count = pool.get_active_count()
        spider.logger.info(f"Active Selenium sessions: {active_count}/{self.pool_size}")
        
        # Get User-Agent from request headers
        user_agent = None
        if 'User-Agent' in request.headers:
            user_agent = request.headers['User-Agent'].decode('utf-8')
        
        # Create or acquire driver
        try:
            if user_agent:
                spider.logger.info(f"Applying User-Agent to Selenium: {user_agent}")
                driver = self._spawn_driver(spider, user_agent)
                request.meta['custom_driver'] = True
            else:
                # Use progressive retry backoff
                driver = pool.acquire(max_retries=3, retry_delay=2)
                request.meta['custom_driver'] = False
            
            # Important: Store the session ID for debugging
            request.meta['selenium_session_id'] = driver.session_id
            spider.logger.debug(f"Using Selenium session ID: {driver.session_id}")
            
            # Store driver in spider for access in callbacks
            spider.set_selenium_driver(driver)
            
            # Apply cookies if they're in the request meta (from Redis)
            cookies = request.meta.get('cookies', [])
            if cookies:
                spider.logger.info(f"Applying {len(cookies)} cookies from Redis to Selenium session")
                # Go to the domain first to set cookies
                parsed_url = urlparse(request.url)
                domain_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                driver.get(domain_url)
                
                # Add each cookie to the driver
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        spider.logger.warning(f"Failed to add cookie: {e}")
            
            # Log navigation
            spider.logger.debug(f"Selenium navigating to {request.url}")
            
            # Increase retry logic with more aggressive timeouts
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Add pre-navigation check to ensure driver is alive
                    driver.current_url  # Will raise if driver is dead
                    
                    # Clear any existing cookies before navigation for fresh state
                    if request.url.startswith(spider.login_url) and not getattr(spider, "is_logged_in", False):
                        driver.delete_all_cookies()
                        spider.logger.debug("Cleared cookies before login attempt")
                    
                    # Navigate to the requested URL
                    spider.logger.debug(f"Navigation attempt {retry_count+1}/{max_retries} to {request.url}")
                    driver.get(request.url)
                    
                    # Wait for page to load
                    WebDriverWait(driver, wait_time).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    
                    break  # Success, exit retry loop
                
                except WebDriverException as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        spider.logger.error(f"Navigation failed after {retry_count} attempts: {e}")
                        raise
                    
                    spider.logger.warning(f"Navigation failed (attempt {retry_count}/{max_retries}): {e}")
                    time.sleep(2 * retry_count)  # Increasing backoff
            
            # Verify the User-Agent was applied 
            if user_agent:
                try:
                    actual_ua = driver.execute_script("return navigator.userAgent")
                    spider.logger.debug(f"Verified Selenium User-Agent: {actual_ua}")
                    if user_agent not in actual_ua:
                        spider.logger.warning(f"User-Agent mismatch! Expected: {user_agent}, Got: {actual_ua}")
                except Exception as e:
                    spider.logger.error(f"Error checking User-Agent in Selenium: {e}")
            
            # Create response object
            body = driver.page_source.encode()
            response = HtmlResponse(
                url=driver.current_url,
                body=body, 
                encoding="utf-8", 
                request=request
            )
            response.meta["driver"] = driver
            response.meta["selenium_session_id"] = driver.session_id
            
            # Remove request from waiting set
            self._waiting_requests.discard(id(request))
            
            return response
            
        except SessionNotCreatedException as e:
            spider.logger.error(f"Failed to create Selenium session: {e}")
            # Remove from waiting set
            self._waiting_requests.discard(id(request))
            # Retry with exponential backoff
            retry_delay = request.meta.get("retry_delay", 5)
            retry_count = request.meta.get("retry_count", 0)
            
            if retry_count < 3:  # Max 3 retries
                # Create a new request with incremented retry count and delay
                new_request = request.copy()
                new_request.meta["retry_count"] = retry_count + 1
                new_request.meta["retry_delay"] = min(retry_delay * 2, 30)  # Max 30 second delay
                new_request.dont_filter = True
                
                # Log and sleep before retrying
                backoff = retry_delay * (1 + random.random())
                spider.logger.info(f"Retrying request in {backoff:.1f}s (attempt {retry_count+1}/3)")
                time.sleep(backoff)
                
                # Return deferred object to signal retry
                return self.crawler.engine.download(new_request)
            else:
                # Max retries exceeded
                raise IgnoreRequest(f"Selenium session creation failed after 3 retries: {e}")
        
        except NoSuchDriverException as e:
            # Remove from waiting set
            self._waiting_requests.discard(id(request))
            spider.logger.error(f"Driver creation failed: {e}")
            raise IgnoreRequest(f"Driver creation failed: {e}")
        except Exception as e:
            # Remove from waiting set
            self._waiting_requests.discard(id(request))
            spider.logger.error(f"Unexpected error in Selenium middleware: {e}")
            raise IgnoreRequest(f"Selenium error: {e}")
    
    def process_response(self, request, response, spider):
        driver = response.meta.get("driver")
        if driver:
            # Log the session we're handling
            session_id = getattr(driver, 'session_id', 'unknown')
            spider.logger.debug(f"Processing response for Selenium session: {session_id}")
            
            try:
                # Check if driver is still valid before doing anything
                driver.current_url  # This will raise if driver is invalid
                
                # Check if this is a login request with perform_login callback
                is_login_request = request.callback and request.callback.__name__ == 'perform_login'
                
                # Only close custom drivers, return pooled drivers to the pool
                # BUT don't close or release the driver if this is a login request 
                # with perform_login callback as we need to keep the session alive
                if is_login_request:
                    spider.logger.debug(f"Keeping driver {session_id} alive for login process")
                    # Explicitly preserve the driver for the callback
                    response.meta["driver"] = driver
                elif request.meta.get('custom_driver'):
                    spider.logger.debug(f"Closing custom driver with session ID: {session_id}")
                    driver.quit()
                else:
                    spider.logger.debug(f"Returning driver to pool: {session_id}")
                    self.pool.release(driver)
            except WebDriverException as e:
                spider.logger.error(f"Error processing driver in response: {e}")
                # Don't attempt to use the driver anymore
                pass
                
        return response
    
    def process_exception(self, request, exception, spider):
        driver = request.meta.get("driver")
        if driver:
            # Log the session we're handling
            session_id = getattr(driver, 'session_id', 'unknown')
            spider.logger.error(f"Processing exception for Selenium session: {session_id}: {exception}")
            
            try:
                # Check if driver is still valid before doing anything
                driver.current_url  # This will raise if driver is invalid
                
                # Only close custom drivers, return pooled drivers to the pool
                if request.meta.get('custom_driver'):
                    spider.logger.debug(f"Closing custom driver with session ID: {session_id}")
                    driver.quit()
                else:
                    spider.logger.debug(f"Returning driver to pool: {session_id}")
                    self.pool.release(driver)
            except WebDriverException as e:
                spider.logger.error(f"Error processing driver in exception handler: {e}")
                # If driver is invalid, make sure we release the session
                if not request.meta.get('custom_driver') and self.pool:
                    # Explicitly release counter since driver is invalid
                    self.pool._session_counter.release()
                    spider.logger.info("Explicitly released session counter for invalid driver")
        
        # Remove request from waiting set
        self._waiting_requests.discard(id(request))
        
        # Return None to allow other exception handlers to process this
        return None
    
    def _on_spider_closed(self, spider):
        if self.pool:
            self.pool.shutdown()

    def _is_logged_in(self, driver):
        """Check if user is logged in by looking for logout link"""
        try:
            self.logger.debug("DEBUG: Checking if logged in...")
            
            # Add more robust check mechanism
            # First, ensure the page is loaded
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Verify the driver is still valid
            current_url = driver.current_url
            self.logger.debug(f"Current URL: {current_url}")
            
            # Multiple ways to check login status
            is_logged_in = False
            
            # Method 1: Check for logout link
            try:
                logout_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/logout')]"))
                )
                if logout_element:
                    self.logger.info("Login verified - found logout link")
                    is_logged_in = True
            except (TimeoutException, NoSuchElementException):
                self.logger.debug("No logout link found - trying alternative checks")
            
            # Method 2: Check for login-specific content
            if not is_logged_in:
                try:
                    # Look for any element that indicates login (e.g., user profile)
                    logged_in_element = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".user-info, .profile, .account"))
                    )
                    if logged_in_element:
                        self.logger.info("Login verified - found user profile elements")
                        is_logged_in = True
                except (TimeoutException, NoSuchElementException):
                    self.logger.debug("No user profile elements found")
            
            # Method 3: Check for absence of login form
            if not is_logged_in:
                try:
                    # If we can't find login form, we might be logged in
                    driver.find_element(By.ID, "username")
                    self.logger.debug("Login form still present - not logged in")
                    is_logged_in = False
                except NoSuchElementException:
                    if "login" not in current_url.lower():
                        self.logger.info("Login form not found and not on login page - assuming logged in")
                        is_logged_in = True
            
            return is_logged_in
            
        except (TimeoutException, NoSuchElementException) as e:
            self.logger.warning(f"Not logged in: {e}")
            return False
            
        except WebDriverException as e:
            self.logger.error(f"WebDriver error checking login status: {e}")
            # Indicate that login check failed due to driver error
            raise

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
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                
                # Ensure elements are fully interactive before typing
                username_field = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "username"))
                )
                
                # Clear the field first
                username_field.clear()
                time.sleep(0.5)  # Brief pause
                
                # Fill login form with typing delay to mimic human behavior
                self.logger.debug(f"DEBUG: Logging in with username={self.username}, password={self.password}")
                for char in self.username:
                    username_field.send_keys(char)
                    time.sleep(0.05)  # Small delay between characters
                
                # Get password field with wait
                password_field = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "password"))
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
                WebDriverWait(driver, 15).until(EC.url_changes(self.login_url))
                
                # Additional wait to allow page to load completely
                time.sleep(3)
                
                # Check if login was successful
                self.is_logged_in = self._is_logged_in(driver)
                
                if self.is_logged_in:
                    self.logger.info("✅ Login successful!")
                else:
                    self.logger.error("❌ Login failed - UI verification check failed")
                    
            except Exception as e:
                self.logger.error(f"Login automation error: {e}")
                self.is_logged_in = False
        
        # Get cookies from driver and save them immediately to ensure they're not lost
        try:
            if getattr(self, "is_logged_in", False):
                self.cookies = driver.get_cookies()
                self.logger.debug(f"DEBUG: After login, collected {len(self.cookies)} cookies: {self.cookies}")
                
                # Save cookies to Redis immediately to prevent loss
                if hasattr(self, 'spider_closed') and not self.spider_closed:
                    self.save_cookies_to_redis()
        except WebDriverException as e:
            self.logger.error(f"Failed to get cookies: {e}")
        
        # Return to main page for scraping if login succeeded
        if getattr(self, "is_logged_in", False):
            try:
                self.logger.info("Navigating to main page after successful login")
                driver.get(self.start_urls[0])
                return self.parse(response)
            except WebDriverException as e:
                self.logger.error(f"Navigation error after login: {e}")
        
        # Fall back to non-authenticated browsing if login failed
        self.logger.warning("⚠️ Login failed - falling back to public pages")
        return scrapy.Request(
            self.start_urls[0],
            callback=self.parse,
            meta={"selenium": True, "wait_time": 10},
            dont_filter=True
        )