"""
quotes_spa spider – now respects ?auth_enabled=... and stores results in S3
"""
import time, scrapy
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
        "SELENIUM_DRIVER_POOL_SIZE": 3,
        # middlewares
        "DOWNLOADER_MIDDLEWARES": {
            "demo.custom_selenium_middleware.SeleniumMiddleware": 800,
            "demo.middlewares.PersistentCookiesMiddleware": 900,
        },
        # pipelines
        "ITEM_PIPELINES": {
            "demo.pipelines.PostgresPipeline": 300,
            "demo.pipelines.S3StoragePipeline": 400,
        },
        # S3 specific settings (can override project settings)
        "S3_FOLDER_NAME": "quotes_data",
        # misc
        "COOKIES_PERSISTENCE_ENABLED": True,
        "COOKIES_PERSISTENCE_DIR": "/data/cookies",
        "CONCURRENT_REQUESTS": 3,
        "CLOSESPIDER_PAGECOUNT": 0,
    }
    # ─── ctor ────────────────────────────────────────────────────────────
    def __init__(self, username=None, password=None, auth_enabled="true", proxy=None, *a, **kw):
        super().__init__(*a, **kw)
        self.username = username or "admin"
        self.password = password or "admin"
        self.auth_enabled = str(auth_enabled).lower() != "false"
        self.proxy = proxy  # Store proxy parameter
        if self.proxy:
            self.logger.info(f"Proxy configured: {self.proxy}")
        
        self.cookies, self.selenium_driver = [], None
        self.is_logged_in = False
        self.current_url = self.start_urls[0]  # Initialize with start URL
    
    # set by middleware
    def set_selenium_driver(self, driver):
        self.selenium_driver = driver
    
    # ─── entry point ─────────────────────────────────────────────────────
    def start_requests(self):
        # Prepare meta with common settings
        meta = {"selenium": True, "wait_time": 1}
        
        # Add proxy to meta if specified
        if self.proxy:
            meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
        
        if self.auth_enabled:
            self.logger.info("Authentication enabled → hitting login page")
            yield scrapy.Request(
                self.login_url,
                self.perform_login,
                meta=meta,
                dont_filter=True,
            )
        else:
            self.logger.info("Authentication disabled → going straight to quotes")
            yield scrapy.Request(
                self.start_urls[0],
                self.parse,
                meta=meta,
                dont_filter=True,
            )
    
    # ─── login flow (only when auth_enabled) ─────────────────────────────
    def perform_login(self, response):
        driver = response.meta["driver"]
        # cookies from previous run?
        if self.cookies:
            self.is_logged_in = self._is_logged_in(driver)
            if self.is_logged_in:
                self.logger.info("Cookie jar already logged in")
        # else try form login
        if not self.is_logged_in:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                driver.find_element(By.ID, "username").send_keys(self.username)
                driver.find_element(By.ID, "password").send_keys(self.password)
                driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                WebDriverWait(driver, 5).until(EC.url_changes(self.login_url))
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Login automation error: {e}")
            self.is_logged_in = self._is_logged_in(driver)
        self.cookies = driver.get_cookies()
        
        # Prepare meta with common settings
        meta = {"selenium": True, "wait_time": 1}
        
        # Add proxy to meta if specified
        if self.proxy:
            meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
            
        yield scrapy.Request(
            self.start_urls[0],
            self.parse,
            meta=meta,
            dont_filter=True,
        )
    
    def _is_logged_in(self, driver):
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/logout')]"))
            )
            self.logger.info("Login verified")
            return True
        except (TimeoutException, NoSuchElementException):
            self.logger.warning("Not logged in")
            return False
    
    # ─── parse quotes pages ──────────────────────────────────────────────
    def parse(self, response):
        # Update current URL (used by S3 pipeline for filename)
        self.current_url = response.url
        
        for q in response.css("div.quote"):
            yield {
                "text": q.css("span.text::text").get(),
                "author": q.css("small.author::text").get(),
                "tags": q.css("div.tags a.tag::text").getall(),
                "url": response.url,
            }
        
        next_rel = response.css("li.next a::attr(href)").get()
        if next_rel:
            # Prepare meta with common settings
            meta = {"selenium": True, "wait_time": 1}
            
            # Add proxy to meta if specified
            if self.proxy:
                meta['proxy'] = self.proxy  # For standard Scrapy proxy middleware
                
            yield scrapy.Request(
                response.urljoin(next_rel),
                self.parse,
                meta=meta,
            )