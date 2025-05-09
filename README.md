# docker 

```bash
docker compose down -v; rm shared-eggs/demo-1.0-py3.10.egg; cd demo_spider/; python3 setup.py bdist_egg; cd ..; cp demo_spider/dist/demo-1.0-py3.10.egg shared-eggs/; docker compose up --build -d
```

# Run spider with login and proxy on Scrapyd2 instance
```bash
curl -u group2:scrapyd2 \
http://localhost:6801/schedule.json \
-d project=demo-1.0-py3.10 \
-d _version=1_0 \
-d spider=quotes_spa \
-d jobid=2025-05-09T13_15_00 \
-d setting=CLOSESPIDER_PAGECOUNT=0 \
-d setting=CLOSESPIDER_TIMEOUT=60 \
-d arg1=val1 \
-d auth_enabled=true \
-d username=admin \
-d password=admin \
-d proxy=http://tinyproxy:8888
```

# Links
- [Scrapyd Web Interface](http://localhost:5000)
- [S3](http://localhost:9001)
- [pgAdmin](http://localhost:5050)
