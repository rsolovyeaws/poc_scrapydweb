#!/usr/bin/env python3
import json
import pika
import structlog
import threading
import time
from typing import Optional, Dict, Any
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from models import SpiderTask
from scrapyd_client import ScrapydClient

class RabbitMQConsumer:
    """Consumer for RabbitMQ messages that contain spider tasks"""
    
    def __init__(
        self,
        host: str = "rabbitmq",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        queue_name: str = "scraper_tasks",
        scrapyd_client: Optional[ScrapydClient] = None,
        reconnect_delay: int = 5
    ):
        """
        Initialize a RabbitMQ consumer.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            queue_name: Name of the queue to consume from
            scrapyd_client: Client for interacting with Scrapyd
            reconnect_delay: Seconds to wait between reconnection attempts
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.queue_name = queue_name
        self.scrapyd_client = scrapyd_client or ScrapydClient()
        self.reconnect_delay = reconnect_delay
        self.should_stop = False
        self.consume_thread = None
        self.logger = structlog.get_logger()
        
        # Connection objects
        self.connection = None
        self.channel = None
    
    def connect(self) -> None:
        """Establish connection to RabbitMQ"""
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=600,  # 10 minutes heartbeat
            blocked_connection_timeout=300  # 5 minutes timeout
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare the queue (create if doesn't exist)
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        
        # Set QoS to prevent overloading this consumer
        self.channel.basic_qos(prefetch_count=1)
        
        self.logger.info("Connected to RabbitMQ", 
                         host=self.host, 
                         port=self.port,
                         queue=self.queue_name)
    
    def start(self) -> None:
        """Start consuming messages in a separate thread"""
        if self.consume_thread and self.consume_thread.is_alive():
            self.logger.warning("Consumer is already running")
            return
        
        self.should_stop = False
        self.consume_thread = threading.Thread(target=self._consume_loop)
        self.consume_thread.daemon = True
        self.consume_thread.start()
        
        self.logger.info("Started RabbitMQ consumer thread")
    
    def stop(self) -> None:
        """Stop consuming messages and close connection"""
        self.should_stop = True
        
        if self.connection and self.connection.is_open:
            self.connection.close()
        
        if self.consume_thread and self.consume_thread.is_alive():
            self.consume_thread.join(timeout=5.0)
        
        self.logger.info("Stopped RabbitMQ consumer")
    
    def _consume_loop(self) -> None:
        """Main loop for consuming messages with automatic reconnection"""
        while not self.should_stop:
            try:
                if not self.connection or self.connection.is_closed:
                    self.connect()
                
                # Start consuming messages
                self.channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._process_message,
                    auto_ack=False
                )
                
                self.logger.info("Started consuming messages", queue=self.queue_name)
                
                # Start the IOLoop to process messages
                self.channel.start_consuming()
                
            except (AMQPConnectionError, ChannelClosedByBroker) as e:
                if not self.should_stop:
                    self.logger.error("Connection to RabbitMQ lost, reconnecting...", 
                                     error=str(e),
                                     reconnect_delay=self.reconnect_delay)
                    time.sleep(self.reconnect_delay)
            except Exception as e:
                self.logger.error("Unexpected error in consumer loop", 
                                 error=str(e),
                                 exc_info=True)
                if not self.should_stop:
                    time.sleep(self.reconnect_delay)
    
    def _process_message(self, ch, method, properties, body) -> None:
        """
        Process a message from RabbitMQ.
        
        Args:
            ch: Channel
            method: Method frame
            properties: Properties
            body: Message body
        """
        try:
            # Parse message body
            message = json.loads(body)
            
            self.logger.info("Received message", 
                            message_id=properties.message_id,
                            content_type=properties.content_type)
            
            # Process the message based on its type
            task = SpiderTask(**message)
            
            # Schedule the spider using the Scrapyd client
            response = self.scrapyd_client.schedule_spider(**task.to_scrapyd_params())
            
            # Log the result
            self.logger.info("Scheduled spider task", 
                            task_id=task.task_id,
                            run_id=response.get("run_id"),
                            job_id=response.get("jobid"),
                            status=response.get("status"))
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse message as JSON", 
                             error=str(e),
                             body=body)
            # Reject the message without requeuing as it's malformed
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        
        except Exception as e:
            self.logger.error("Error processing message", 
                             error=str(e),
                             body=body,
                             exc_info=True)
            # Reject and requeue the message to try again later
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)
    
    def publish_task(self, task: SpiderTask) -> None:
        """
        Publish a task to the queue.
        
        Args:
            task: The spider task to publish
        """
        try:
            if not self.connection or self.connection.is_closed:
                self.connect()
            
            # Convert task to JSON
            message = task.model_dump_json()
            
            # Set message properties
            properties = pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json',
                message_id=task.task_id,
                priority=task.priority
            )
            
            # Publish the message
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=message,
                properties=properties
            )
            
            self.logger.info("Published task", 
                           task_id=task.task_id,
                           project=task.project,
                           spider=task.spider)
            
        except Exception as e:
            self.logger.error("Failed to publish task", 
                             error=str(e),
                             task_id=task.task_id,
                             exc_info=True)
            raise 