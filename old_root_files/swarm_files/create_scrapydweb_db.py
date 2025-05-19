#!/usr/bin/env python3

import os
import sqlite3

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# Create the metadata database
metadata_db_path = 'data/metadata.db'
jobs_db_path = 'data/jobs.db'
scrapydweb_db_path = 'data/scrapydweb.db'

# SQL for creating the metadata table
metadata_sql = '''
CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT,
    last_check_update_timestamp TEXT,
    main_pid INTEGER,
    logparser_pid INTEGER,
    poll_pid INTEGER,
    pageview INTEGER DEFAULT 0,
    url_scrapydweb TEXT,
    url_jobs TEXT,
    url_schedule_task TEXT,
    url_delete_task_result TEXT,
    username TEXT,
    password TEXT,
    scheduler_state TEXT DEFAULT 'RUNNING',
    jobs_per_page INTEGER DEFAULT 100,
    tasks_per_page INTEGER DEFAULT 100,
    jobs_style TEXT DEFAULT 'card'
);

-- Insert initial metadata record
INSERT OR IGNORE INTO metadata (
    version, scheduler_state, jobs_per_page, tasks_per_page, jobs_style
) VALUES (
    '1.6.0', 'RUNNING', 100, 100, 'card'
);
'''

# SQL for creating the jobs table
jobs_sql = '''
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node INTEGER,
    project TEXT,
    spider TEXT,
    job TEXT,
    status TEXT,
    start TEXT,
    end TEXT,
    duration TEXT,
    pages_num INTEGER DEFAULT 0
);
'''

print("Creating ScrapydWeb database files...")

# Create and initialize metadata.db
conn_metadata = sqlite3.connect(metadata_db_path)
conn_metadata.executescript(metadata_sql)
conn_metadata.commit()
conn_metadata.close()
print(f"Created and initialized {metadata_db_path}")

# Create and initialize jobs.db
conn_jobs = sqlite3.connect(jobs_db_path)
conn_jobs.executescript(jobs_sql)
conn_jobs.commit()
conn_jobs.close()
print(f"Created and initialized {jobs_db_path}")

# Create empty scrapydweb.db (main db)
conn_main = sqlite3.connect(scrapydweb_db_path)
conn_main.close()
print(f"Created empty {scrapydweb_db_path}")

print("Setting permissions...")
os.system("sudo chmod -R 777 data")

print("ScrapydWeb database initialization complete!")