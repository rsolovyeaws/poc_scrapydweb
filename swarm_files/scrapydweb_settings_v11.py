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

# Disable features you don't need for PoC
TIMER_TASKS = False
TIMER_RUNS = False
JOBS_RELOAD_INTERVAL = 10
DELETE_JOBS = False

# Set a reasonable limit for a PoC
JOBS_FINISHED_JOBS_LIMIT = 100

# Disable monitor to avoid database requirements
ENABLE_MONITOR = False

# Essential for SQLAlchemy to work - fix for the "metadata bind" error
SQLALCHEMY_DATABASE_URI = 'sqlite:////app/data/scrapydweb.db'
SQLALCHEMY_BINDS = {
    'metadata': 'sqlite:////app/data/metadata.db',
    'jobs': 'sqlite:////app/data/jobs.db'
}

# Secret key for session management
SECRET_KEY = 'scrapydweb-poc-secret-key-2025'