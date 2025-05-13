#!/usr/bin/env python3
"""
User-Agent Rotation Service
----------------------------
A simple Flask API service that:
1. Provides random User-Agents for web scraping
2. Supports different device types (desktop, mobile, tablet)
3. Supports different browser families (chrome, firefox, safari, edge)
4. Tracks usage statistics
"""

import os
import json
import random
import logging
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Data storage paths
DATA_DIR = os.environ.get('DATA_DIR', '/data')
USER_AGENTS_FILE = os.path.join(DATA_DIR, 'user_agents.json')
STATS_FILE = os.path.join(DATA_DIR, 'usage_stats.json')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Default User-Agents by category if no file exists
DEFAULT_USER_AGENTS = {
    "desktop": {
        "chrome": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        ],
        "firefox": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ],
        "safari": [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"
        ],
        "edge": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.37"
        ]
    },
    "mobile": {
        "chrome": [
            "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
        ],
        "safari": [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        ]
    },
    "tablet": {
        "chrome": [
            "Mozilla/5.0 (Linux; Android 11; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 10; SM-T500) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36"
        ],
        "safari": [
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 14_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Mobile/15E148 Safari/604.1"
        ]
    }
}

# Default stats template
DEFAULT_STATS = {
    "total_requests": 0,
    "requests_by_type": {
        "desktop": 0,
        "mobile": 0,
        "tablet": 0
    },
    "requests_by_browser": {
        "chrome": 0,
        "firefox": 0,
        "safari": 0,
        "edge": 0
    },
    "last_updated": datetime.now().isoformat()
}

# Load user agents from file or use defaults
def load_user_agents():
    try:
        if os.path.exists(USER_AGENTS_FILE):
            with open(USER_AGENTS_FILE, 'r') as f:
                return json.load(f)
        else:
            # First-time initialization - save defaults
            with open(USER_AGENTS_FILE, 'w') as f:
                json.dump(DEFAULT_USER_AGENTS, f, indent=2)
            return DEFAULT_USER_AGENTS
    except Exception as e:
        logger.error(f"Error loading user agents: {e}")
        return DEFAULT_USER_AGENTS

# Load usage stats
def load_stats():
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        else:
            # First-time initialization - save defaults
            with open(STATS_FILE, 'w') as f:
                json.dump(DEFAULT_STATS, f, indent=2)
            return DEFAULT_STATS
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        return DEFAULT_STATS.copy()

# Update and save stats
def update_stats(device_type, browser):
    stats = load_stats()
    stats["total_requests"] += 1
    
    # Update device type stats
    if device_type in stats["requests_by_type"]:
        stats["requests_by_type"][device_type] += 1
    
    # Update browser stats
    if browser in stats["requests_by_browser"]:
        stats["requests_by_browser"][browser] += 1
    
    stats["last_updated"] = datetime.now().isoformat()
    
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

# Global variables
user_agents = load_user_agents()
stats = load_stats()

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/user-agent', methods=['GET'])
def get_user_agent():
    """Get a random user agent based on type and browser preferences"""
    device_type = request.args.get('type', 'desktop')
    browser = request.args.get('browser')
    
    # Validate device type
    if device_type not in user_agents:
        device_type = 'desktop'  # Default to desktop
    
    # If browser specified, validate it exists for this device type
    if browser and (browser not in user_agents[device_type] or not user_agents[device_type][browser]):
        browser = None  # Invalid browser, will pick randomly
    
    # Select random browser if not specified
    if not browser:
        available_browsers = list(user_agents[device_type].keys())
        browser = random.choice(available_browsers)
    
    # Get random user agent from the selected category
    user_agent = random.choice(user_agents[device_type][browser])
    
    # Update stats
    update_stats(device_type, browser)
    
    return jsonify({
        "user_agent": user_agent,
        "type": device_type,
        "browser": browser
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get usage statistics"""
    return jsonify(load_stats())

@app.route('/api/user-agents', methods=['GET'])
def list_user_agents():
    """List all available user agents"""
    return jsonify(load_user_agents())

@app.route('/api/user-agents', methods=['POST'])
def add_user_agent():
    """Add a new user agent to the database"""
    data = request.json
    
    if not data or not all(k in data for k in ['user_agent', 'type', 'browser']):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Validate type and browser
    device_type = data['type']
    browser = data['browser']
    user_agent_str = data['user_agent']
    
    if device_type not in user_agents:
        return jsonify({"error": f"Invalid device type: {device_type}"}), 400
    
    if browser not in user_agents[device_type]:
        # Create new browser category if it doesn't exist
        user_agents[device_type][browser] = []
    
    # Add the new user agent
    if user_agent_str not in user_agents[device_type][browser]:
        user_agents[device_type][browser].append(user_agent_str)
        
        # Save to file
        try:
            with open(USER_AGENTS_FILE, 'w') as f:
                json.dump(user_agents, f, indent=2)
            
            return jsonify({
                "status": "success",
                "message": "User agent added",
                "type": device_type,
                "browser": browser
            })
        except Exception as e:
            logger.error(f"Error saving user agents: {e}")
            return jsonify({"error": "Failed to save user agent"}), 500
    else:
        return jsonify({
            "status": "warning", 
            "message": "User agent already exists"
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Log startup information
    logger.info(f"Starting User-Agent Rotation Service on {host}:{port}")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Loaded {sum(len(agents) for device in user_agents.values() for agents in device.values())} user agents")
    
    app.run(host=host, port=port, debug=debug) 