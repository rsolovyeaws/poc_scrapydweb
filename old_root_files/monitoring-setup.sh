#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up monitoring and logging system...${NC}"

# Create directories if they don't exist
echo -e "${YELLOW}Creating required directories...${NC}"
mkdir -p grafana-dashboards
mkdir -p grafana-datasources
mkdir -p prometheus-data
mkdir -p elasticsearch-data
mkdir -p monitoring-setup
cp grafana-dashboards/scraper_dashboard.json grafana-dashboards/

# Set up environment file for secrets
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}Creating .env file from template...${NC}"
  cp env.template .env
  echo -e "${RED}ВАЖНО: Обновите файл .env своими учетными данными Telegram!${NC}"
  echo -e "${YELLOW}Выполните: nano .env${NC}"
fi

echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x telegram_alerts.py

# Create container for the monitoring services
echo -e "${GREEN}Creating and starting monitoring services...${NC}"
docker-compose up -d elasticsearch kibana filebeat prometheus grafana cadvisor alertmanager node-exporter

# Wait for services to start
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check if services are running
echo -e "${YELLOW}Checking service status...${NC}"
if docker-compose ps | grep -q "elasticsearch"; then
  echo -e "${GREEN}✅ Elasticsearch is running${NC}"
else
  echo -e "${RED}❌ Elasticsearch is not running${NC}"
fi

if docker-compose ps | grep -q "kibana"; then
  echo -e "${GREEN}✅ Kibana is running${NC}"
else
  echo -e "${RED}❌ Kibana is not running${NC}"
fi

if docker-compose ps | grep -q "filebeat"; then
  echo -e "${GREEN}✅ Filebeat is running${NC}"
else
  echo -e "${RED}❌ Filebeat is not running${NC}"
fi

if docker-compose ps | grep -q "prometheus"; then
  echo -e "${GREEN}✅ Prometheus is running${NC}"
else
  echo -e "${RED}❌ Prometheus is not running${NC}"
fi

if docker-compose ps | grep -q "grafana"; then
  echo -e "${GREEN}✅ Grafana is running${NC}"
else
  echo -e "${RED}❌ Grafana is not running${NC}"
fi

echo -e "${GREEN}Monitoring system setup complete!${NC}"
echo -e "${YELLOW}Access your dashboards at:${NC}"
echo -e "- Kibana: http://localhost:5601"
echo -e "- Grafana: http://localhost:3000 (admin/admin)"
echo -e "- Prometheus: http://localhost:9090"

echo -e "${YELLOW}Before using Telegram alerts, configure BOT_TOKEN and CHAT_ID in .env file.${NC}"

# Уведомление о запуске будет отправлено автоматически через сервис startup-notification 