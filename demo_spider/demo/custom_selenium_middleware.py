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
from selenium.common.exceptions import NoSuchDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions


# ───────── helpers ─────────────────────────────────────────────────────────
def _inject_cookies(driver, cookies, domain, log):
    if not cookies:
        return
    driver.get(f"https://{domain}")
    time.sleep(0.3)
    added = 0
    for c in cookies:
        try:
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
            d.refresh()
        return d

    def acquire(self):
        return self._q.get()

    def release(self, d):
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
    def _make_options(self):
        o = ChromeOptions()
        for a in self.driver_args:
            o.add_argument(a)
        o.add_argument("--no-sandbox")
        o.add_argument("--disable-dev-shm-usage")
        return o

    def _spawn_driver(self):
        return webdriver.Remote(
            command_executor=self.command_executor,
            options=self._make_options(),
        )

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
            self.pool = _DriverPool(self.pool_size, self._spawn_driver, spider)
        return self.pool

    # ---- request / response hooks ---------------------------------------
    def process_request(self, request, spider):
        if not request.meta.get("selenium"):
            return None

        pool = self._pool(spider)
        try:
            driver = pool.acquire()
        except NoSuchDriverException as exc:
            raise IgnoreRequest from exc

        # put driver into spider for convenience
        spider.set_selenium_driver(driver)

        driver.get(request.url)
        time.sleep(request.meta.get("wait_time", 0))

        body = driver.page_source.encode()
        response = HtmlResponse(driver.current_url, body=body, encoding="utf-8", request=request)
        response.meta["driver"] = driver  # for callbacks
        return response

    def process_response(self, request, response, spider):
        driver = response.meta.get("driver")
        if driver:
            self.pool.release(driver)
        return response

    def process_exception(self, request, exception, spider):
        driver = request.meta.get("driver")
        if driver:
            self.pool.release(driver)
        raise IgnoreRequest from exception

    def _on_spider_closed(self, spider):
        if self.pool:
            self.pool.shutdown()
