#!/bin/bash
scrapyd &

# Wait for scrapyd to start
sleep 5

# Deploy all eggs found in the shared folder
for egg in /root/.scrapyd/eggs/*.egg; do
  if [ -f "$egg" ]; then
    echo "Deploying $egg..."
    project_name=$(basename "$egg" .egg)
    curl -X POST http://localhost:6800/addversion.json \
      -F "project=$project_name" \
      -F "version=1.0" \
      -F "egg=@$egg"
  fi
done

# Keep container running
wait