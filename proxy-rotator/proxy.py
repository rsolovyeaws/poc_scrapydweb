import json
import os
import random
import time
import threading
import requests
from config import CONFIG

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.health_status = {}
        self.current_index = 0
        self.lock = threading.Lock()
        self.rotation_strategy = CONFIG['rotation_strategy']
        self.data_file = os.path.join(CONFIG['data_dir'], 'proxies.json')
        
        # Initialize proxies from config or stored state
        self._init_proxies()
        
        # Start health check thread
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
    
    def _init_proxies(self):
        """Initialize proxies from config or stored data"""
        # First try to load from saved data
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if 'proxies' in data and isinstance(data['proxies'], list):
                        self.proxies = data['proxies']
                    if 'health_status' in data and isinstance(data['health_status'], dict):
                        self.health_status = data['health_status']
            except Exception as e:
                print(f"Error loading proxies from {self.data_file}: {e}")
        
        # If no proxies loaded or in config, use config proxies
        if not self.proxies and CONFIG['proxies']:
            self.proxies = CONFIG['proxies']
            
        # Initialize health status for any new proxies
        for proxy in self.proxies:
            if proxy not in self.health_status:
                self.health_status[proxy] = {
                    'healthy': True,
                    'last_check': 0,
                    'error_count': 0,
                    'last_error': None
                }
        
        # Save initial state
        self._save_state()
    
    def _save_state(self):
        """Save current state to disk"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump({
                    'proxies': self.proxies,
                    'health_status': self.health_status
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving proxies to {self.data_file}: {e}")
    
    def _check_proxy_health(self, proxy):
        """Check if a proxy is healthy by making a test request"""
        try:
            response = requests.get(
                CONFIG['health_check_url'],
                proxies={'http': proxy, 'https': proxy},
                timeout=CONFIG['health_check_timeout']
            )
            if response.status_code == 200:
                with self.lock:
                    self.health_status[proxy] = {
                        'healthy': True,
                        'last_check': time.time(),
                        'error_count': 0,
                        'last_error': None
                    }
                return True
            else:
                with self.lock:
                    self.health_status[proxy]['healthy'] = False
                    self.health_status[proxy]['last_check'] = time.time()
                    self.health_status[proxy]['error_count'] += 1
                    self.health_status[proxy]['last_error'] = f"Status code: {response.status_code}"
                return False
        except Exception as e:
            with self.lock:
                self.health_status[proxy]['healthy'] = False
                self.health_status[proxy]['last_check'] = time.time()
                self.health_status[proxy]['error_count'] += 1
                self.health_status[proxy]['last_error'] = str(e)
            return False
    
    def _health_check_loop(self):
        """Continuously check health of all proxies on a schedule"""
        while True:
            for proxy in self.proxies:
                self._check_proxy_health(proxy)
            
            # Save state after checking all proxies
            self._save_state()
            
            # Sleep until next check
            time.sleep(CONFIG['health_check_interval'])
    
    def get_next_proxy(self):
        """Get the next proxy according to the current rotation strategy"""
        with self.lock:
            healthy_proxies = [p for p in self.proxies if self.health_status.get(p, {}).get('healthy', False)]
            
            # If no healthy proxies, return None
            if not healthy_proxies:
                return None
            
            # Different rotation strategies
            if self.rotation_strategy == 'random':
                return random.choice(healthy_proxies)
            else:  # Default to round_robin
                # Find next healthy proxy
                if not healthy_proxies:
                    return None
                
                # Ensure current_index is valid
                self.current_index = self.current_index % len(self.proxies)
                
                # Try to find a healthy proxy starting from current_index
                start_index = self.current_index
                while True:
                    proxy = self.proxies[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.proxies)
                    
                    if proxy in healthy_proxies:
                        return proxy
                    
                    # If we've checked all proxies and come back to start, no healthy proxy found
                    if self.current_index == start_index:
                        return None
    
    def get_all_proxies(self):
        """Get all proxies with their health status"""
        with self.lock:
            return {
                'proxies': self.proxies,
                'health_status': self.health_status,
                'rotation_strategy': self.rotation_strategy
            }
    
    def add_proxy(self, proxy):
        """Add a new proxy to the rotation"""
        with self.lock:
            if proxy not in self.proxies:
                self.proxies.append(proxy)
                self.health_status[proxy] = {
                    'healthy': True,
                    'last_check': 0,
                    'error_count': 0,
                    'last_error': None
                }
                self._save_state()
                # Trigger an immediate health check
                threading.Thread(target=self._check_proxy_health, args=(proxy,)).start()
                return True
            return False
    
    def remove_proxy(self, proxy):
        """Remove a proxy from rotation"""
        with self.lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                if proxy in self.health_status:
                    del self.health_status[proxy]
                self._save_state()
                return True
            return False
    
    def reset_proxy(self, proxy):
        """Reset health status for a proxy"""
        with self.lock:
            if proxy in self.health_status:
                self.health_status[proxy] = {
                    'healthy': True,
                    'last_check': 0,
                    'error_count': 0,
                    'last_error': None
                }
                self._save_state()
                # Trigger an immediate health check
                threading.Thread(target=self._check_proxy_health, args=(proxy,)).start()
                return True
            return False

# Create a singleton instance
proxy_manager = ProxyManager() 