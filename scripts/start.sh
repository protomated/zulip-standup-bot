#!/bin/bash
set -e

# Zulip Standup Bot startup script
# This script handles initialization and starts the bot

echo "🤖 Starting Zulip Standup Bot..."

# Create necessary directories
mkdir -p /app/data
mkdir -p /app/logs

# Set default SQLite database path if DATABASE_URL is not set
if [ -z "${DATABASE_URL:-}" ]; then
    export DATABASE_URL="sqlite:///app/data/standup.db"
    echo "📁 Using SQLite database: /app/data/standup.db"
fi

# Check if running in development mode
if [ "${LOG_LEVEL}" = "DEBUG" ]; then
    echo "🔧 Running in development mode"
    export PYTHONPATH="/app:${PYTHONPATH}"
fi

# Wait for database if using PostgreSQL
if [[ "${DATABASE_URL:-}" == postgresql* ]]; then
    echo "⏳ Waiting for PostgreSQL database..."

    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')

    # Wait for database to be ready
    timeout=60
    while ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; do
        timeout=$((timeout - 1))
        if [ $timeout -eq 0 ]; then
            echo "❌ Database connection timeout"
            exit 1
        fi
        echo "Waiting for database... ($timeout seconds remaining)"
        sleep 1
    done

    echo "✅ Database connection established"
fi

# Validate required environment variables
required_vars=("ZULIP_EMAIL" "ZULIP_API_KEY" "ZULIP_SITE")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required environment variable $var is not set"
        exit 1
    fi
done

echo "✅ Environment validation passed"

# Test Zulip connection
echo "🔗 Testing Zulip connection..."
python3 -c "
import os
import sys
sys.path.insert(0, '/app')
try:
    import zulip
    client = zulip.Client(
        email=os.environ['ZULIP_EMAIL'],
        api_key=os.environ['ZULIP_API_KEY'],
        site=os.environ['ZULIP_SITE']
    )
    result = client.get_profile()
    if result['result'] == 'success':
        print('✅ Zulip connection successful')
        print(f'Bot user: {result[\"full_name\"]} ({result[\"email\"]})')
    else:
        print(f'❌ Zulip connection failed: {result}')
        exit(1)
except Exception as e:
    print(f'❌ Zulip connection error: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Zulip connection test passed"
else
    echo "❌ Zulip connection test failed"
    exit 1
fi

# Test module imports
echo "🧪 Testing module imports..."
export PYTHONPATH="/app:${PYTHONPATH}"
python3 /app/test_imports.py

if [ $? -ne 0 ]; then
    echo "⚠️ Module import test failed, but continuing with standalone database initialization..."
fi

# Initialize database using standalone script
echo "🗄️ Initializing database..."
python3 /app/init_database.py

if [ $? -ne 0 ]; then
    echo "❌ Database initialization failed"
    exit 1
fi

# Create a simple health check script
cat > /app/health_server.py << 'EOF'
import threading
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'timestamp': time.time(),
                'service': 'zulip-standup-bot'
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/ready':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'ready',
                'timestamp': time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging

def start_health_server():
    server = HTTPServer(('0.0.0.0', 5002), HealthHandler)
    server.serve_forever()

if __name__ == '__main__':
    start_health_server()
EOF

# Start health server in background
echo "🏥 Starting health check server..."
python3 /app/health_server.py &
HEALTH_PID=$!

# Give health server time to start
sleep 2

# Start the bot
echo "🚀 Starting Zulip Standup Bot..."

# Function to handle shutdown
cleanup() {
    echo "🛑 Shutting down..."
    if [ ! -z "$HEALTH_PID" ]; then
        kill $HEALTH_PID 2>/dev/null || true
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start the bot in background so we can handle signals
export PYTHONPATH="/app:/app/zulip_bots:${PYTHONPATH}"
python3 /app/run_standup_bot.py &
BOT_PID=$!

# Wait for bot process to finish
wait $BOT_PID
