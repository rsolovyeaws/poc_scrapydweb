import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import prometheus_client
from prometheus_client import Counter, Gauge, generate_latest

from config import CONFIG
from proxy import proxy_manager

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Prometheus metrics
PROXY_REQUESTS = Counter('proxy_requests_total', 'Total number of proxy requests', ['proxy'])
PROXY_ERRORS = Counter('proxy_errors_total', 'Total number of proxy errors', ['proxy'])
HEALTHY_PROXIES = Gauge('healthy_proxies', 'Number of healthy proxies')
TOTAL_PROXIES = Gauge('total_proxies', 'Total number of proxies')

# Initialize metrics
def update_metrics():
    proxy_data = proxy_manager.get_all_proxies()
    total = len(proxy_data['proxies'])
    healthy = sum(1 for p in proxy_data['proxies'] if proxy_data['health_status'].get(p, {}).get('healthy', False))
    TOTAL_PROXIES.set(total)
    HEALTHY_PROXIES.set(healthy)

# Routes
@app.route('/proxy', methods=['GET'])
def get_proxy():
    """Get the next proxy in rotation"""
    proxy = proxy_manager.get_next_proxy()
    if proxy:
        PROXY_REQUESTS.labels(proxy=proxy).inc()
        return jsonify({'proxy': proxy})
    else:
        return jsonify({'error': 'No healthy proxies available'}), 503

@app.route('/proxies', methods=['GET'])
def get_all_proxies():
    """Get all proxies and their health status"""
    return jsonify(proxy_manager.get_all_proxies())

@app.route('/proxy/add', methods=['POST'])
def add_proxy():
    """Add a new proxy to the rotation"""
    data = request.json
    if not data or 'proxy' not in data:
        return jsonify({'error': 'Missing proxy parameter'}), 400
    
    proxy = data['proxy']
    if proxy_manager.add_proxy(proxy):
        update_metrics()
        return jsonify({'status': 'success', 'message': f'Added proxy {proxy}'})
    else:
        return jsonify({'status': 'error', 'message': 'Proxy already exists'}), 409

@app.route('/proxy/remove', methods=['POST'])
def remove_proxy():
    """Remove a proxy from rotation"""
    data = request.json
    if not data or 'proxy' not in data:
        return jsonify({'error': 'Missing proxy parameter'}), 400
    
    proxy = data['proxy']
    if proxy_manager.remove_proxy(proxy):
        update_metrics()
        return jsonify({'status': 'success', 'message': f'Removed proxy {proxy}'})
    else:
        return jsonify({'status': 'error', 'message': 'Proxy not found'}), 404

@app.route('/proxy/reset', methods=['POST'])
def reset_proxy():
    """Reset a proxy's health status"""
    data = request.json
    if not data or 'proxy' not in data:
        return jsonify({'error': 'Missing proxy parameter'}), 400
    
    proxy = data['proxy']
    if proxy_manager.reset_proxy(proxy):
        return jsonify({'status': 'success', 'message': f'Reset proxy {proxy}'})
    else:
        return jsonify({'status': 'error', 'message': 'Proxy not found'}), 404

@app.route('/proxy/check', methods=['POST'])
def check_proxy():
    """Manually trigger a health check for a proxy"""
    data = request.json
    if not data or 'proxy' not in data:
        return jsonify({'error': 'Missing proxy parameter'}), 400
    
    proxy = data['proxy']
    proxies = proxy_manager.get_all_proxies()['proxies']
    if proxy not in proxies:
        return jsonify({'error': 'Proxy not found'}), 404
    
    # Trigger health check in a separate thread
    import threading
    threading.Thread(target=proxy_manager._check_proxy_health, args=(proxy,)).start()
    
    return jsonify({'status': 'success', 'message': f'Health check triggered for {proxy}'})

@app.route('/metrics', methods=['GET'])
def metrics():
    """Export Prometheus metrics"""
    update_metrics()
    return generate_latest(), 200, {'Content-Type': 'text/plain'}

@app.route('/status', methods=['GET'])
def status():
    """Service health check endpoint"""
    update_metrics()
    proxy_data = proxy_manager.get_all_proxies()
    total = len(proxy_data['proxies'])
    healthy = sum(1 for p in proxy_data['proxies'] if proxy_data['health_status'].get(p, {}).get('healthy', False))
    
    return jsonify({
        'status': 'ok',
        'total_proxies': total,
        'healthy_proxies': healthy,
        'rotation_strategy': proxy_data['rotation_strategy'],
        'version': '1.0.0'
    })

if __name__ == '__main__':
    # Update metrics on startup
    update_metrics()
    
    # Start the Flask app
    app.run(
        host=CONFIG['host'],
        port=CONFIG['port'],
        debug=CONFIG['debug']
    ) 