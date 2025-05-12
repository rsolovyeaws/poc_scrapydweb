#!/usr/bin/env python3
import pika
import json
import uuid
import os

# Create a unique task ID
task_id = str(uuid.uuid4())

# Create the task payload - updated with correct project and spider names
task = {
    "task_id": task_id,
    "project": "demo-1.0-py3.10",
    "spider": "quotes_spa",
    "settings": {
        "LOG_LEVEL": "INFO",
        "CONCURRENT_REQUESTS": 8
    },
    "args": {
        "start_url": "https://example.com"
    },
    "priority": 0,
    "status": "pending"
}

# Convert to JSON
message = json.dumps(task)

# Get RabbitMQ connection parameters from environment
rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
rabbitmq_pass = os.getenv("RABBITMQ_PASSWORD", "guest")
queue_name = os.getenv("RABBITMQ_QUEUE", "scraper_tasks")

try:
    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        credentials=credentials
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Make sure the queue exists
    channel.queue_declare(queue=queue_name, durable=True)
    
    # Set message properties
    properties = pika.BasicProperties(
        delivery_mode=2,  # Make message persistent
        content_type='application/json',
        message_id=task_id
    )
    
    # Publish the message
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=message,
        properties=properties
    )
    
    print(f"Published task {task_id} to {queue_name}")
    print(f"Project: {task['project']}, Spider: {task['spider']}")
    
    # Close the connection
    connection.close()
    
except Exception as e:
    print(f"Error publishing task: {str(e)}") 