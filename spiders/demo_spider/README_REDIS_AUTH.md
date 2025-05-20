# Redis-Based Authentication for Scrapy Spiders

This enhancement improves the session and cookie management in the demo spider by using Redis for persistent storage of authentication credentials.

## Features Added

1. **Redis-Based Cookie Storage**
   - Cookies and session data are now stored in Redis instead of local files
   - This enables sharing authentication state across multiple spider instances
   - Makes the system more scalable and resilient

2. **Enhanced API for Session Management**
   - Added methods to programmatically manage cookies outside of the spider lifecycle
   - Simplifies integration with external systems
   - Provides a foundation for a session management API service

3. **Cookie Command-Line Tool**
   - Example script for managing cookies using command-line interface
   - Demonstrates how to use the Redis cookie API

## Setup

### 1. Requirements

The Redis integration requires the `redis` Python package, which has been added to `requirements.txt`:

```
redis==5.0.1
```

### 2. Configuration

Add the following to your docker-compose.yml:

```yaml
redis:
  image: redis:alpine
  container_name: scraper-redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  networks:
    - scraper-network
```

Don't forget to add the volume at the bottom of the file:

```yaml
volumes:
  # ... other volumes
  redis_data:
```

### 3. Spider Configuration

The `quotes_spa` spider has been updated with Redis configuration:

```python
custom_settings = {
    # ... existing settings

    # Middleware configuration
    "DOWNLOADER_MIDDLEWARES": {
        "demo.custom_selenium_middleware.SeleniumMiddleware": 800,
        "demo.redis_cookies_middleware.RedisCookiesMiddleware": 900,
    },

    # Redis settings
    "REDIS_HOST": "redis",
    "REDIS_PORT": 6379,
    "REDIS_DB": 0,
    "REDIS_COOKIES_ENABLED": True,
    "REDIS_COOKIES_KEY_PREFIX": "scrapy:cookies:",
}
```

## Files Added

1. `demo/redis_cookies_middleware.py` - Redis-based cookie persistence middleware
2. `demo/cookie_api_example.py` - Command-line tool for managing cookies

## Usage

### Running the Spider

The spider can be run as before - no changes to the command-line arguments:

```bash
scrapy crawl quotes_spa
```

### Managing Cookies via CLI

The cookie management tool provides a command-line interface for managing cookies:

```bash
# List cookies for a spider
python -m demo.cookie_api_example --host redis list quotes_spa

# Add a cookie
python -m demo.cookie_api_example --host redis add quotes_spa session_id ABC123 quotes.toscrape.com

# Delete all cookies for a spider
python -m demo.cookie_api_example --host redis delete quotes_spa

# Export cookies to a JSON file
python -m demo.cookie_api_example --host redis export quotes_spa cookies.json

# Import cookies from a JSON file
python -m demo.cookie_api_example --host redis import quotes_spa cookies.json
```

## Integration Ideas

The Redis-based cookie storage can be leveraged for:

1. **Central Authentication Service**
   - Build a web API to manage sessions across multiple spiders
   - Allow external systems to update authentication tokens

2. **Token Refresh**
   - Implement a background service that refreshes authentication tokens
   - Keep sessions alive between spider runs

3. **Cross-Instance Sharing**
   - Share authentication state between different spider instances
   - Scale out crawling operations while maintaining login state 