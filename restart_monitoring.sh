#!/bin/bash

echo "Restarting monitoring services..."
docker-compose down elasticsearch kibana filebeat prometheus grafana alertmanager cadvisor node-exporter
docker-compose up -d elasticsearch kibana filebeat prometheus grafana alertmanager cadvisor node-exporter

echo "Waiting for services to start..."
sleep 10

echo "==========================================="
echo "Monitoring services restarted successfully!"
echo "==========================================="
echo ""
echo "Access Kibana (logs): http://localhost:5601"
echo "Access Grafana (metrics): http://localhost:3000"
echo ""
echo "Default Grafana credentials:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "You'll be prompted to change password on first login" 