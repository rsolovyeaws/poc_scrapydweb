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
    
    def schedule_spider(self, **kwargs):
        """
        Schedules a spider by calling the API Gateway.

        This method intelligently constructs the request body by separating
        standard API Gateway parameters from custom spider arguments, which are
        nested under 'kwargs'.
        """
        self.logger.info("Preparing to schedule spider", raw_args=kwargs)

        # Standard parameters expected by the API Gateway's SpiderRequest model
        standard_params = [
            'project', 'spider', 'settings', 'jobid', '_version',
            'auth_enabled', 'username', 'password', 'proxy',
            'user_agent_type', 'user_agent'
        ]

        # Payload for the API Gateway
        payload = {}
        # Dictionary for custom spider arguments
        spider_kwargs = {}

        # Separate standard params from custom spider args
        for key, value in kwargs.items():
            if key in standard_params:
                payload[key] = value
            else:
                spider_kwargs[key] = value

        # Add the custom arguments under the 'kwargs' key
        if spider_kwargs:
            payload['kwargs'] = spider_kwargs
            
        self.logger.info("Scheduling spider with payload", payload=payload)
        return self._post("schedule", json=payload)
    
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

    def _post(self, endpoint: str, json: dict) -> Dict[str, Any]:
        """
        Helper method to perform a POST request to the API Gateway.
        
        Args:
            endpoint: API endpoint to call
            json: JSON payload to send
            
        Returns:
            Dictionary with response data
        """
        try:
            response = requests.post(f"{self.base_url}/{endpoint}", json=json)
            response.raise_for_status()
            result = response.json()
            
            self.logger.info("Request successful", endpoint=endpoint, status=result.get("status"))
            
            return result
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to perform request", 
                             error=str(e),
                             endpoint=endpoint)
            raise
        except Exception as e:
            self.logger.error("An unexpected error occurred", error=str(e))
            return {"status": "error", "message": "An unexpected error occurred"} 