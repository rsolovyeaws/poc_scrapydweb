import os
import json
import random
import time
import asyncio
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
import httpx
import redis
from pydantic import BaseModel

app = FastAPI(title="Scraper API Gateway")

# Configuration
SCRAPYD_INSTANCES = [
    {"name": "scrapyd1", "url": "http://scrapyd1:6800"},
    {"name": "scrapyd2", "url": "http://scrapyd2:6800"},
]

# Selenium resource configuration
MAX_SELENIUM_SESSIONS = int(os.getenv("MAX_SELENIUM_SESSIONS", "4"))
SELENIUM_HUB_URL = os.getenv("SELENIUM_HUB_URL", "http://selenium-hub:4444")
SELENIUM_QUEUE_KEY = "selenium:job_queue"
SELENIUM_ACTIVE_KEY = "selenium:active_sessions"
SELENIUM_LOCK_KEY = "selenium:lock"
SELENIUM_QUEUE_CHECK_INTERVAL = 1  # seconds

# Proxy configuration
PROXY_ROTATION_ENABLED = os.getenv("PROXY_ROTATION_ENABLED", "true").lower() == "true"
PROXY_SERVICE_URL = os.getenv("PROXY_SERVICE_URL", "http://proxy-rotator:5000")
DEFAULT_PROXY = os.getenv("DEFAULT_PROXY", "http://tinyproxy1:8888")

# User-Agent configuration
USER_AGENT_SERVICE_URL = os.getenv("USER_AGENT_SERVICE_URL", "http://ua-rotator:5000")

# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=True
)

# Models
class SpiderRequest(BaseModel):
    project: str
    spider: str
    settings: Optional[Dict[str, Any]] = None
    jobid: Optional[str] = None
    _version: Optional[str] = None
    auth_enabled: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None
    proxy: Optional[str] = None
    user_agent_type: Optional[str] = None
    user_agent: Optional[str] = None
    kwargs: Optional[Dict[str, Any]] = {}

class SpiderResponse(BaseModel):
    status: str
    jobid: Optional[str] = None
    node: Optional[str] = None
    message: Optional[str] = None

class SeleniumResourceStatus(BaseModel):
    max_sessions: int
    active_sessions: int
    queued_jobs: int
    available_sessions: int

# Helper functions
async def get_server_status():
    """Get status of all Scrapyd instances"""
    results = {}
    async with httpx.AsyncClient() as client:
        for instance in SCRAPYD_INSTANCES:
            try:
                response = await client.get(f"{instance['url']}/daemonstatus.json")
                if response.status_code == 200:
                    data = response.json()
                    results[instance["name"]] = {
                        "status": "online" if data.get("status") == "ok" else "offline",
                        "running": data.get("running", 0),
                        "pending": data.get("pending", 0),
                        "finished": data.get("finished", 0),
                    }
                else:
                    results[instance["name"]] = {"status": "error", "message": "Error getting status"}
            except Exception as e:
                results[instance["name"]] = {"status": "error", "message": str(e)}
    return results

def select_best_node(statuses):
    """Select the best node for job scheduling (simple load balancing)"""
    available_nodes = [
        node for node, status in statuses.items() 
        if status.get("status") == "online"
    ]
    
    if not available_nodes:
        raise HTTPException(status_code=503, detail="No Scrapyd instances available")
    
    # Simple strategy: pick node with least running jobs
    best_node = min(
        available_nodes, 
        key=lambda node: statuses[node].get("running", 0) + statuses[node].get("pending", 0)
    )
    
    return best_node

# Selenium resource management functions
async def get_selenium_status():
    """Get the current status of Selenium resources"""
    # Check if Selenium hub is accessible
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SELENIUM_HUB_URL}/status")
            if response.status_code != 200:
                return {"status": "error", "message": f"Selenium hub returned status {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Error connecting to Selenium hub: {str(e)}"}
    
    # Get current resource usage from Redis
    active_sessions = int(redis_client.get(SELENIUM_ACTIVE_KEY) or "0")
    queued_jobs = redis_client.llen(SELENIUM_QUEUE_KEY)
    
    return {
        "status": "online",
        "max_sessions": MAX_SELENIUM_SESSIONS,
        "active_sessions": active_sessions,
        "available_sessions": max(0, MAX_SELENIUM_SESSIONS - active_sessions),
        "queued_jobs": queued_jobs
    }

async def get_proxy():
    """Get a proxy from the proxy rotation service"""
    if not PROXY_ROTATION_ENABLED:
        return DEFAULT_PROXY
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PROXY_SERVICE_URL}/proxy", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                proxy = data.get("proxy")
                if proxy:
                    return proxy
    except Exception as e:
        print(f"Error getting proxy from rotation service: {str(e)}")
            
    # Fallback to default proxy
    return DEFAULT_PROXY

def acquire_selenium_session(job_details):
    """Try to acquire a Selenium session or queue job"""
    # Use a Redis lock to prevent race conditions
    with redis_client.lock(SELENIUM_LOCK_KEY, timeout=5):
        active_sessions = int(redis_client.get(SELENIUM_ACTIVE_KEY) or "0")
        
        # Check if we can acquire a session
        if active_sessions < MAX_SELENIUM_SESSIONS:
            # Increment active sessions
            redis_client.incr(SELENIUM_ACTIVE_KEY)
            return True
        else:
            # Add to queue
            redis_client.rpush(SELENIUM_QUEUE_KEY, json.dumps(job_details))
            return False

def release_selenium_session():
    """Release a Selenium session and process queue if needed"""
    with redis_client.lock(SELENIUM_LOCK_KEY, timeout=5):
        active_sessions = int(redis_client.get(SELENIUM_ACTIVE_KEY) or "0")
        if active_sessions > 0:
            redis_client.decr(SELENIUM_ACTIVE_KEY)

async def process_selenium_queue():
    """Process the Selenium job queue"""
    # This runs in the background continuously
    while True:
        try:
            # Use a lock to prevent race conditions
            with redis_client.lock(SELENIUM_LOCK_KEY, timeout=5):
                active_sessions = int(redis_client.get(SELENIUM_ACTIVE_KEY) or "0")
                
                # Check if we can process more jobs
                if active_sessions < MAX_SELENIUM_SESSIONS and redis_client.llen(SELENIUM_QUEUE_KEY) > 0:
                    # Get the next job from the queue
                    job_details_json = redis_client.lpop(SELENIUM_QUEUE_KEY)
                    if job_details_json:
                        # Increment active sessions
                        redis_client.incr(SELENIUM_ACTIVE_KEY)
                        
                        # Process the job
                        job_details = json.loads(job_details_json)
                        asyncio.create_task(schedule_job_on_node(job_details))
        except Exception as e:
            print(f"Error processing Selenium queue: {str(e)}")
            
        # Wait before checking again
        await asyncio.sleep(SELENIUM_QUEUE_CHECK_INTERVAL)

async def schedule_job_on_node(job_details):
    """Schedule a job on a Scrapyd node"""
    try:
        # Extract job details
        instance = next(inst for inst in SCRAPYD_INSTANCES if inst["name"] == job_details["node"])
        data = job_details["data"]
        
        # Schedule job
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{instance['url']}/schedule.json", data=data)
            
        # Release Selenium session regardless of success or failure
        # The spider will acquire a new session when it actually runs
        release_selenium_session()
            
    except Exception as e:
        print(f"Error scheduling job from queue: {str(e)}")
        release_selenium_session()

# Routes
@app.get("/")
async def root():
    return {"message": "Scraper API Gateway", "version": "1.0.0"}

@app.get("/status")
async def status():
    """Get status of all Scrapyd instances"""
    scrapyd_status = await get_server_status()
    selenium_status = await get_selenium_status()
    
    return {
        "scrapyd": scrapyd_status,
        "selenium": selenium_status
    }

@app.get("/selenium/status", response_model=SeleniumResourceStatus)
async def selenium_status():
    """Get status of Selenium resources"""
    status = await get_selenium_status()
    if status.get("status") == "error":
        raise HTTPException(status_code=503, detail=status.get("message"))
    
    return {
        "max_sessions": status.get("max_sessions"),
        "active_sessions": status.get("active_sessions"),
        "queued_jobs": status.get("queued_jobs"),
        "available_sessions": status.get("available_sessions")
    }

@app.get("/selenium/reset")
async def reset_selenium():
    """Reset Selenium resources counter - useful when sessions get stuck"""
    try:
        # Reset active sessions counter
        redis_client.set(SELENIUM_ACTIVE_KEY, "0")
        
        # Clear any queued jobs
        queue_size = redis_client.llen(SELENIUM_QUEUE_KEY)
        if queue_size > 0:
            redis_client.delete(SELENIUM_QUEUE_KEY)
        
        return {
            "status": "success",
            "message": f"Reset Selenium counter and cleared {queue_size} queued jobs",
            "previous_active_sessions": redis_client.get(SELENIUM_ACTIVE_KEY) or "0"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset Selenium resources: {str(e)}")

@app.post("/schedule", response_model=SpiderResponse)
async def schedule_spider(request: SpiderRequest, background_tasks: BackgroundTasks):
    """Schedule a spider on the best available Scrapyd instance with Selenium resource management"""
    try:
        # Check if Selenium counter is stuck (all active but no actual running jobs)
        statuses = await get_server_status()
        selenium_status = await get_selenium_status()
        
        # Auto-reset if all sessions are marked active but no jobs are actually running
        all_running_jobs = sum(status.get("running", 0) for name, status in statuses.items())
        if (selenium_status.get("active_sessions", 0) >= MAX_SELENIUM_SESSIONS and 
            all_running_jobs == 0):
            # Reset counter automatically
            redis_client.set(SELENIUM_ACTIVE_KEY, "0")
            # Log the auto-reset
            print(f"Auto-reset Selenium counter: {selenium_status.get('active_sessions', 0)} -> 0")
        
        # Get status of all instances
        statuses = await get_server_status()
        
        # Select best node
        best_node = select_best_node(statuses)
        instance = next(inst for inst in SCRAPYD_INSTANCES if inst["name"] == best_node)
        
        # Prepare request data
        data = {
            "project": request.project,
            "spider": request.spider,
        }
        
        # Add optional parameters
        if request.jobid:
            data["jobid"] = request.jobid
            
        if request._version:
            data["_version"] = request._version
            
        # Add authentication parameters
        if request.auth_enabled:
            data["auth_enabled"] = "true" if request.auth_enabled else "false"
            
        if request.username:
            data["username"] = request.username
            
        if request.password:
            data["password"] = request.password
        
        # Handle proxy settings
        if request.proxy:
            # Use explicitly specified proxy
            data["proxy"] = request.proxy
        elif PROXY_ROTATION_ENABLED:
            # Get a proxy from the rotation service
            proxy = await get_proxy()
            data["proxy"] = proxy
            print(f"Using rotated proxy: {proxy}")
        
        # Handle user agent settings
        if request.user_agent:
            # Use explicitly specified user agent
            data["user_agent"] = request.user_agent
            # Also set as a setting to ensure it's picked up
            if not request.settings:
                request.settings = {}
            request.settings["USER_AGENT"] = request.user_agent
            print(f"Using specified User-Agent: {request.user_agent}")
        elif request.user_agent_type:
            # Use user agent type for rotation
            data["user_agent_type"] = request.user_agent_type
            print(f"Using User-Agent rotation type: {request.user_agent_type}")
            
        # Add settings as JSON
        if request.settings:
            data["setting"] = [f"{k}={v}" for k, v in request.settings.items()]
            
        # Add spider kwargs
        if request.kwargs:
            for k, v in request.kwargs.items():
                data[k] = v
        
        # Check selenium resource utilization
        selenium_status = await get_selenium_status()
        
        # Create job details for direct scheduling or queuing
        job_details = {
            "node": instance["name"],
            "data": data,
            "timestamp": time.time()
        }
        
        # Try to acquire a Selenium session or queue the job
        session_acquired = acquire_selenium_session(job_details)
        
        if session_acquired:
            # Send request to Scrapyd
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{instance['url']}/schedule.json", data=data)
                
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    return {
                        "status": "success",
                        "jobid": result.get("jobid"),
                        "node": instance["name"],
                        "message": f"Spider scheduled on {instance['name']}"
                    }
                else:
                    # Release the session on error
                    release_selenium_session()
                    return {
                        "status": "error",
                        "message": result.get("message", "Unknown error")
                    }
            else:
                # Release the session on error
                release_selenium_session()
                return {
                    "status": "error",
                    "message": f"Error {response.status_code}: {response.text}"
                }
        else:
            # Job was queued
            return {
                "status": "queued",
                "message": f"Spider queued for execution due to Selenium resource constraints",
                "node": instance["name"],
                "jobid": request.jobid
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-jobs/{project}")
async def list_jobs(project: str):
    """List all jobs across all Scrapyd instances"""
    results = {}
    
    async with httpx.AsyncClient() as client:
        for instance in SCRAPYD_INSTANCES:
            try:
                response = await client.get(f"{instance['url']}/listjobs.json", params={"project": project})
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        # Add node name to each job
                        for job_type in ["pending", "running", "finished"]:
                            for job in data.get(job_type, []):
                                job["node"] = instance["name"]
                        
                        results[instance["name"]] = data
                    else:
                        results[instance["name"]] = {"status": "error", "message": data.get("message")}
                else:
                    results[instance["name"]] = {"status": "error", "message": f"Error {response.status_code}"}
            except Exception as e:
                results[instance["name"]] = {"status": "error", "message": str(e)}
    
    # Add queued jobs information
    queued_jobs = []
    for i in range(redis_client.llen(SELENIUM_QUEUE_KEY)):
        job_json = redis_client.lindex(SELENIUM_QUEUE_KEY, i)
        if job_json:
            job = json.loads(job_json)
            if job["data"].get("project") == project:
                node_name = job["node"]
                job_id = job["data"].get("jobid", "unknown")
                spider_name = job["data"].get("spider", "unknown")
                queued_jobs.append({
                    "id": job_id,
                    "spider": spider_name,
                    "node": node_name,
                    "queue_time": job["timestamp"]
                })
    
    if queued_jobs:
        results["queued"] = queued_jobs
        
    return results

@app.get("/cancel/{project}/{job_id}")
async def cancel_job(project: str, job_id: str):
    """Cancel a job on any Scrapyd instance or remove from queue"""
    # First, check if job is in the queue
    for i in range(redis_client.llen(SELENIUM_QUEUE_KEY)):
        job_json = redis_client.lindex(SELENIUM_QUEUE_KEY, i)
        if job_json:
            job = json.loads(job_json)
            if (job["data"].get("project") == project and 
                job["data"].get("jobid") == job_id):
                # Remove job from queue
                redis_client.lrem(SELENIUM_QUEUE_KEY, 1, job_json)
                return {
                    "status": "success",
                    "message": f"Job {job_id} removed from queue",
                    "node": job["node"]
                }
    
    # If not in queue, try to cancel on Scrapyd instances
    for instance in SCRAPYD_INSTANCES:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{instance['url']}/listjobs.json", 
                    params={"project": project}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if job exists in this instance
                    job_exists = False
                    for job_type in ["pending", "running"]:
                        if any(job.get("id") == job_id for job in data.get(job_type, [])):
                            job_exists = True
                            break
                            
                    if job_exists:
                        # Cancel the job
                        cancel_response = await client.post(
                            f"{instance['url']}/cancel.json",
                            data={"project": project, "job": job_id}
                        )
                        
                        if cancel_response.status_code == 200:
                            result = cancel_response.json()
                            
                            # If job was running, release Selenium session
                            for job in data.get("running", []):
                                if job.get("id") == job_id:
                                    release_selenium_session()
                                    break
                                    
                            return {
                                "status": "success" if result.get("status") == "ok" else "error",
                                "message": result.get("prevstate", "Job cancelled"),
                                "node": instance["name"]
                            }
        except Exception:
            continue
            
    # If we get here, job wasn't found
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found in project {project}")

# Start the background task for processing the queue
@app.on_event("startup")
async def startup_event():
    # Initialize Selenium active sessions counter if it doesn't exist
    if not redis_client.exists(SELENIUM_ACTIVE_KEY):
        redis_client.set(SELENIUM_ACTIVE_KEY, "0")
    
    # Start background task to process queue
    asyncio.create_task(process_selenium_queue())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 