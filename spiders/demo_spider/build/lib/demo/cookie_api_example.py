"""
demo/cookie_api_example.py
────────────────────────────────────────────────────────────────────────────
Example script demonstrating how to use the RedisCookiesMiddleware API
to manage cookies outside of the Scrapy spider lifecycle.

This can be used as a starting point for building an API service
to manage cookies and sessions.
"""

import argparse
import json
import redis
from redis_cookies_middleware import RedisCookiesMiddleware


def setup_redis_client(host='redis', port=6379, db=0, password=None):
    """Create a Redis client with the specified connection parameters"""
    return redis.Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        decode_responses=True  # For easier JSON manipulation
    )


def get_middleware(redis_client):
    """Create a settings-like object and initialize middleware"""
    class DummySettings:
        def __init__(self):
            self.settings = {
                "REDIS_HOST": redis_client.connection_pool.connection_kwargs['host'],
                "REDIS_PORT": redis_client.connection_pool.connection_kwargs['port'],
                "REDIS_DB": redis_client.connection_pool.connection_kwargs['db'],
                "REDIS_PASSWORD": redis_client.connection_pool.connection_kwargs.get('password'),
                "REDIS_COOKIES_ENABLED": True,
                "REDIS_COOKIES_KEY_PREFIX": "scrapy:cookies:"
            }
        
        def get(self, key, default=None):
            return self.settings.get(key, default)
            
        def getbool(self, key, default=False):
            value = self.settings.get(key, default)
            return value in (True, 'true', 'True', '1', 1)
    
    dummy_settings = DummySettings()
    return RedisCookiesMiddleware(dummy_settings)


def list_cookies(middleware, spider_name):
    """List cookies for a specific spider"""
    cookies = middleware.get_cookies(spider_name)
    print(f"Cookies for {spider_name}:")
    if cookies:
        for i, cookie in enumerate(cookies, 1):
            print(f"  {i}. {cookie.get('name')}: {cookie.get('value')} (domain: {cookie.get('domain')})")
    else:
        print("  No cookies found")
    return cookies


def add_cookie(middleware, spider_name, name, value, domain, path='/'):
    """Add a cookie to a spider's cookie store"""
    # First get existing cookies
    cookies = middleware.get_cookies(spider_name) or []
    
    # Check if cookie already exists, update it if it does
    for cookie in cookies:
        if cookie.get('name') == name and cookie.get('domain') == domain:
            cookie['value'] = value
            cookie['path'] = path
            break
    else:
        # Cookie doesn't exist, add it
        cookies.append({
            'name': name,
            'value': value,
            'domain': domain,
            'path': path
        })
    
    # Save updated cookies
    success = middleware.update_cookies(spider_name, cookies)
    if success:
        print(f"Added/updated cookie {name} for {spider_name}")
    else:
        print(f"Failed to add/update cookie {name}")


def delete_spider_cookies(middleware, spider_name):
    """Delete all cookies for a specific spider"""
    success = middleware.delete_cookies(spider_name)
    if success:
        print(f"Deleted all cookies for {spider_name}")
    else:
        print(f"Failed to delete cookies for {spider_name}")


def import_cookies_from_json(middleware, spider_name, json_file):
    """Import cookies from a JSON file"""
    try:
        with open(json_file, 'r') as file:
            cookies = json.load(file)
        
        if not isinstance(cookies, list):
            print("Error: JSON file must contain a list of cookie objects")
            return False
        
        success = middleware.update_cookies(spider_name, cookies)
        if success:
            print(f"Imported {len(cookies)} cookies for {spider_name} from {json_file}")
        else:
            print(f"Failed to import cookies from {json_file}")
        return success
    except Exception as e:
        print(f"Error importing cookies: {e}")
        return False


def export_cookies_to_json(middleware, spider_name, json_file):
    """Export cookies to a JSON file"""
    cookies = middleware.get_cookies(spider_name)
    try:
        with open(json_file, 'w') as file:
            json.dump(cookies, file, indent=2)
        print(f"Exported {len(cookies)} cookies for {spider_name} to {json_file}")
        return True
    except Exception as e:
        print(f"Error exporting cookies: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Redis Cookie Manager for Scrapy')
    parser.add_argument('--host', default='redis', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    parser.add_argument('--db', type=int, default=0, help='Redis database')
    parser.add_argument('--password', default=None, help='Redis password')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List cookies for a spider')
    list_parser.add_argument('spider', help='Spider name')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a cookie')
    add_parser.add_argument('spider', help='Spider name')
    add_parser.add_argument('name', help='Cookie name')
    add_parser.add_argument('value', help='Cookie value')
    add_parser.add_argument('domain', help='Cookie domain')
    add_parser.add_argument('--path', default='/', help='Cookie path')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete all cookies for a spider')
    delete_parser.add_argument('spider', help='Spider name')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import cookies from JSON file')
    import_parser.add_argument('spider', help='Spider name')
    import_parser.add_argument('file', help='JSON file path')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export cookies to JSON file')
    export_parser.add_argument('spider', help='Spider name')
    export_parser.add_argument('file', help='JSON file path')
    
    args = parser.parse_args()
    
    # Initialize Redis client
    redis_client = setup_redis_client(args.host, args.port, args.db, args.password)
    
    # Get middleware instance
    middleware = get_middleware(redis_client)
    
    # Execute the specified command
    if args.command == 'list':
        list_cookies(middleware, args.spider)
    elif args.command == 'add':
        add_cookie(middleware, args.spider, args.name, args.value, args.domain, args.path)
    elif args.command == 'delete':
        delete_spider_cookies(middleware, args.spider)
    elif args.command == 'import':
        import_cookies_from_json(middleware, args.spider, args.file)
    elif args.command == 'export':
        export_cookies_to_json(middleware, args.spider, args.file)
    else:
        parser.print_help()


if __name__ == '__main__':
    main() 