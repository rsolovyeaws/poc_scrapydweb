#!/usr/bin/env python3
import pika
import json
import uuid
import argparse
import sys

def publish_task(host, port, username, password, queue, project, spider, settings=None, args=None):
    """Publish a test spider task to RabbitMQ"""
    
    # Create a unique task ID
    task_id = str(uuid.uuid4())
    
    # Create the task payload
    task = {
        "task_id": task_id,
        "project": project,
        "spider": spider,
        "settings": settings or {},
        "args": args or {},
        "priority": 0,
        "status": "pending"
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
        print(f"Project: {project}, Spider: {spider}")
        
        # Close the connection
        connection.close()
        
        return True
    
    except Exception as e:
        print(f"Error publishing task: {str(e)}")
        return False

def parse_settings(settings_list):
    """Parse settings from the command line"""
    if not settings_list:
        return {}
    
    settings = {}
    for setting in settings_list:
        if "=" in setting:
            key, value = setting.split("=", 1)
            settings[key.strip()] = value.strip()
    
    return settings

def parse_args(args_list):
    """Parse spider arguments from the command line"""
    if not args_list:
        return {}
    
    spider_args = {}
    for arg in args_list:
        if "=" in arg:
            key, value = arg.split("=", 1)
            spider_args[key.strip()] = value.strip()
    
    return spider_args

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish a test spider task to RabbitMQ")
    
    parser.add_argument("--host", default="localhost", help="RabbitMQ host")
    parser.add_argument("--port", type=int, default=5672, help="RabbitMQ port")
    parser.add_argument("--user", default="guest", help="RabbitMQ username")
    parser.add_argument("--password", default="guest", help="RabbitMQ password")
    parser.add_argument("--queue", default="scraper_tasks", help="Queue name")
    parser.add_argument("--project", required=True, help="Scrapy project name")
    parser.add_argument("--spider", required=True, help="Spider name")
    parser.add_argument("--setting", action="append", help="Spider settings (key=value)")
    parser.add_argument("--arg", action="append", help="Spider arguments (key=value)")
    
    args = parser.parse_args()
    
    settings = parse_settings(args.setting)
    spider_args = parse_args(args.arg)
    
    success = publish_task(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        queue=args.queue,
        project=args.project,
        spider=args.spider,
        settings=settings,
        args=spider_args
    )
    
    sys.exit(0 if success else 1) 