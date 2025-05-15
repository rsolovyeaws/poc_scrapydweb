#!/bin/bash

curl -u group2:scrapyd2 \
http://localhost:6801/schedule.json \
-d project=demo-1.0-py3.10 \
-d _version=1_0 \
-d spider=quotes_spa \
-d jobid=2025-05-09T13_48_03 \
-d setting=CLOSESPIDER_PAGECOUNT=0 \
-d setting=CLOSESPIDER_TIMEOUT=60 \
-d setting=LOG_LEVEL=DEBUG \
-d arg1=val1 \
-d auth_enabled=true \
-d username=admin \
-d password=admin \
-d proxy=http://tinyproxy:8888