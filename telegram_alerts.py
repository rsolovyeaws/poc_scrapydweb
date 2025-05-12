#!/usr/bin/env python3
"""
Simple script to send alerts to Telegram.
This can be used as a webhook target or manually called.
"""

import os
import sys
import json
import logging
import time
from pathlib import Path
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
SPAM_PROTECTION_SECONDS = int(os.environ.get('SPAM_PROTECTION_SECONDS', '60'))
LAST_MESSAGE_FILE = Path('/tmp/last_telegram_message.txt')

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_telegram_message(message, parse_mode='HTML'):
    """Send message to Telegram with spam protection"""
    # Check for recent identical messages to prevent spam
    current_time = time.time()
    
    if LAST_MESSAGE_FILE.exists():
        try:
            with open(LAST_MESSAGE_FILE, 'r') as f:
                last_data = f.read().strip().split('|', 1)
                if len(last_data) == 2:
                    last_time, last_message = last_data
                    last_time = float(last_time)
                    
                    # If same message was sent recently and time difference is less than threshold, skip
                    if (last_message == message and 
                        current_time - last_time < SPAM_PROTECTION_SECONDS):
                        logger.info(f"Skipping duplicate message (sent {current_time - last_time:.1f}s ago)")
                        return True
        except Exception as e:
            logger.warning(f"Failed to read last message data: {e}")
    
    # Proceed with sending the message
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': parse_mode
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent successfully: {response.json()}")
        
        # Save this message to prevent duplicates
        try:
            with open(LAST_MESSAGE_FILE, 'w') as f:
                f.write(f"{current_time}|{message}")
        except Exception as e:
            logger.warning(f"Failed to save message data: {e}")
            
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send message: {e}")
        return False

def format_alert(alert_data):
    """Format alert data for Telegram message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if isinstance(alert_data, dict):
        # Проверяем, содержит ли алерт достаточно информации для отправки
        if 'labels' not in alert_data or 'annotations' not in alert_data:
            logger.warning(f"Skipping malformed alert without required fields: {alert_data}")
            return None
            
        if 'alertname' not in alert_data.get('labels', {}) or not alert_data.get('labels', {}).get('alertname'):
            logger.warning(f"Skipping alert without alertname: {alert_data}")
            return None
            
        # Пропускаем алерты с suppress_default=true
        if alert_data.get('labels', {}).get('suppress_default') == "true":
            logger.info(f"Skipping alert marked as suppress_default: {alert_data.get('labels', {}).get('alertname')}")
            return None
            
        level = alert_data.get('status', 'alert').upper()
        name = alert_data.get('labels', {}).get('alertname', 'Unknown Alert')
        severity = alert_data.get('labels', {}).get('severity', 'info')
        
        # Получаем summary и description из annotations
        summary = alert_data.get('annotations', {}).get('summary', 'Нет информации')
        description = alert_data.get('annotations', {}).get('description', 'Подробное описание отсутствует')
        
        # Если summary или description отсутствуют, не отправляем пустой алерт
        if not summary or summary == 'No summary':
            logger.warning(f"Skipping alert with empty summary: {name}")
            return None
        
        # Устанавливаем цвет в зависимости от severity
        color = "🟢"  # По умолчанию info
        if severity == "warning":
            color = "🟠"
        elif severity == "critical":
            color = "🔴"
        
        message = (
            f"{color} <b>{level}: {name}</b>\n"
            f"<i>{timestamp}</i>\n\n"
            f"<b>Summary:</b> {summary}\n"
            f"<b>Description:</b> {description}"
        )
    else:
        # Проверяем, не пустой ли алерт или слишком короткий
        if not alert_data or len(str(alert_data).strip()) < 5:
            logger.warning(f"Skipping empty or too short alert: '{alert_data}'")
            return None
            
        # Simple text alert
        message = (
            f"🔵 <b>ALERT</b>\n"
            f"<i>{timestamp}</i>\n\n"
            f"{alert_data}"
        )
    
    return message

def main():
    """Main function to handle alerts"""
    # Check if data is passed as an argument
    if len(sys.argv) > 1:
        message = sys.argv[1]
        formatted_alert = format_alert(message)
        if formatted_alert:
            send_telegram_message(formatted_alert)
        else:
            logger.info("Alert was filtered and not sent")
        return
    
    # Check if data is piped in
    if not sys.stdin.isatty():
        try:
            data = sys.stdin.read().strip()
            # Try to parse as JSON
            try:
                alert_data = json.loads(data)
                # Handle Prometheus Alertmanager format
                if 'alerts' in alert_data:
                    alerts_sent = 0
                    for alert in alert_data['alerts']:
                        formatted_alert = format_alert(alert)
                        if formatted_alert:
                            send_telegram_message(formatted_alert)
                            alerts_sent += 1
                    logger.info(f"Processed {len(alert_data['alerts'])} alerts, sent {alerts_sent}")
                else:
                    formatted_alert = format_alert(alert_data)
                    if formatted_alert:
                        send_telegram_message(formatted_alert)
                    else:
                        logger.info("Alert was filtered and not sent")
            except json.JSONDecodeError:
                # Not JSON, just send as text
                formatted_alert = format_alert(data)
                if formatted_alert:
                    send_telegram_message(formatted_alert)
                else:
                    logger.info("Alert was filtered and not sent")
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            sys.exit(1)
    else:
        logger.error("No alert data provided. Pass as argument or pipe to script.")
        sys.exit(1)

if __name__ == '__main__':
    main() 