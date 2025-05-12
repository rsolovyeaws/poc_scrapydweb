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
    . as $data | 
    keys[] as $key | 
    if $data[$key].status == "online" then
        "✅ " + $key + ": " + $data[$key].status + " (running: " + ($data[$key].running | tostring) + ", pending: " + ($data[$key].pending | tostring) + ")"
    else
        "❌ " + $key + ": " + $data[$key].status
    end
'

echo -e "\nExample usage:"
echo "  Schedule a spider:  ./api-gateway/client_example.py schedule --project demo --spider example --kwargs='{\"url\":\"https://example.com\"}'"
echo "  List jobs:          ./api-gateway/client_example.py list --project demo"
echo "  Cancel a job:       ./api-gateway/client_example.py cancel --project demo --job-id JOB_ID" 