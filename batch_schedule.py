#!/usr/bin/env python3
"""
Script to schedule multiple spider runs across Scrapyd instances
"""
import argparse
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor


def schedule_spider(server_url, project, spider, settings=None, job_id=None):
    """Schedule a spider run on a Scrapyd server"""
    params = {
        'project': project,
        'spider': spider
    }
    
    if settings:
        params['setting'] = settings
    
    if job_id:
        params['jobid'] = job_id
    
    try:
        response = requests.post(f"{server_url}/schedule.json", data=params)
        result = response.json()
        print(f"Scheduling on {server_url}: {result}")
        return result
    except Exception as e:
        print(f"Error scheduling on {server_url}: {e}")
        return None


def batch_schedule(load_balancer_url, project, spider, count, concurrent=True):
    """Schedule multiple runs of the same spider"""
    start_time = time.time()
    
    if concurrent:
        # Schedule multiple spiders concurrently
        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = []
            for i in range(count):
                job_id = f"{spider}_batch_{i+1}"
                futures.append(
                    executor.submit(
                        schedule_spider, 
                        load_balancer_url, 
                        project, 
                        spider, 
                        None, 
                        job_id
                    )
                )
            
            # Wait for all to complete
            for future in futures:
                future.result()
    else:
        # Schedule spiders sequentially
        for i in range(count):
            job_id = f"{spider}_batch_{i+1}"
            schedule_spider(load_balancer_url, project, spider, None, job_id)
    
    elapsed = time.time() - start_time
    print(f"Scheduled {count} spider runs in {elapsed:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Schedule Scrapy Spiders")
    parser.add_argument("--url", default="http://localhost:8800", help="Load balancer URL")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--spider", required=True, help="Spider name")
    parser.add_argument("--count", type=int, default=3, help="Number of runs to schedule")
    parser.add_argument("--sequential", action="store_true", help="Schedule sequentially instead of concurrently")
    
    args = parser.parse_args()
    
    batch_schedule(
        args.url, 
        args.project, 
        args.spider, 
        args.count, 
        not args.sequential
    )