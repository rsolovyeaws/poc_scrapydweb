# Demo Spider with User-Agent Rotation

This Scrapy project demonstrates advanced scraping techniques including User-Agent rotation.

## Features

- Selenium integration for handling JavaScript-heavy sites
- Cookie persistence with Redis
- User-Agent rotation to avoid detection
- Integration with PostgreSQL and S3 storage
- Support for proxy servers

## User-Agent Rotation

The project now includes User-Agent rotation capabilities:

1. A new `UserAgentRotationMiddleware` is added that fetches random User-Agents from a dedicated service
2. The `ua-rotator` service provides User-Agents via REST API
3. The `SeleniumMiddleware` is updated to apply User-Agents to Selenium WebDriver sessions
4. Each request can specify a User-Agent type (desktop, mobile, tablet)

## Usage

### Command Line Parameters

```bash
# Run with User-Agent rotation
scrapy crawl quotes_spa -a user_agent_type=desktop

# Available types: desktop, mobile, tablet
scrapy crawl quotes_spa -a user_agent_type=mobile
```

### In Script

```python
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

process = CrawlerProcess(get_project_settings())
process.crawl('quotes_spa', user_agent_type='desktop')
process.start()
```

### With Docker

```bash
docker-compose up -d
```

## Configuration

Settings in `settings.py`:

```python
# User-Agent Rotation Settings
USER_AGENT_ROTATION_ENABLED = True
USER_AGENT_SERVICE_URL = 'http://ua-rotator:5000'

# Middleware
DOWNLOADER_MIDDLEWARES = {
    "demo.user_agent_middleware.UserAgentRotationMiddleware": 750,
    "demo.custom_selenium_middleware.SeleniumMiddleware": 800,
    # ...
}
```

## Testing

You can test the User-Agent rotation with the provided scripts:

```bash
# Test the User-Agent service directly
./test_user_agent.py --count 5 --type mobile

# Run a spider with User-Agent rotation through the load balancer
./test_balancer.sh --user-agent-type mobile
``` 