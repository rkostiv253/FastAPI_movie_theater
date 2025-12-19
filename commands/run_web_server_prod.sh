#!/bin/sh

# Running Gunicorn with Uvicorn workers
gunicorn cinema.main:app \
    --workers 10 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
