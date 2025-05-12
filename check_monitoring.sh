#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking monitoring system status...${NC}"

# Check Elasticsearch
echo -n "Checking Elasticsearch... "
if curl -s "http://localhost:9200/_cluster/health" | grep -q '"status":\("green"\|"yellow"\)'; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check Kibana
echo -n "Checking Kibana... "
if curl -s "http://localhost:5601/api/status" | grep -q '"overall":{"level":"available"'; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check Prometheus
echo -n "Checking Prometheus... "
if curl -s "http://localhost:9090/-/healthy" | grep -q "Prometheus is Healthy"; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check Grafana
echo -n "Checking Grafana... "
if curl -s "http://localhost:3000/api/health" | grep -q '"database":"ok"'; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check cAdvisor
echo -n "Checking cAdvisor... "
if curl -s "http://localhost:8080/healthz" | grep -q "ok"; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check Node Exporter
echo -n "Checking Node Exporter... "
if curl -s "http://localhost:9100/metrics" | grep -q "node_"; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

# Check Alertmanager
echo -n "Checking Alertmanager... "
if curl -s "http://localhost:9093/-/healthy" | grep -q "OK"; then
  echo -e "${GREEN}OK${NC}"
else
  echo -e "${RED}FAILED${NC}"
fi

echo -e "\n${YELLOW}Checking docker containers...${NC}"
docker-compose ps

echo -e "\n${YELLOW}Useful links:${NC}"
echo -e "Kibana:      ${GREEN}http://localhost:5601${NC}"
echo -e "Grafana:     ${GREEN}http://localhost:3000${NC} (admin/admin)"
echo -e "Prometheus:  ${GREEN}http://localhost:9090${NC}"
echo -e "cAdvisor:    ${GREEN}http://localhost:8080${NC}"
echo -e "Alertmanager:${GREEN}http://localhost:9093${NC}" 