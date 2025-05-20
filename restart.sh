#!/bin/bash

echo "Starting restart process..."

# Stop all services
docker compose down -v

# Prepare egg file for demo spider
mkdir -p docker/shared-eggs
rm -f docker/shared-eggs/demo-1.0-py3.10.egg
cd spiders/demo_spider/
python3 setup.py bdist_egg
cd ../..
cp spiders/demo_spider/dist/demo-1.0-py3.10.egg docker/shared-eggs/

# Start all services
docker compose up --build -d

# Wait for services to start
echo "Waiting for services to start up..." 
sleep 10

# Make sure the startup-notification is started after other services are ready
echo "Ensuring startup notification is working..."
docker compose up -d startup-notification

echo "Restart completed. Check Telegram for startup notification."