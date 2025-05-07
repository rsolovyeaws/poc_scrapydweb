#!/bin/bash
#curl http://localhost:6800/schedule.json -d project=demo -d spider=quotes_spa -d jobid=job1
#curl http://localhost:6800/schedule.json -d project=demo -d spider=quotes_spa -d jobid=job2

# Run on scrapyd2 (port 6801) 
#curl http://localhost:6801/schedule.json -d project=demo -d spider=quotes_spa -d jobid=job3

curl -X POST http://localhost:5000/run/spider -d "project=demo&spider=quotes_spa&job_count=3"

watch -n 1 'echo "scrapyd1:" && curl -s http://localhost:6800/listjobs.json?project=demo | jq ".running | length" && echo "scrapyd2:" && curl -s http://localhost:6801/listjobs.json?project=demo | jq ".running | length"'