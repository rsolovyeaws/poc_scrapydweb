#!/bin/bash

# Script to check the API Gateway status and show available Scrapyd instances

API_URL=${1:-"http://localhost:5001"}

echo "Checking API Gateway at $API_URL..."

# Check if the API is up
status_code=$(curl -s -o /dev/null -w "%{http_code}" ${API_URL})

if [ $status_code -ne 200 ]; then
    echo "❌ API Gateway is not running (status code: $status_code)"
    exit 1
fi

echo "✅ API Gateway is running"

# Get the status of Scrapyd instances
echo -e "\nScrapyd Instances Status:"
curl -s ${API_URL}/status | jq -r '
    .scrapyd | to_entries[] | 
    if .value.status == "online" then
        "✅ " + .key + ": " + .value.status + " (running: " + (.value.running | tostring) + ", pending: " + (.value.pending | tostring) + ")"
    else
        "❌ " + .key + ": " + .value.status
    end
'

# Get the status of Selenium
echo -e "\nSelenium Status:"
curl -s ${API_URL}/status | jq -r '
    .selenium | 
    if .status == "online" then
        "✅ Selenium: online (active sessions: " + (.active_sessions | tostring) + "/" + (.max_sessions | tostring) + ", queued: " + (.queued_jobs | tostring) + ")"
    else
        "❌ Selenium: " + (.status // "offline")
    end
'

echo -e "\nExample usage:"
echo "  Schedule a spider:  ./api-gateway/client_example.py schedule --project demo --spider example --kwargs='{\"url\":\"https://example.com\"}'"
echo "  List jobs:          ./api-gateway/client_example.py list --project demo"
echo "  Cancel a job:       ./api-gateway/client_example.py cancel --project demo --job-id JOB_ID" 