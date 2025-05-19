#!/bin/bash

# Create data directory if it doesn't exist
mkdir -p data

echo "Creating and initializing ScrapydWeb database..."

# Run our Python script to create the database tables directly
python3 create_scrapydweb_db.py

echo "Database initialization complete."
echo "Now you can deploy your Docker Swarm stack."

# Double check permissions on the data directory
chmod -R 777 data