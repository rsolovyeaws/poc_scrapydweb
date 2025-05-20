#!/usr/bin/env python3
"""
Test script for demonstrating User-Agent rotation
"""
import argparse
import json
import requests
import time

def get_user_agent(base_url, device_type=None, browser=None):
    """Get a random user agent from the rotation service"""
    url = f"{base_url}/api/user-agent"
    params = {}
    
    if device_type:
        params['type'] = device_type
    
    if browser:
        params['browser'] = browser
        
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Failed to get User-Agent: {e}")
        return None

def get_stats(base_url):
    """Get usage statistics from the User-Agent rotation service"""
    try:
        response = requests.get(f"{base_url}/api/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Failed to get stats: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Test User-Agent Rotation Service')
    parser.add_argument('--url', default='http://localhost:5002', help='Base URL of the User-Agent service')
    parser.add_argument('--count', type=int, default=10, help='Number of User-Agents to request')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests in seconds')
    parser.add_argument('--type', choices=['desktop', 'mobile', 'tablet'], help='Device type')
    parser.add_argument('--browser', choices=['chrome', 'firefox', 'safari', 'edge'], help='Browser family')
    
    args = parser.parse_args()
    
    print(f"Testing User-Agent rotation service at {args.url}")
    print(f"Requesting {args.count} User-Agents")
    if args.type:
        print(f"Device type: {args.type}")
    if args.browser:
        print(f"Browser: {args.browser}")
    
    print("\nRequesting User-Agents:")
    print("-" * 80)
    
    for i in range(args.count):
        result = get_user_agent(args.url, args.type, args.browser)
        if result:
            print(f"{i+1}. [{result['type']}] [{result['browser']}]: {result['user_agent']}")
        time.sleep(args.delay)
    
    print("\nUser-Agent Service Statistics:")
    print("-" * 80)
    
    stats = get_stats(args.url)
    if stats:
        print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main() 