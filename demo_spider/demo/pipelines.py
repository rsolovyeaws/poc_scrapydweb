# demo/pipelines.py
import hashlib
import json
from datetime import datetime
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from scrapy.exceptions import NotConfigured
import psycopg2

class S3StoragePipeline:
    """
    Pipeline that stores scraped items in S3-compatible storage (MinIO)
    """
    
    def __init__(self, settings):
        # S3 connection settings
        self.endpoint_url = settings.get('S3_ENDPOINT_URL')
        self.access_key = settings.get('S3_ACCESS_KEY')
        self.secret_key = settings.get('S3_SECRET_KEY')
        self.bucket_name = settings.get('S3_BUCKET_NAME')
        
        # Optional settings
        self.region_name = settings.get('S3_REGION_NAME', None)
        self.folder_name = settings.get('S3_FOLDER_NAME', 'scraped_data')
        
        # Initialize client to None (will be created in open_spider)
        self.client = None
        
        # Item counter for unique filenames
        self.item_count = 0
        
        # Validate required settings
        if not all([self.endpoint_url, self.access_key, self.secret_key, self.bucket_name]):
            raise NotConfigured("S3 storage settings not configured properly")
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    def open_spider(self, spider):
        """Initialize S3 client when spider opens"""
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name
        )
        
        # Reset item counter for each spider run
        self.item_count = 0
        
        # Check if bucket exists
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            spider.logger.info(f"Connected to S3 bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                spider.logger.error(f"Bucket {self.bucket_name} does not exist")
            else:
                spider.logger.error(f"Error connecting to S3: {str(e)}")
            raise NotConfigured(f"S3 bucket error: {str(e)}")
    
    def close_spider(self, spider):
        """Clean up when spider closes"""
        spider.logger.info(f"Total items stored in S3: {self.item_count}")
    
    def _generate_unique_id(self, item, spider):
        """Generate a unique ID for the item based on its content and URL"""
        # Create a string containing the URL and item content
        content_str = spider.current_url if hasattr(spider, 'current_url') else spider.start_urls[0]
        
        # Add item values to make it unique per item
        for k, v in sorted(item.items()):
            if k != 'crawl_time':  # Skip timestamp as it changes
                content_str += str(v)
                
        # Generate a hash of the content
        item_hash = hashlib.md5(content_str.encode('utf-8')).hexdigest()[:10]
        
        return item_hash
    
    def process_item(self, item, spider):
        """Store item in S3 bucket"""
        # Add metadata
        enriched_item = dict(item)
        enriched_item['crawl_time'] = datetime.now().isoformat()
        enriched_item['spider_name'] = spider.name
        enriched_item['source_url'] = spider.current_url if hasattr(spider, 'current_url') else spider.start_urls[0]
        
        # Create JSON from item
        json_item = json.dumps(enriched_item, ensure_ascii=False)
        
        # Increment counter for this item
        self.item_count += 1
        
        # Generate a unique ID for this item based on content
        item_hash = self._generate_unique_id(enriched_item, spider)
        
        # Generate S3 key (path) with unique identifier to prevent overwriting
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        url_path = ""
        
        if hasattr(spider, 'current_url') and spider.current_url:
            # Extract page number or other useful info from URL if available
            url = spider.current_url
            if 'page=' in url:
                page_num = url.split('page=')[1].split('&')[0]
                url_path = f"page{page_num}_"
            elif '/page/' in url:
                page_num = url.split('/page/')[1].split('/')[0]
                url_path = f"page{page_num}_"
        
        # Create a filename with timestamp, counter, item_hash to ensure uniqueness
        filename = f"{spider.name}_{timestamp}_{url_path}item{self.item_count}_{item_hash}.json"
        s3_key = f"{self.folder_name}/{spider.name}/{datetime.now().strftime('%Y-%m-%d')}/{filename}"
        
        # Upload file to S3
        try:
            self.client.upload_fileobj(
                BytesIO(json_item.encode('utf-8')),
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'application/json'}
            )
            spider.logger.info(f"Stored item in S3: {s3_key}")
        except ClientError as e:
            spider.logger.error(f"Failed to upload item to S3: {str(e)}")
        
        # Return item for further processing
        return item
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