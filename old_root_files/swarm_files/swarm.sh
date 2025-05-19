#!/bin/bash
# Instructions for setting up Docker Swarm for scrapyd scaling

# Initialize Docker Swarm (only if not already in swarm mode)
docker swarm init --advertise-addr 172.20.254.112

# Deploy the stack with your docker-compose file
docker stack deploy -c docker-compose.yml scrapy-stack

# Verify the services are running
docker service ls

# Check the tasks/containers
docker service ps scrapy-stack_scrapyd

# Scale the service if needed (alternate method)
docker service scale scrapy-stack_scrapyd=2

# To schedule multiple spiders
python3 batch_scheduler.py --project demo --spider quotes_spa --count 3

# View logs from all instances
docker service logs scrapy-stack_scrapyd

# To stop the stack when done
docker stack rm scrapy-stack

# Leave swarm mode if no longer needed
docker swarm leave --force