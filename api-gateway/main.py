import os
import json
import random
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Response
import httpx
import redis
from pydantic import BaseModel

app = FastAPI(title="Scraper API Gateway")

# Configuration
SCRAPYD_INSTANCES = [
    {"name": "scrapyd1", "url": "http://scrapyd1:6800"},
    {"name": "scrapyd2", "url": "http://scrapyd2:6800"},
]

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
    kwargs: Optional[Dict[str, Any]] = {}

class SpiderResponse(BaseModel):
    status: str
    jobid: Optional[str] = None
    node: Optional[str] = None
    message: Optional[str] = None

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

# Routes
@app.get("/")
async def root():
    return {"message": "Scraper API Gateway", "version": "1.0.0"}

@app.get("/status")
async def status():
    """Get status of all Scrapyd instances"""
    return await get_server_status()

@app.post("/schedule", response_model=SpiderResponse)
async def schedule_spider(request: SpiderRequest):
    """Schedule a spider on the best available Scrapyd instance"""
    try:
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
            
        if request.proxy:
            data["proxy"] = request.proxy
            
        # Add settings as JSON
        if request.settings:
            data["setting"] = [f"{k}={v}" for k, v in request.settings.items()]
            
        # Add spider kwargs
        if request.kwargs:
            for k, v in request.kwargs.items():
                data[k] = v
        
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
                return {
                    "status": "error",
                    "message": result.get("message", "Unknown error")
                }
        else:
            return {
                "status": "error",
                "message": f"Error {response.status_code}: {response.text}"
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
    
    return results

@app.get("/cancel/{project}/{job_id}")
async def cancel_job(project: str, job_id: str):
    """Cancel a job on any Scrapyd instance"""
    # Find which node has the job
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
                            return {
                                "status": "success" if result.get("status") == "ok" else "error",
                                "message": result.get("prevstate", "Job cancelled"),
                                "node": instance["name"]
                            }
        except Exception:
            continue
            
    # If we get here, job wasn't found
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found in project {project}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 