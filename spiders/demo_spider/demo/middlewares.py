"""
demo/middlewares.py
────────────────────────────────────────────────────────────────────────────
PersistentCookiesMiddleware
• Loads cookies at spider start (if they exist on disk).
• Saves cookies at spider close—but only while the Selenium session is
  still alive, covering BOTH local and remote WebDriver instances.
"""

import os
import pickle
from pathlib import Path

from scrapy import signals
from scrapy.exceptions import NotConfigured


class PersistentCookiesMiddleware:
    def __init__(self, settings):
        self.dir = settings.get("COOKIES_PERSISTENCE_DIR", "/data/cookies")
        self.enabled = settings.getbool("COOKIES_PERSISTENCE_ENABLED", True)
        if self.enabled:
            Path(self.dir).mkdir(parents=True, exist_ok=True)

    # ─────────────────────────── Scrapy hooks ──────────────────────────
    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("COOKIES_PERSISTENCE_ENABLED", True):
            raise NotConfigured
        mw = cls(crawler.settings)
        crawler.signals.connect(mw.spider_opened, signals.spider_opened)
        crawler.signals.connect(mw.spider_closed, signals.spider_closed)
        return mw

    # ─────────────────────────── helpers ───────────────────────────────
    def _filepath(self, spider):
        return os.path.join(self.dir, f"{spider.name}_cookies.pkl")

    # ─────────────────────────── events ────────────────────────────────
    def spider_opened(self, spider):
        fp = self._filepath(spider)
        if os.path.exists(fp):
            try:
                with open(fp, "rb") as fh:
                    spider.cookies = pickle.load(fh)
                spider.logger.info(f"Loaded {len(spider.cookies)} cookies")
            except Exception as exc:  # noqa: BLE001
                spider.logger.error(f"Cookie load error: {exc}")
                spider.cookies = []
        else:
            spider.cookies = []

    def spider_closed(self, spider):
        """
        Save cookies only if the WebDriver session is still reachable.
        Works for both local (Chrome/Gecko) and remote drivers.
        """
        driver = getattr(spider, "selenium_driver", None)

        # 1. driver attr missing or already quit → skip saving
        if driver is None or getattr(driver, "session_id", None) is None:
            return

        # 2. lightweight ping to confirm the session is still alive
        try:
            driver.execute("getLog", {"type": "browser"})
        except Exception:  # session is gone (local or remote)
            return

        # 3. session alive → dump cookies
        try:
            cookies = driver.get_cookies() or []
            if cookies:
                with open(self._filepath(spider), "wb") as fh:
                    pickle.dump(cookies, fh)
                spider.logger.info(f"Saved {len(cookies)} cookies")
        except Exception as exc:  # noqa: BLE001
            spider.logger.error(f"Cookie save error: {exc}")
