#!/usr/bin/env python3
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    """Status of a spider task"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

class SpiderTask(BaseModel):
    """Model representing a spider task from RabbitMQ"""
    task_id: str = Field(..., description="Unique identifier for the task")
    project: str = Field(..., description="Scrapy project name")
    spider: str = Field(..., description="Spider name")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Scrapy settings")
    args: Optional[Dict[str, Any]] = Field(default=None, description="Spider arguments")
    priority: int = Field(default=0, description="Task priority (0-100)")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    callback_url: Optional[str] = Field(default=None, description="Webhook URL for task completion notification")
    # Added auth and proxy parameters
    auth_enabled: bool = Field(default=False, description="Whether authentication is enabled")
    username: Optional[str] = Field(default=None, description="Authentication username")
    password: Optional[str] = Field(default=None, description="Authentication password")
    proxy: Optional[str] = Field(default=None, description="Proxy URL for the spider")
    # Add user agent parameters
    user_agent_type: Optional[str] = Field(default=None, description="Type of User-Agent to use")
    user_agent: Optional[str] = Field(default=None, description="Custom User-Agent string")
    
    def to_scrapyd_params(self) -> Dict[str, Any]:
        """
        Convert the task to a flat dictionary of parameters for the ScrapydClient.
        
        The ScrapydClient is responsible for structuring this into the final 
        payload for the API Gateway.
        
        Returns:
            A flat dictionary with all task parameters.
        """
        # Start with the base parameters
        params = {
            "project": self.project,
            "spider": self.spider,
            "jobid": self.task_id,  # Use task_id as the jobid for tracking
            "run_id": self.task_id   # Pass task_id as run_id to the spider
        }

        if self.settings:
            params["settings"] = self.settings

        # Add spider arguments from the 'args' field
        if self.args:
            params.update(self.args)
        
        # Add authentication parameters if enabled
        if self.auth_enabled:
            params["auth_enabled"] = True
            params["username"] = self.username
            params["password"] = self.password
        
        # Add proxy if specified
        if self.proxy:
            params["proxy"] = self.proxy
            
        # Add user agent parameters
        if self.user_agent:
            params["user_agent"] = self.user_agent
        elif self.user_agent_type:
            params["user_agent_type"] = self.user_agent_type
        
        return params 