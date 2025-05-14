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
        
        # Add proxy if provided in spider settings
        if spider and hasattr(spider, 'proxy') and spider.proxy:
            o.add_argument(f'--proxy-server={spider.proxy}')
            spider.logger.debug(f"Selenium using proxy: {spider.proxy}")
        
        return o
    
    def _spawn_driver(self, spider=None, user_agent=None):
        spider.logger.debug("Creating new Selenium driver")
        driver = webdriver.Remote(
            command_executor=self.command_executor,
            options=self._make_options(spider, user_agent),
        )
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
        
        # Check if we already processed this request
        if id(request) in self._waiting_requests:
            spider.logger.debug(f"Request {id(request)} already being processed")
            return None
        
        pool = self._pool(spider)
        spider.logger.info(f"Active Selenium sessions: {pool.get_active_count()}/{self.pool_size}")
        
        # Mark this request as being processed
        self._waiting_requests.add(id(request))
        
        try:
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
                
                # Log navigation
                spider.logger.debug(f"Selenium navigating to {request.url}")
                
                # Do the actual navigation with retry logic
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        driver.get(request.url)
                        # Increased wait time to ensure page loads
                        wait_time = request.meta.get("wait_time", 3)
                        time.sleep(wait_time)
                        break
                    except WebDriverException as e:
                        spider.logger.error(f"WebDriver error during navigation (attempt {attempt+1}): {e}")
                        if attempt < max_retries - 1:
                            # Add jitter to retry delay
                            jitter = random.uniform(0.5, 1.5)
                            sleep_time = 2 * (attempt + 1) * jitter
                            spider.logger.info(f"Retrying navigation in {sleep_time:.2f} seconds...")
                            time.sleep(sleep_time)
                        else:
                            raise IgnoreRequest(f"WebDriver error after {max_retries} attempts: {e}")
                
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
                
                # Only close custom drivers, return pooled drivers to the pool
                if request.meta.get('custom_driver'):
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