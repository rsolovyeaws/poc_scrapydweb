#!/bin/bash

echo "Checking Redis for cookies..."
docker exec -it scraper-redis redis-cli keys "scrapy:cookies:*"

echo ""
echo "Getting contents of quotes_spa cookies:"
docker exec -it scraper-redis redis-cli get "scrapy:cookies:quotes_spa"

echo ""
echo "Redis info:"
docker exec -it scraper-redis redis-cli info keyspace 