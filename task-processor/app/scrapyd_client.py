#!/usr/bin/env python3
import requests
import structlog
from typing import Dict, Any, Optional

class ScrapydClient:
    """Client for interacting with Scrapyd API via the API Gateway"""
    
    def __init__(self, base_url: str = "http://api-gateway:5000"):
        """
        Initialize the Scrapyd client.
        
        Args:
            base_url: Base URL of the API Gateway
        """
        self.base_url = base_url.rstrip('/')
        self.logger = structlog.get_logger()
    
    def schedule_spider(self, project: str, spider: str, settings: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Schedule a spider to run.
        
        Args:
            project: Name of the Scrapy project
            spider: Name of the spider to run
            settings: Dictionary with Scrapy settings
            **kwargs: Additional spider arguments
            
        Returns:
            Dictionary with response data
        """
        endpoint = f"{self.base_url}/schedule"
        
        payload = {
            "project": project,
            "spider": spider,
            "settings": settings or {},
            "kwargs": kwargs
        }
        
        if "jobid" in kwargs:
            payload["jobid"] = kwargs["jobid"]
        
        self.logger.info("Scheduling spider", 
                         project=project, 
                         spider=spider, 
                         settings=settings)
        
        try:
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            
            self.logger.info("Spider scheduled successfully", 
                             job_id=result.get("jobid"),
                             status=result.get("status"))
            
            return result
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to schedule spider", 
                              error=str(e),
                              project=project,
                              spider=spider)
            raise
    
    def cancel_spider(self, project: str, job_id: str) -> Dict[str, Any]:
        """
        Cancel a running spider.
        
        Args:
            project: Name of the Scrapy project
            job_id: ID of the job to cancel
            
        Returns:
            Dictionary with response data
        """
        endpoint = f"{self.base_url}/cancel/{project}/{job_id}"
        
        self.logger.info("Canceling spider", project=project, job_id=job_id)
        
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            result = response.json()
            
            self.logger.info("Spider canceled", 
                            job_id=job_id,
                            project=project,
                            result=result)
            
            return result
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to cancel spider", 
                             error=str(e),
                             project=project,
                             job_id=job_id)
            raise
    
    def list_jobs(self, project: str) -> Dict[str, Any]:
        """
        List all jobs for a project.
        
        Args:
            project: Name of the Scrapy project
            
        Returns:
            Dictionary with job data
        """
        endpoint = f"{self.base_url}/list-jobs/{project}"
        
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            result = response.json()
            
            return result
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to list jobs", 
                             error=str(e),
                             project=project)
            raise
    
    def check_status(self) -> Dict[str, Any]:
        """
        Check the status of the API Gateway.
        
        Returns:
            Dictionary with status information
        """
        endpoint = f"{self.base_url}/status"
        
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to check API Gateway status", error=str(e))
            raise 