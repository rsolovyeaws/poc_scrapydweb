# Minimal ScrapydWeb settings for PoC
# This version disables most advanced features to focus on core functionality

############################## QUICK SETUP start ##############################

# Setting SCRAPYDWEB_BIND to '0.0.0.0' makes ScrapydWeb server visible externally
SCRAPYDWEB_BIND = '0.0.0.0'
SCRAPYDWEB_PORT = 5000

# List of Scrapyd servers to connect to
SCRAPYD_SERVERS = [
    ('scrapyd-1', 'scrapyd_1', '6800', '', False),
    ('scrapyd-2', 'scrapyd_2', '6800', '', False),
]

############################## QUICK SETUP end ##############################

# Essential database configuration
SQLALCHEMY_DATABASE_URI = 'sqlite:////app/data/scrapydweb.db'
SQLALCHEMY_BINDS = {
    'metadata': 'sqlite:////app/data/metadata.db',
    'jobs': 'sqlite:////app/data/jobs.db'
}

# Simplify configuration - disable all features that might cause issues
ENABLE_EMAIL = False
ENABLE_AUTH = False
ENABLE_MONITOR = False
DELETE_CACHE = 0
ENABLE_LOGPARSER = False

# Disable features that might depend on database
JOBS_RELOAD_INTERVAL = 300  # Longer interval to reduce load
ENABLE_CACHE = False

# Secret key for session management
SECRET_KEY = 'scrapydweb-poc-minimal-config'