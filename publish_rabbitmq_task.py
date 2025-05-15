#!/usr/bin/env python3
import pika
import json
import uuid
import datetime
import argparse

def publish_task(host, port, username, password, queue, params):
    """Publish a spider task to RabbitMQ with the same parameters as schedule_egg.sh"""
    
    # Generate a task ID if not provided
    task_id = params.get("jobid", str(uuid.uuid4()))
    
    # Extract settings and args from params
    settings = {}
    args = {}
    
    for key, value in params.items():
        if key.startswith("setting="):
            setting_name = key[8:]  # Remove "setting=" prefix
            settings[setting_name] = value
        elif not key in ["project", "spider", "_version", "jobid", "user_agent_type"]:
            args[key] = value
    
    # Create the task payload
    task = {
        "task_id": task_id,
        "project": params.get("project"),
        "spider": params.get("spider"),
        "settings": settings,
        "args": args,
        "priority": 0,
        "status": "pending",
        # Include special handling for authentication and proxy
        "auth_enabled": params.get("auth_enabled", "false") == "true",
        "username": params.get("username"),
        "password": params.get("password"),
        "proxy": params.get("proxy"),
        "user_agent_type": params.get("user_agent_type", "desktop")
    }
    
    # Convert to JSON
    message = json.dumps(task)
    
    try:
        # Connect to RabbitMQ
        credentials = pika.PlainCredentials(username, password)
        parameters = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Make sure the queue exists
        channel.queue_declare(queue=queue, durable=True)
        
        # Set message properties
        properties = pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
            content_type='application/json',
            message_id=task_id
        )
        
        # Publish the message
        channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=message,
            properties=properties
        )
        
        print(f"Published task {task_id} to {queue}")
        print(f"Project: {params.get('project')}, Spider: {params.get('spider')}")
        print(f"User-Agent Type: {params.get('user_agent_type', 'desktop')}")
        print(f"Settings: {json.dumps(settings, indent=2)}")
        print(f"Arguments: {json.dumps(args, indent=2)}")
        
        # Close the connection
        connection.close()
        
        return True
    
    except Exception as e:
        print(f"Error publishing task: {str(e)}")
        return False

if __name__ == "__main__":
    # Default parameters from schedule_egg.sh
    default_params = {
        "project": "demo-1.0-py3.10",
        "_version": "1_0",
        "spider": "quotes_spa",
        "jobid": datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S"),
        "setting=CLOSESPIDER_PAGECOUNT": "0",
        "setting=CLOSESPIDER_TIMEOUT": "60",
        "setting=LOG_LEVEL": "INFO",  # Changed from DEBUG to INFO
        "arg1": "val1",
        "auth_enabled": "true",
        "username": "admin",
        "password": "admin",
        "proxy": "http://tinyproxy:8888",
        "user_agent_type": "desktop"  # Default user agent type
    }
    
    parser = argparse.ArgumentParser(description="Publish a spider task to RabbitMQ (matching schedule_egg.sh)")
    
    # RabbitMQ connection parameters
    parser.add_argument("--host", default="localhost", help="RabbitMQ host")
    parser.add_argument("--port", type=int, default=5672, help="RabbitMQ port")
    parser.add_argument("--rmq-user", default="guest", help="RabbitMQ username")
    parser.add_argument("--rmq-password", default="guest", help="RabbitMQ password")
    parser.add_argument("--queue", default="scraper_tasks", help="Queue name")
    
    # Spider parameters (all optional, will use defaults from schedule_egg.sh if not provided)
    parser.add_argument("--project", help="Scrapy project name")
    parser.add_argument("--version", help="Project version")
    parser.add_argument("--spider", help="Spider name")
    parser.add_argument("--jobid", help="Custom job ID")
    parser.add_argument("--setting", action="append", help="Spider settings (key=value)")
    parser.add_argument("--arg", action="append", help="Spider arguments (key=value)")
    parser.add_argument("--auth", action="store_true", help="Enable authentication")
    parser.add_argument("--username", help="Auth username")
    parser.add_argument("--password", help="Auth password")
    parser.add_argument("--proxy", help="Proxy URL")
    
    # New parameters
    parser.add_argument("--count", type=int, default=1, help="Number of spider tasks to send (default: 1)")
    parser.add_argument("--user-agent-type", default="desktop", choices=["desktop", "mobile", "tablet"], 
                        help="Type of User-Agent to use (default: desktop)")
    
    args = parser.parse_args()
    
    # Start with default parameters
    params = default_params.copy()
    
    # Override with command line arguments if provided
    if args.project:
        params["project"] = args.project
    if args.version:
        params["_version"] = args.version
    if args.spider:
        params["spider"] = args.spider
    if args.jobid:
        params["jobid"] = args.jobid
    
    # Set user agent type
    params["user_agent_type"] = args.user_agent_type
        
    # Process settings
    if args.setting:
        for setting in args.setting:
            key, value = setting.split("=", 1)
            params[f"setting={key}"] = value
            
    # Process arguments
    if args.arg:
        for arg in args.arg:
            key, value = arg.split("=", 1)
            params[key] = value
            
    # Auth parameters
    if args.auth:
        params["auth_enabled"] = "true"
    if args.username:
        params["username"] = args.username
    if args.password:
        params["password"] = args.password
    if args.proxy:
        params["proxy"] = args.proxy
    
    # Generate a base timestamp for all jobs
    base_timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
    
    # Publish tasks based on the count parameter
    print(f"Publishing {args.count} spider tasks to RabbitMQ...")
    
    for i in range(1, args.count + 1):
        # Create a unique job ID for each task
        current_params = params.copy()
        current_params["jobid"] = f"{base_timestamp}_{i}"
        
        # Publish the task
        success = publish_task(
            host=args.host,
            port=args.port,
            username=args.rmq_user,
            password=args.rmq_password,
            queue=args.queue,
            params=current_params
        )
        
        if success:
            print(f"Task {i}/{args.count} published successfully")
        else:
            print(f"Failed to publish task {i}/{args.count}") 