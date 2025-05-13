"""
Selenium middleware (remote-hub friendly) with driver pool ✔
"""
import queue
import time
from urllib.parse import urlparse
from scrapy import signals
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.common.exceptions import NoSuchDriverException, WebDriverException
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

class _DriverPool:
    """Thread-safe pool."""
    def __init__(self, size, make_driver, spider):
        self._size = size
        self._make = make_driver
        self._spider = spider
        self._q = queue.Queue(maxsize=size)
        self._all = []
        for _ in range(size):
            d = self._spawn()
            self._q.put(d)
            self._all.append(d)
    
    def _spawn(self):
        d = self._make()
        if getattr(self._spider, "cookies", None):
            dom = urlparse(self._spider.start_urls[0]).netloc
            _inject_cookies(d, self._spider.cookies, dom, self._spider.logger)
        return d
    
    def acquire(self):
        return self._q.get()
    
    def release(self, d):
        try:
            # Check if driver is still valid before returning to pool
            d.current_url  # This will raise if driver is invalid
            self._q.put(d)
        except WebDriverException:
            # If driver is invalid, create a new one
            self._spider.logger.debug("Driver is invalid, creating a new one for pool")
            d = self._make()
            self._q.put(d)
            
    def shutdown(self):
        for d in self._all:
            try:
                d.quit()
            except Exception:  # noqa: BLE001
                pass
        self._all.clear()
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
        
        pool = self._pool(spider)
        
        try:
            # Get User-Agent from request headers
            user_agent = None
            if 'User-Agent' in request.headers:
                user_agent = request.headers['User-Agent'].decode('utf-8')
            
            # Create and manage driver
            if user_agent:
                spider.logger.info(f"Applying User-Agent to Selenium: {user_agent}")
                driver = self._spawn_driver(spider, user_agent)
                request.meta['custom_driver'] = True
            else:
                driver = pool.acquire()
                request.meta['custom_driver'] = False
            
            # Important: Store the session ID for debugging
            request.meta['selenium_session_id'] = driver.session_id
            spider.logger.debug(f"Using Selenium session ID: {driver.session_id}")
            
            # Store driver in spider for access in callbacks
            spider.set_selenium_driver(driver)
            
            # Log navigation
            spider.logger.debug(f"Selenium navigating to {request.url}")
            
            # Do the actual navigation
            try:
                driver.get(request.url)
                time.sleep(request.meta.get("wait_time", 2))  # Increased default wait time
            except WebDriverException as e:
                spider.logger.error(f"WebDriver error during navigation: {e}")
                raise IgnoreRequest(f"WebDriver error: {e}")
            
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
            
            return response
            
        except NoSuchDriverException as e:
            spider.logger.error(f"Driver creation failed: {e}")
            raise IgnoreRequest(f"Driver creation failed: {e}")
        except Exception as e:
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
            spider.logger.error(f"Processing exception for Selenium session: {session_id}")
            
            try:
                # Only close custom drivers, return pooled drivers to the pool
                if request.meta.get('custom_driver'):
                    spider.logger.debug(f"Closing custom driver in exception handler: {session_id}")
                    driver.quit()
                else:
                    spider.logger.debug(f"Returning driver to pool in exception handler: {session_id}")
                    self.pool.release(driver)
            except WebDriverException as e:
                spider.logger.error(f"Error handling driver in exception handler: {e}")
                # Don't attempt to use the driver anymore
        
        # We must propagate the exception
        raise IgnoreRequest(f"Selenium request failed: {exception}")
    
    def _on_spider_closed(self, spider):
        if self.pool:
            spider.logger.info("Shutting down Selenium driver pool")
            self.pool.shutdown()