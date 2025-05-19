import os
from dotenv import load_dotenv
import yaml
import pathlib

# Load environment variables from .env file if it exists
load_dotenv()

# Base configuration
DEFAULT_CONFIG = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': False,
    'data_dir': '/data',
    'rotation_strategy': 'round_robin',  # Options: round_robin, random
    'health_check_interval': 60,  # Seconds between health checks
    'health_check_timeout': 5,    # Timeout in seconds for health check
    'health_check_url': 'http://httpbin.org/ip',  # URL to check proxy functionality
    'proxies': []  # Will be populated from environment variable
}

def load_config():
    """Load configuration from environment and YAML file"""
    config = DEFAULT_CONFIG.copy()
    
    # Override from environment variables
    if os.environ.get('HOST'):
        config['host'] = os.environ.get('HOST')
    
    if os.environ.get('PORT'):
        config['port'] = int(os.environ.get('PORT'))
    
    if os.environ.get('DEBUG'):
        config['debug'] = os.environ.get('DEBUG').lower() == 'true'
    
    if os.environ.get('DATA_DIR'):
        config['data_dir'] = os.environ.get('DATA_DIR')
    
    if os.environ.get('ROTATION_STRATEGY'):
        config['rotation_strategy'] = os.environ.get('ROTATION_STRATEGY')
    
    if os.environ.get('HEALTH_CHECK_INTERVAL'):
        config['health_check_interval'] = int(os.environ.get('HEALTH_CHECK_INTERVAL'))
    
    if os.environ.get('HEALTH_CHECK_TIMEOUT'):
        config['health_check_timeout'] = int(os.environ.get('HEALTH_CHECK_TIMEOUT'))
    
    if os.environ.get('HEALTH_CHECK_URL'):
        config['health_check_url'] = os.environ.get('HEALTH_CHECK_URL')
    
    # Load proxies from environment variable or from file
    if os.environ.get('PROXIES'):
        config['proxies'] = [proxy.strip() for proxy in os.environ.get('PROXIES').split(',')]
    
    # Ensure data directory exists
    pathlib.Path(config['data_dir']).mkdir(parents=True, exist_ok=True)
    
    # Try to load config from YAML if it exists
    config_path = os.path.join(config['data_dir'], 'config.yaml')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and isinstance(yaml_config, dict):
                    # Update with YAML config but don't override environment variables
                    for key, value in yaml_config.items():
                        if key not in ('host', 'port', 'debug', 'data_dir') and key not in os.environ:
                            config[key] = value
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
    
    return config

# Export the configuration
CONFIG = load_config() 