#!/bin/bash

# Activate the virtual environment
source .venv/bin/activate

# Run the publisher with default parameters from schedule_egg.sh
python publish_rabbitmq_task.py \
  --host localhost \
  --port 5672 \
  --auth \
  --username admin \
  --password admin \
  --proxy http://tinyproxy:8888 \
  --setting "CLOSESPIDER_PAGECOUNT=0" \
  --setting "CLOSESPIDER_TIMEOUT=60" \
  --setting "LOG_LEVEL=DEBUG" \
  --user-agent-type desktop

# Optional: Add additional parameters to override defaults
# --project demo-1.0-py3.10 \
# --version 1_0 \
# --spider quotes_spa \
# --jobid custom_id \
# --arg "arg1=val1" 
# --user-agent-type mobile 