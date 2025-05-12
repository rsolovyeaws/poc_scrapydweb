#!/usr/bin/env python3
import os
import time
import signal
import sys
import structlog

from dotenv import load_dotenv
from consumer import RabbitMQConsumer
from scrapyd_client import ScrapydClient

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
)
logger = structlog.get_logger()

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle termination signals for graceful shutdown"""
    global running
    logger.info("Received shutdown signal, stopping services...", signal=sig)
    running = False

# Set up signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Initialize and run the task processor"""
    # Environment variables
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_pass = os.getenv("RABBITMQ_PASSWORD", "guest")
    queue_name = os.getenv("RABBITMQ_QUEUE", "scraper_tasks")
    api_gateway_url = os.getenv("API_GATEWAY_URL", "http://api-gateway:5000")
    
    try:
        # Initialize Scrapyd client
        scrapyd_client = ScrapydClient(base_url=api_gateway_url)
        
        # Initialize and start RabbitMQ consumer
        consumer = RabbitMQConsumer(
            host=rabbitmq_host,
            port=rabbitmq_port,
            username=rabbitmq_user,
            password=rabbitmq_pass,
            queue_name=queue_name,
            scrapyd_client=scrapyd_client
        )
        
        logger.info("Starting RabbitMQ consumer", 
                    queue=queue_name, 
                    rabbitmq_host=rabbitmq_host)
        
        # Start consuming messages
        consumer.start()
        
        # Keep the main thread alive until signal is received
        while running:
            time.sleep(1)
            
        # Graceful shutdown
        logger.info("Shutting down consumer...")
        consumer.stop()
        
    except Exception as e:
        logger.error("Error in main process", error=str(e), exc_info=True)
        sys.exit(1)
    
    logger.info("Task processor shutdown complete")
    sys.exit(0)

if __name__ == "__main__":
    main() 