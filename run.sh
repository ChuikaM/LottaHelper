#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create local log directories
mkdir -p logs/celery logs/gunicorn .cache

# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    redis-server &
fi

# Start Celery worker with local log file
echo "Starting Celery worker..."
celery -A celery_worker worker \
    --loglevel=info \
    --pool=solo \
    --concurrency=1 \
    --logfile=logs/celery/worker.log &

# Wait for Celery to initialize
sleep 3

# Start Gunicorn with local log files
echo "Starting Gunicorn..."
gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 1 \
    --timeout 180 \
    --access-logfile logs/gunicorn/access.log \
    --error-logfile logs/gunicorn/error.log \
    --log-level info \
    --capture-output \
    main:app