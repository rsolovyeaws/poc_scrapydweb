SCRAPYD_SERVERS = [
    # Format: (group, name, host:port, auth, priority)
    ('group1', 'scrapyd1', 'scrapyd1', None, 0),
    ('group2', 'scrapyd2', 'scrapyd2', None, 0)
]

# Optional: Enable load balancing between instances
SCHEDULER_PRIORITY_QUEUE = 'random'  # or 'random' for round-robin
ENABLE_MULTINODE_MANAGEMENT = True