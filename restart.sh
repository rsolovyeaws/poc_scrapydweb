#!/bin/bash

docker compose down -v
rm shared-eggs/demo-1.0-py3.10.egg
cd demo_spider/
python3 setup.py bdist_egg
cd ..
cp demo_spider/dist/demo-1.0-py3.10.egg shared-eggs/
docker compose up --build -d