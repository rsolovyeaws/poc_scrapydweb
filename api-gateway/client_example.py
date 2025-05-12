#!/usr/bin/env python3
"""
Example client for the Scraper API Gateway.
This script demonstrates how to use the API gateway to schedule and manage scraping jobs.
"""

import argparse
import json
import httpx
import sys
from typing import Dict, Optional, List
from datetime import datetime

# Default API endpoint
API_ENDPOINT = "http://localhost:5001"

async def get_status():
    """Get status of all Scrapyd instances"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_ENDPOINT}/status")
        return response.json()

async def schedule_spider(
    project: str, 
    spider: str, 
    version: Optional[str] = None,
    jobid: Optional[str] = None, 
    settings: Optional[Dict[str, str]] = None,
    auth_enabled: Optional[bool] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    proxy: Optional[str] = None,
    kwargs: Optional[Dict[str, str]] = None
):
    """Schedule a spider on the best available Scrapyd instance"""
    data = {
        "project": project,
        "spider": spider,
    }
    
    if version:
        data["_version"] = version
        
    if jobid:
        data["jobid"] = jobid
    
    if settings:
        data["settings"] = settings
        
    if auth_enabled is not None:
        data["auth_enabled"] = auth_enabled
        
    if username:
        data["username"] = username
        
    if password:
        data["password"] = password
        
    if proxy:
        data["proxy"] = proxy
        
    if kwargs:
        data["kwargs"] = kwargs
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_ENDPOINT}/schedule",
            json=data
        )
        return response.json()

async def list_jobs(project: str):
    """List all jobs for a project across all instances"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_ENDPOINT}/list-jobs/{project}")
        return response.json()

async def cancel_job(project: str, job_id: str):
    """Cancel a job on any instance"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_ENDPOINT}/cancel/{project}/{job_id}")
        return response.json()

def generate_jobid():
    """Generate a jobid based on current time"""
    return datetime.now().strftime('%Y-%m-%dT%H_%M_%S')

async def main():
    global API_ENDPOINT
    
    parser = argparse.ArgumentParser(description="Scraper API Gateway Client")
    parser.add_argument("--endpoint", default=API_ENDPOINT, help="API Gateway endpoint")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get status of all Scrapyd instances")
    
    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Schedule a spider")
    schedule_parser.add_argument("--project", required=True, help="Project name")
    schedule_parser.add_argument("--spider", required=True, help="Spider name")
    schedule_parser.add_argument("--version", help="Project version")
    schedule_parser.add_argument("--jobid", help="Job ID (will be auto-generated if not provided)")
    schedule_parser.add_argument("--setting", action='append', help="Setting in format KEY=VALUE (can be used multiple times)")
    schedule_parser.add_argument("--auth-enabled", action='store_true', help="Enable authentication")
    schedule_parser.add_argument("--username", help="Username for authentication")
    schedule_parser.add_argument("--password", help="Password for authentication")
    schedule_parser.add_argument("--proxy", help="Proxy URL (e.g. http://tinyproxy:8888)")
    schedule_parser.add_argument("--arg", action='append', help="Additional argument in format KEY=VALUE (can be used multiple times)")
    
    # List jobs command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--project", required=True, help="Project name")
    
    # Cancel job command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a job")
    cancel_parser.add_argument("--project", required=True, help="Project name")
    cancel_parser.add_argument("--job-id", required=True, help="Job ID")
    
    args = parser.parse_args()
    
    # Set API endpoint
    if args.endpoint:
        API_ENDPOINT = args.endpoint
    
    if args.command == "status":
        result = await get_status()
        print(json.dumps(result, indent=2))
    
    elif args.command == "schedule":
        # Parse settings
        settings = {}
        if args.setting:
            for setting in args.setting:
                if '=' in setting:
                    key, value = setting.split('=', 1)
                    settings[key] = value
        
        # Parse additional arguments
        kwargs = {}
        if args.arg:
            for arg in args.arg:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    kwargs[key] = value
        
        # Generate jobid if not provided
        jobid = args.jobid or generate_jobid()
        
        result = await schedule_spider(
            project=args.project,
            spider=args.spider,
            version=args.version,
            jobid=jobid,
            settings=settings if settings else None,
            auth_enabled=args.auth_enabled if hasattr(args, 'auth_enabled') else None,
            username=args.username,
            password=args.password,
            proxy=args.proxy,
            kwargs=kwargs if kwargs else None
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "list":
        result = await list_jobs(args.project)
        print(json.dumps(result, indent=2))
    
    elif args.command == "cancel":
        result = await cancel_job(args.project, args.job_id)
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 