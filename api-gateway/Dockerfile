FROM python:3.9-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default environment variables
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV REDIS_DB=0
ENV MAX_SELENIUM_SESSIONS=4
ENV SELENIUM_HUB_URL=http://selenium-hub:4444

# Proxy configuration
ENV PROXY_ROTATION_ENABLED=true
ENV PROXY_SERVICE_URL=http://proxy-rotator:5000
ENV DEFAULT_PROXY=http://tinyproxy1:8888

# User Agent configuration
ENV USER_AGENT_SERVICE_URL=http://ua-rotator:5000

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"] 