#!/usr/bin/env python3
import pika
import json
import uuid
import datetime
import argparse

def publish_task(host, port, username, password, queue, params, use_proxy_rotation=False):
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
        elif not key in ["project", "spider", "_version", "jobid", "user_agent_type", "user_agent"]:
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
    }
    
    # Add user agent parameters - make sure they're direct parameters, not in args
    if "user_agent" in params:
        task["user_agent"] = params.get("user_agent")
    elif "user_agent_type" in params:
        task["user_agent_type"] = params.get("user_agent_type", "desktop")
    
    # Only add proxy field if not using rotation
    if not use_proxy_rotation and "proxy" in params:
        task["proxy"] = params.get("proxy")
        
    # Display message about proxy mode
    if use_proxy_rotation:
        print(f"Using proxy rotation for task {task_id}")
    elif "proxy" in params:
        print(f"Using fixed proxy for task {task_id}: {params.get('proxy')}")
    else:
        print(f"No proxy specified for task {task_id}")
    
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
        
        # Display user-agent information
        if "user_agent" in params:
            print(f"User-Agent: {params.get('user_agent')} (custom)")
        else:
            print(f"User-Agent Type: {params.get('user_agent_type', 'desktop')} (rotation)")
        
        # Display proxy information
        if use_proxy_rotation:
            print("Proxy: Автоматическая ротация")
        elif "proxy" in params:
            print(f"Proxy: {params.get('proxy')} (фиксированный)")
        else:
            print("Proxy: Не указан")
            
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
        "auth_enabled": "true",
        "username": "admin",
        "password": "admin",
        "proxy": "http://tinyproxy1:8888",
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
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication")
    parser.add_argument("--username", help="Auth username")
    parser.add_argument("--password", help="Auth password")
    
    # Proxy rotation options
    parser.add_argument("--use-proxy-rotation", action="store_true", 
                        help="Use automatic proxy rotation (overrides --proxy)")
    parser.add_argument("--no-proxy-rotation", action="store_true", 
                        help="Don't use proxy rotation (use fixed proxy if specified)")
    parser.add_argument("--proxy", 
                        help="Proxy URL (used only if --use-proxy-rotation is not set)")
    
    # New parameters
    parser.add_argument("--count", type=int, default=1, help="Number of spider tasks to send (default: 1)")
    parser.add_argument("--user-agent-type", default="desktop", choices=["desktop", "mobile", "tablet"], 
                        help="Type of User-Agent to use (default: desktop)")
    parser.add_argument("--user-agent", 
                        help="Specify a custom User-Agent string (overrides --user-agent-type)")
    
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
    
    # Set custom user-agent if specified
    if args.user_agent:
        params["user_agent"] = args.user_agent
        
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
    elif args.no_auth:
        params["auth_enabled"] = "false"
    if args.username:
        params["username"] = args.username
    if args.password:
        params["password"] = args.password
    
    # Handle proxy configuration
    use_proxy_rotation = args.use_proxy_rotation
    
    # --no-proxy-rotation overrides --use-proxy-rotation
    if args.no_proxy_rotation:
        use_proxy_rotation = False
    
    # Set proxy if specified and not using rotation
    if args.proxy and not use_proxy_rotation:
        params["proxy"] = args.proxy
    elif use_proxy_rotation and "proxy" in params:
        # Remove proxy parameter completely when using rotation
        del params["proxy"]
    
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
            params=current_params,
            use_proxy_rotation=use_proxy_rotation
        )
        
        if success:
            print(f"Task {i}/{args.count} published successfully")
        else:
            print(f"Failed to publish task {i}/{args.count}") 