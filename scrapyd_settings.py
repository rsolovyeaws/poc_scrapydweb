"""
Scrapyd settings with Prometheus metrics exporter enabled
"""

# Scrapyd standard settings
max_proc = 0
max_proc_per_cpu = 4
debug = False
eggs_dir = '/root/.scrapyd/eggs'
dbs_dir = '/root/.scrapyd/dbs'
logs_dir = '/root/.scrapyd/logs'
items_dir = '/root/.scrapyd/items'

# Enable the Prometheus exporter extension
EXTENSIONS = {
    'scrapy_prometheus_exporter.prometheus.WebService': 500,
}

# Prometheus exporter settings
PROMETHEUS_ENABLED = True
PROMETHEUS_PORT = 9410
PROMETHEUS_HOST = '0.0.0.0'
PROMETHEUS_PATH = 'metrics'
PROMETHEUS_UPDATE_INTERVAL = 5

# Include our custom metrics middleware
SPIDER_MIDDLEWARES = {
    'custom_middleware.metrics_middleware.PrometheusMetricsMiddleware': 543,
} 