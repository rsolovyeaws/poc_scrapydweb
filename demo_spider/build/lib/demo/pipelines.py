# demo/pipelines.py
import psycopg2
import json
from datetime import datetime

class PostgresPipeline:
    def __init__(self, db_settings):
        self.db_settings = db_settings
        self.connection = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        db_settings = {
            'dbname': crawler.settings.get('POSTGRES_DB', 'scraper_data'),
            'user': crawler.settings.get('POSTGRES_USER', 'scraper_user'),
            'password': crawler.settings.get('POSTGRES_PASSWORD', 'scraper_password'),
            'host': crawler.settings.get('POSTGRES_HOST', 'postgres'),
            'port': crawler.settings.get('POSTGRES_PORT', 5432),
        }
        return cls(db_settings)

    def open_spider(self, spider):
        self.connection = psycopg2.connect(**self.db_settings)
        self.cursor = self.connection.cursor()
        
        # Create table if it doesn't exist
        # This is a dynamic approach that creates tables based on spider name
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {spider.name}_data (
            id SERIAL PRIMARY KEY,
            url TEXT,
            spider_name TEXT,
            data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        self.connection.commit()

    def close_spider(self, spider):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def process_item(self, item, spider):
        # Add metadata
        enriched_item = dict(item)
        enriched_item['crawl_time'] = datetime.now().isoformat()
        enriched_item['spider_name'] = spider.name

        # Insert data into the database
        self.cursor.execute(
            f"""
            INSERT INTO {spider.name}_data 
            (url, spider_name, data) 
            VALUES (%s, %s, %s)
            """,
            (
                spider.current_url if hasattr(spider, 'current_url') else spider.start_urls[0],
                spider.name,
                json.dumps(enriched_item)
            )
        )
        self.connection.commit()
        
        return item