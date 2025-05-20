#!/usr/bin/env python3
import os
from typing import Dict, Any

# RabbitMQ settings
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "scraper_tasks")

# Scrapyd settings
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:5000")

# Reconnect settings
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "5"))

# Default spider settings
DEFAULT_SPIDER_SETTINGS: Dict[str, Any] = {
    "LOG_LEVEL": "INFO",
    "CONCURRENT_REQUESTS": 16,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    "RETRY_TIMES": 3,
    "DOWNLOAD_TIMEOUT": 180,
    "COOKIES_ENABLED": True,
    "TELNETCONSOLE_ENABLED": False,
}

# Message processing settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "60")) 