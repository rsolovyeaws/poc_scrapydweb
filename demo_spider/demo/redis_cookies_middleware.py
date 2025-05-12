"""
demo/redis_cookies_middleware.py
────────────────────────────────────────────────────────────────────────────
RedisCookiesMiddleware
• Loads cookies at spider start from Redis
• Saves cookies to Redis at spider close
• Provides a more scalable and distributed storage for cookies
"""

import json
import redis
from scrapy import signals
from scrapy.exceptions import NotConfigured


class RedisCookiesMiddleware:
    def __init__(self, settings):
        self.redis_host = settings.get("REDIS_HOST", "redis")
        self.redis_port = settings.get("REDIS_PORT", 6379)
        self.redis_db = settings.get("REDIS_DB", 0)
        self.redis_password = settings.get("REDIS_PASSWORD", None)
        self.redis_key_prefix = settings.get("REDIS_COOKIES_KEY_PREFIX", "scrapy:cookies:")
        self.enabled = settings.getbool("REDIS_COOKIES_ENABLED", True)
        
        # Connect to Redis
        if self.enabled:
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    decode_responses=False  # Keep as bytes for pickle compatibility
                )
                # Test connection
                self.redis_client.ping()
            except Exception as e:
                raise NotConfigured(f"Redis connection error: {e}")

    # ─────────────────────────── Scrapy hooks ──────────────────────────
    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("REDIS_COOKIES_ENABLED", True):
            raise NotConfigured("Redis cookies middleware is disabled")
        mw = cls(crawler.settings)
        crawler.signals.connect(mw.spider_opened, signals.spider_opened)
        crawler.signals.connect(mw.spider_closed, signals.spider_closed)
        return mw

    # ─────────────────────────── helpers ───────────────────────────────
    def _get_key(self, spider):
        """Generate a unique Redis key for this spider"""
        return f"{self.redis_key_prefix}{spider.name}"

    # ─────────────────────────── events ────────────────────────────────
    def spider_opened(self, spider):
        """Load cookies from Redis when spider starts"""
        key = self._get_key(spider)
        try:
            cookies_data = self.redis_client.get(key)
            if cookies_data:
                spider.cookies = json.loads(cookies_data)
                spider.logger.info(f"Loaded {len(spider.cookies)} cookies from Redis")
            else:
                spider.cookies = []
                spider.logger.info("No cookies found in Redis")
                
                # Debug: Add a test cookie to redis to verify it works
                test_cookies = [
                    {
                        "name": "test_cookie",
                        "value": "test_value",
                        "domain": "quotes.toscrape.com",
                        "path": "/"
                    }
                ]
                self.redis_client.set(key, json.dumps(test_cookies))
                spider.logger.debug(f"DEBUG: Added test cookie to Redis with key {key}")
                
                # Verify it was added
                saved = self.redis_client.get(key)
                if saved:
                    spider.logger.debug(f"DEBUG: Test cookie successfully stored in Redis")
                    spider.cookies = json.loads(saved)
                else:
                    spider.logger.error("DEBUG: Failed to store test cookie in Redis")
                
        except Exception as exc:
            spider.logger.error(f"Redis cookie load error: {exc}")
            spider.cookies = []

    def spider_closed(self, spider):
        """
        Save cookies to Redis when spider closes
        Only if the WebDriver session is still reachable
        """
        driver = getattr(spider, "selenium_driver", None)

        # 1. driver attr missing or already quit → skip saving
        if driver is None or getattr(driver, "session_id", None) is None:
            spider.logger.debug("DEBUG: Cannot save cookies - driver not available")
            return

        # 2. lightweight ping to confirm the session is still alive
        try:
            driver.execute("getLog", {"type": "browser"})
        except Exception as e:
            spider.logger.debug(f"DEBUG: Cannot save cookies - driver session gone: {e}")
            return

        # 3. session alive → store cookies in Redis
        try:
            cookies = driver.get_cookies() or []
            spider.logger.debug(f"DEBUG: Got {len(cookies)} cookies from driver")
            if cookies:
                key = self._get_key(spider)
                self.redis_client.set(key, json.dumps(cookies))
                spider.logger.info(f"Saved {len(cookies)} cookies to Redis with key {key}")
                
                # Verify it was saved
                saved = self.redis_client.get(key)
                if saved:
                    spider.logger.debug("DEBUG: Cookies successfully verified in Redis")
                else:
                    spider.logger.error("DEBUG: Failed to verify cookies in Redis")
            else:
                spider.logger.warning("No cookies to save from driver")
        except Exception as exc:
            spider.logger.error(f"Redis cookie save error: {exc}")

    def update_cookies(self, spider_name, cookies):
        """
        API method to update cookies for a specific spider
        This can be called from external code to manipulate the cookie store
        """
        if not cookies:
            return False
            
        try:
            key = f"{self.redis_key_prefix}{spider_name}"
            self.redis_client.set(key, json.dumps(cookies))
            return True
        except Exception:
            return False
            
    def get_cookies(self, spider_name):
        """
        API method to retrieve cookies for a specific spider
        This can be called from external code to access the cookie store
        """
        try:
            key = f"{self.redis_key_prefix}{spider_name}"
            cookies_data = self.redis_client.get(key)
            if cookies_data:
                return json.loads(cookies_data)
            return []
        except Exception:
            return []

    def delete_cookies(self, spider_name):
        """
        API method to delete cookies for a specific spider
        This can be called from external code to manipulate the cookie store
        """
        try:
            key = f"{self.redis_key_prefix}{spider_name}"
            self.redis_client.delete(key)
            return True
        except Exception:
            return False 