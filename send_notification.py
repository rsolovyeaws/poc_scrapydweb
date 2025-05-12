#!/usr/bin/env python3
"""
Utility script to send custom notifications to Telegram.
Usage:
  ./send_notification.py "Заголовок сообщения" "Подробное описание сообщения"
  ./send_notification.py --severity=warning "Внимание!" "Произошло важное событие"
"""

import sys
import os
import argparse
from dotenv import load_dotenv
from telegram_alerts import send_telegram_message, format_alert

def main():
    """Send a custom notification to Telegram"""
    parser = argparse.ArgumentParser(description='Send notifications to Telegram')
    parser.add_argument('summary', help='Заголовок сообщения')
    parser.add_argument('description', help='Подробное описание сообщения')
    parser.add_argument('--severity', default='info', choices=['info', 'warning', 'critical'],
                        help='Уровень важности (info, warning, critical)')
    parser.add_argument('--alertname', default='CustomAlert',
                        help='Название предупреждения')
    parser.add_argument('--instance', default='manual-notification',
                        help='Имя узла/источника')
    
    args = parser.parse_args()

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
    
    # Create custom alert
    alert = {
        'status': 'firing',
        'labels': {
            'alertname': args.alertname,
            'instance': args.instance,
            'severity': args.severity
        },
        'annotations': {
            'summary': args.summary,
            'description': args.description
        }
    }
    
    # Format and send the alert
    message = format_alert(alert)
    success = send_telegram_message(message)
    
    if success:
        print("✅ Уведомление успешно отправлено!")
    else:
        print("❌ Не удалось отправить уведомление. Проверьте настройки Telegram")
        sys.exit(1)

if __name__ == '__main__':
    main() 