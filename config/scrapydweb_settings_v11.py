import os

SCRAPYD_SERVERS = [
    # Format: (group, name, host:port, auth, priority)
    ('group1', 'scrapyd1', 'scrapyd1', None, 0),
    ('group2', 'scrapyd2', 'scrapyd2', None, 0)
]

# Optional: Enable load balancing between instances
SCHEDULER_PRIORITY_QUEUE = 'random'  # or 'random' for round-robin
ENABLE_MULTINODE_MANAGEMENT = True

# Telegram notification settings
# Bot token should be in format like: 123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Chat ID should be a user or group chat ID, NOT the bot's ID
# For group chats, make sure to include the negative sign if applicable
# Example: -123456789 for a group or 123456789 for a user
TELEGRAM_CHAT_ID = int(os.environ.get('TELEGRAM_CHAT_ID', 0))

# Enable Telegram alert
ENABLE_TELEGRAM_ALERT = True

# Job monitoring settings
ENABLE_MONITOR = True 
POLL_ROUND_INTERVAL = 60  # Check jobs every 60 seconds
POLL_REQUEST_INTERVAL = 10  # 10 seconds between requests while polling

# Alert triggers for job events
ON_JOB_RUNNING_INTERVAL = 0  # Don't send alerts for running jobs
ON_JOB_FINISHED = True  # Send alert when job finishes

# Log level triggers
LOG_CRITICAL_THRESHOLD = 1  # Alert after 1 critical log
LOG_ERROR_THRESHOLD = 5  # Alert after 5 errors
LOG_WARNING_THRESHOLD = 10  # Alert after 10 warnings

# Working time for alerts (24/7)
ALERT_WORKING_DAYS = [1, 2, 3, 4, 5, 6, 7]  # Monday to Sunday
ALERT_WORKING_HOURS = list(range(24))  # 0 to 23 hours