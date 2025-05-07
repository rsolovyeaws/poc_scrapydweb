-- init-db/01-init.sql
-- Create schema for organizing scraping data
CREATE SCHEMA IF NOT EXISTS scrapers;

-- Create a master table to track all spider runs
CREATE TABLE IF NOT EXISTS spider_runs (
    id SERIAL PRIMARY KEY,
    spider_name TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT,
    items_scraped INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

-- Create a table to store configuration for spiders
CREATE TABLE IF NOT EXISTS spider_config (
    id SERIAL PRIMARY KEY,
    spider_name TEXT UNIQUE NOT NULL,
    schedule TEXT,  -- Cron expression for scheduling
    settings JSONB,  -- Spider-specific settings
    enabled BOOLEAN DEFAULT TRUE,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create a table to store project metadata
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create a function to automatically add timestamp to tables
CREATE OR REPLACE FUNCTION update_last_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to update last_modified in spider_config
CREATE TRIGGER update_spider_config_last_modified
BEFORE UPDATE ON spider_config
FOR EACH ROW
EXECUTE FUNCTION update_last_modified_column();

-- Add trigger to update last_modified in projects
CREATE TRIGGER update_projects_last_modified
BEFORE UPDATE ON projects
FOR EACH ROW
EXECUTE FUNCTION update_last_modified_column();