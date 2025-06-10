#!/bin/bash
#!/bin/bash

# Function to install dependencies from egg
install_egg_dependencies() {
    local egg_file="$1"
    echo "Extracting dependencies from $egg_file..."
    
    # Extract requires.txt from egg and install dependencies
    python3 -c "
import zipfile
import subprocess
import sys

egg_path = '$egg_file'
try:
    with zipfile.ZipFile(egg_path, 'r') as z:
        try:
            requires_content = z.read('EGG-INFO/requires.txt').decode('utf-8')
            dependencies = [line.strip() for line in requires_content.split('\n') if line.strip()]
            
            if dependencies:
                print(f'Installing dependencies: {dependencies}')
                subprocess.run([sys.executable, '-m', 'pip', 'install', '--break-system-packages'] + dependencies, check=True)
            else:
                print('No dependencies found')
        except KeyError:
            print('No requires.txt found in egg')
except Exception as e:
    print(f'Error processing egg: {e}')
"
}

# Start Scrapyd 
scrapyd &

# Wait for scrapyd to start properly
echo "Waiting for scrapyd to start..."
until curl -f -s http://localhost:6800/daemonstatus.json > /dev/null; do
    echo "Scrapyd not ready yet, waiting 2 seconds..."
    sleep 2
done
echo "Scrapyd is ready!"

# Start the Prometheus exporter in the background
/usr/bin/python3 /app/scrapyd_exporter.py &

# Deploy all eggs found in the shared folder
for egg in /root/.scrapyd/eggs/*.egg; do
  if [ -f "$egg" ]; then
    echo "installing dependencies for $egg..."
    install_egg_dependencies "$egg"
    echo "Deploying $egg..."
    project_name=$(basename "$egg" .egg)
    curl -X POST http://localhost:6800/addversion.json \
      -F "project=$project_name" \
      -F "version=1.0" \
      -F "egg=@$egg"
  fi
done

# Keep container running
wait