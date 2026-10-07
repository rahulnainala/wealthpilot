#!/bin/sh
# Apply database migrations, then start the API. Alembic owns the schema in
# containers (AUTO_CREATE_TABLES is false there).
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting WealthPilot API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
