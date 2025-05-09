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
# --- S3/MinIO Storage Settings ---
S3_ENDPOINT_URL = 'http://minio:9000'
S3_ACCESS_KEY = 'minio_user'
S3_SECRET_KEY = 'minio_password'
S3_BUCKET_NAME = 'scraper-results'
S3_FOLDER_NAME = 'scraped_data'
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
# Item pipelines
ITEM_PIPELINES = {
    "demo.pipelines.PostgresPipeline": 300,
    "demo.pipelines.S3StoragePipeline": 400,
}
# Cookie persistence settings
COOKIES_PERSISTENCE_ENABLED = True
COOKIES_PERSISTENCE_DIR = '/data/cookies'
ROBOTSTXT_OBEY = False
LOG_LEVEL = "INFO"

# Default proxy settings - can be overridden by spider parameters
# PROXY = None  # e.g. "http://tinyproxy:8888"