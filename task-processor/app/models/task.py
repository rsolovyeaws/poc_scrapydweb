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
    
    def to_scrapyd_params(self) -> Dict[str, Any]:
        """
        Convert the task to parameters for Scrapyd API.
        
        Returns:
            Dictionary with parameters for the Scrapyd API
        """
        # Updated to match the API Gateway's expected format
        params = {
            "project": self.project,
            "spider": self.spider,
            "settings": self.settings or {},
            "kwargs": self.args or {},
            "jobid": self.task_id
        }
        
        # Add authentication parameters if enabled
        if self.auth_enabled:
            params["auth_enabled"] = True
            params["username"] = self.username
            params["password"] = self.password
        
        # Add proxy if specified
        if self.proxy:
            params["proxy"] = self.proxy
        
        return params 