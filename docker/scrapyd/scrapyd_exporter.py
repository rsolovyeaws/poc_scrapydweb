"""
Simple Prometheus metrics exporter for Scrapyd.
"""

import time
import threading
import requests
import psutil
import os
import glob
import json
from datetime import datetime
from prometheus_client import start_http_server, Gauge, Counter, Info

# Define metrics
SCRAPYD_UP = Gauge('scrapyd_up', 'Whether Scrapyd is up (1) or down (0)')
RUNNING_JOBS = Gauge('scrapyd_running_jobs', 'Number of running Scrapyd jobs', ['project'])
PENDING_JOBS = Gauge('scrapyd_pending_jobs', 'Number of pending Scrapyd jobs', ['project'])
FINISHED_JOBS = Counter('scrapyd_finished_jobs_total', 'Total number of finished Scrapyd jobs', ['project', 'spider'])
MEMORY_USAGE = Gauge('scrapyd_memory_usage_bytes', 'Memory usage of Scrapyd process')
CPU_USAGE = Gauge('scrapyd_cpu_usage_percent', 'CPU usage of Scrapyd process')

# Create a gauge for log entries with labels instead of using Info
LOG_ENTRIES = Gauge('scrapyd_log_entry', 'Log entries from Scrapyd spiders', 
                   ['project', 'spider', 'filename', 'timestamp', 'content'])

# Track already counted jobs
processed_job_ids = set()
# Track already exposed logs to avoid duplicates
exposed_logs = set()

class ScrapydExporter:
    """
    Prometheus exporter for Scrapyd metrics.
    """
    def __init__(self, scrapyd_url='http://localhost:6800', update_interval=5, log_path='/var/lib/scrapyd/logs'):
        self.scrapyd_url = scrapyd_url
        self.update_interval = update_interval
        self.running = True
        self.process = None
        self.log_path = log_path
        self.find_scrapyd_process()
    
    def find_scrapyd_process(self):
        """Find the Scrapyd process for monitoring."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                # Look for the scrapyd process by command line
                if proc.info['name'] == 'python' and any('scrapyd' in cmd.lower() for cmd in proc.info['cmdline'] if cmd):
                    self.process = proc
                    print(f"Found Scrapyd process with PID {proc.pid}")
                    return
            
            # If not found by command line, try finding by name
            for proc in psutil.process_iter(['pid', 'name']):
                if 'scrapyd' in proc.info['name'].lower():
                    self.process = proc
                    print(f"Found Scrapyd process with PID {proc.pid}")
                    return
            
            # If we still didn't find it, use the parent process as a fallback
            self.process = psutil.Process(os.getppid())
            print(f"Using parent process with PID {self.process.pid} as fallback")
        except Exception as e:
            print(f"Error finding Scrapyd process: {e}")
            # Use current process as a last resort
            self.process = psutil.Process()
            print(f"Using current process with PID {self.process.pid} as fallback")
    
    def start(self):
        """Start the metrics collection thread."""
        thread = threading.Thread(target=self._collect_metrics)
        thread.daemon = True
        thread.start()
        return thread
    
    def stop(self):
        """Stop the metrics collection thread."""
        self.running = False
    
    def _collect_metrics(self):
        """Periodically collect metrics from Scrapyd."""
        while self.running:
            try:
                self._update_metrics()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error collecting metrics: {e}")
                time.sleep(self.update_interval)
    
    def _get_recent_logs(self):
        """Get the most recent log entries from Scrapyd spiders."""
        try:
            # Get a list of all log files, sorted by modification time (newest first)
            log_files = []
            
            # Check if the directory exists
            if not os.path.exists(self.log_path):
                print(f"Log directory {self.log_path} does not exist")
                return {}
                
            for root, dirs, files in os.walk(self.log_path):
                for file in files:
                    if file.endswith('.log'):
                        file_path = os.path.join(root, file)
                        log_files.append((file_path, os.path.getmtime(file_path)))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Take the 10 most recent log files
            recent_log_files = log_files[:10]
            
            # Extract the last 5 lines from each file
            logs_data = []
            
            for file_path, _ in recent_log_files:
                # Extract project and spider names from path
                parts = file_path.split('/')
                if len(parts) >= 4:
                    project_name = parts[-3]
                    spider_name = parts[-2]
                    log_file = parts[-1]
                    log_key = f"{project_name}_{spider_name}_{log_file}"
                    
                    # Skip if we've already processed this log
                    if log_key in exposed_logs:
                        continue
                    
                    # Get the last 5 lines from the file
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            lines = f.readlines()
                            last_lines = lines[-5:] if lines else []
                            timestamp = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Concatenate lines and strip newlines to make it more readable
                            content = ' | '.join([line.strip() for line in last_lines])
                            
                            logs_data.append({
                                'project': project_name,
                                'spider': spider_name,
                                'filename': log_file,
                                'timestamp': timestamp,
                                'content': content,
                                'key': log_key
                            })
                            exposed_logs.add(log_key)
                    except Exception as e:
                        print(f"Error reading log file {file_path}: {e}")
            
            # Limit the number of tracked logs
            if len(exposed_logs) > 100:
                exposed_logs.clear()
                
            return logs_data
                
        except Exception as e:
            print(f"Error collecting log data: {e}")
            return []
    
    def _update_metrics(self):
        """Update all metrics."""
        global processed_job_ids
        
        # Update system metrics using psutil
        self._update_system_metrics()
        
        # Update log information - using gauge metrics instead of Info
        self._update_log_metrics()
        
        # Check Scrapyd status
        try:
            response = requests.get(f"{self.scrapyd_url}/daemonstatus.json", timeout=2)
            if response.status_code == 200 and response.json().get('status') == 'ok':
                SCRAPYD_UP.set(1)
            else:
                SCRAPYD_UP.set(0)
                return
        except:
            SCRAPYD_UP.set(0)
            return
        
        # Get all projects
        try:
            response = requests.get(f"{self.scrapyd_url}/listprojects.json", timeout=2)
            if response.status_code == 200 and response.json().get('status') == 'ok':
                projects = response.json().get('projects', [])
            else:
                return
        except:
            return
            
        # Initialize all project metrics to 0
        for project in projects:
            RUNNING_JOBS.labels(project=project).set(0)
            PENDING_JOBS.labels(project=project).set(0)
            
        # Get job stats for each project
        for project in projects:
            try:
                response = requests.get(f"{self.scrapyd_url}/listjobs.json?project={project}", timeout=2)
                if response.status_code != 200 or response.json().get('status') != 'ok':
                    continue
                    
                data = response.json()
                running_jobs = data.get('running', [])
                pending_jobs = data.get('pending', [])
                finished_jobs = data.get('finished', [])
                
                # Set running and pending counts
                RUNNING_JOBS.labels(project=project).set(len(running_jobs))
                PENDING_JOBS.labels(project=project).set(len(pending_jobs))
                
                # Count finished jobs we haven't seen before
                for job in finished_jobs:
                    job_id = job.get('id')
                    if job_id and job_id not in processed_job_ids:
                        spider = job.get('spider', 'unknown')
                        FINISHED_JOBS.labels(project=project, spider=spider).inc()
                        processed_job_ids.add(job_id)
                
                # Limit the processed jobs set size
                if len(processed_job_ids) > 1000:
                    processed_job_ids = set(list(processed_job_ids)[-500:])
                    
            except Exception as e:
                print(f"Error collecting jobs for project {project}: {e}")
                continue
    
    def _update_log_metrics(self):
        """Update log metrics using gauge instead of Info."""
        logs_data = self._get_recent_logs()
        
        for log_entry in logs_data:
            LOG_ENTRIES.labels(
                project=log_entry['project'],
                spider=log_entry['spider'],
                filename=log_entry['filename'],
                timestamp=log_entry['timestamp'],
                content=log_entry['content']
            ).set(1)
    
    def _update_system_metrics(self):
        """Update system metrics using psutil."""
        try:
            if self.process and self.process.is_running():
                # Update CPU usage (percentage)
                cpu_percent = self.process.cpu_percent(interval=None)
                CPU_USAGE.set(cpu_percent)
                
                # Update memory usage (bytes)
                memory_info = self.process.memory_info()
                MEMORY_USAGE.set(memory_info.rss)  # Resident Set Size in bytes
            else:
                # If process is not running, try to find it again
                self.find_scrapyd_process()
        except Exception as e:
            print(f"Error updating system metrics: {e}")
            # Try to find the process again
            self.find_scrapyd_process()

if __name__ == '__main__':
    # Start HTTP server for Prometheus metrics
    start_http_server(9410)
    print(f"Prometheus metrics server started on port 9410")
    
    # Start metrics collector
    exporter = ScrapydExporter()
    collector_thread = exporter.start()
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        exporter.stop() 