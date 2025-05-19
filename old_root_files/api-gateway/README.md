# Scraper API Gateway

API Gateway for distributing scrapy tasks across multiple Scrapyd instances with load balancing.

## Features

- Automatic load balancing between Scrapyd instances
- REST API for scheduling and managing scraping jobs
- Status monitoring for all Scrapyd instances
- Centralized job management
- Integration with Redis for shared state

## API Endpoints

- `GET /` - API information
- `GET /status` - Status of all Scrapyd instances
- `POST /schedule` - Schedule a spider on the best available Scrapyd instance
- `GET /list-jobs/{project}` - List all jobs for a project across all instances
- `GET /cancel/{project}/{job_id}` - Cancel a job on any instance

## Usage

### Schedule a Spider

```bash
curl -X POST "http://localhost:5001/schedule" \
     -H "Content-Type: application/json" \
     -d '{"project": "example", "spider": "example_spider", "kwargs": {"arg1": "value1"}}'
```

### Get All Jobs

```bash
curl -X GET "http://localhost:5001/list-jobs/example"
```

### Cancel a Job

```bash
curl -X GET "http://localhost:5001/cancel/example/job_id"
``` 