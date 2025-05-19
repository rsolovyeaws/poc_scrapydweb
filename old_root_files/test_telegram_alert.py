#!/usr/bin/env python3
"""
Simple script to test Telegram alerts.
The script sends a single message when first run and creates a marker file
to avoid sending duplicate alerts on subsequent runs.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram_alerts import send_telegram_message, format_alert

MARKER_FILE = Path('.telegram_test_sent')

def main():
    """Send a test alert message to Telegram only if not sent previously"""
    # Check if alert was already sent
    if MARKER_FILE.exists():
        print("Test alert was already sent previously.")
        print("To send another test alert, delete the marker file with:")
        print(f"  rm {MARKER_FILE}")
        return

    # Load environment variables from .env file
    load_dotenv()
    
    # Check if Telegram credentials are configured
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or bot_token == 'your_bot_token_here':
        print("Error: TELEGRAM_BOT_TOKEN is not configured in .env file")
        print("Please update the .env file with your Telegram bot token")
        sys.exit(1)
    
    if not chat_id or chat_id == 'your_chat_id_here':
        print("Error: TELEGRAM_CHAT_ID is not configured in .env file")
        print("Please update the .env file with your Telegram chat ID")
        sys.exit(1)
    
    # Create a test alert
    test_alert = {
        'status': 'firing',
        'labels': {
            'alertname': 'SystemStarted',
            'instance': 'monitoring-system',
            'severity': 'info'
        },
        'annotations': {
            'summary': 'Мониторинг запущен',
            'description': 'Система мониторинга и оповещений успешно запущена и настроена.'
        }
    }
    
    # Format and send the alert
    message = format_alert(test_alert)
    success = send_telegram_message(message)
    
    if success:
        print("Test alert sent successfully!")
        print(f"Check your Telegram chat (ID: {chat_id}) for the alert message")
        
        # Create marker file to prevent sending again
        MARKER_FILE.touch()
    else:
        print("Failed to send test alert. Check your Telegram bot configuration.")
        sys.exit(1)

if __name__ == '__main__':
    main() 