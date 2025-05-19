# User-Agent Rotation Service

A lightweight microservice for providing random User-Agents for web scraping projects. It helps avoid detection by websites by rotating User-Agents for your requests.

## Features

- Random User-Agent rotation from a curated database
- Supports different device types (desktop, mobile, tablet)
- Supports different browser families (Chrome, Firefox, Safari, Edge)
- REST API for integration with any scraping framework
- Usage statistics tracking
- Persistent storage of User-Agents and stats
- API to add new User-Agents

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /api/user-agent` - Get a random User-Agent
  - Query params:
    - `type`: Device type (desktop, mobile, tablet)
    - `browser`: Browser family (chrome, firefox, safari, edge)
- `GET /api/stats` - Get usage statistics
- `GET /api/user-agents` - List all available User-Agents
- `POST /api/user-agents` - Add a new User-Agent
  - Body:
    ```json
    {
      "user_agent": "Mozilla/5.0 ...",
      "type": "desktop",
      "browser": "chrome"
    }
    ```

## Integration with Scrapy

This service is designed to work seamlessly with the Scrapy framework through a custom middleware.

Example Scrapy settings:

```python
USER_AGENT_ROTATION_ENABLED = True
USER_AGENT_SERVICE_URL = 'http://ua-rotator:5000'

DOWNLOADER_MIDDLEWARES = {
    "demo.user_agent_middleware.UserAgentRotationMiddleware": 750,
    # other middlewares...
}
```

## Usage with Docker

```bash
# Build the image
docker build -t ua-rotator .

# Run the container
docker run -d --name ua-rotator \
  -p 5002:5000 \
  -v ua-rotator-data:/data \
  ua-rotator
```

## Data Persistence

User-Agents and usage statistics are stored in the `/data` directory, which is configured as a Docker volume for persistence.

## Environment Variables

- `PORT`: Service port (default: 5000)
- `HOST`: Service host (default: 0.0.0.0)
- `DATA_DIR`: Directory for persistent data (default: /data)
- `DEBUG`: Enable debug mode (default: False) 