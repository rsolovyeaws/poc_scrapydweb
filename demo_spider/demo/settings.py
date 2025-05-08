BOT_NAME = "demo"

SPIDER_MODULES = ["demo.spiders"]
NEWSPIDER_MODULE = "demo.spiders"

# Set settings whose default value is deprecated to a future-proof value
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Database settings
POSTGRES_DB = 'scraper_data'
POSTGRES_USER = 'scraper_user'
POSTGRES_PASSWORD = 'scraper_password'
POSTGRES_HOST = 'postgres'
POSTGRES_PORT = 5432

# --- Selenium (remote hub) ---
SELENIUM_DRIVER_NAME = "remote"
SELENIUM_COMMAND_EXECUTOR = "http://selenium-hub:4444/wd/hub"  # Use container name in docker network
# SELENIUM_COMMAND_EXECUTOR = "http://localhost:4444/wd/hub"
SELENIUM_DRIVER_ARGUMENTS = [
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
]
SELENIUM_DRIVER_CAPABILITIES = {
    "browserName": "chrome",
    "platformName": "linux",
}

# Use our custom middleware
DOWNLOADER_MIDDLEWARES = {
    "demo.custom_selenium_middleware.SeleniumMiddleware": 800,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750
}

# Cookie persistence settings
COOKIES_PERSISTENCE_ENABLED = True
COOKIES_PERSISTENCE_DIR = '/data/cookies'

ROBOTSTXT_OBEY = False
LOG_LEVEL = "INFO"