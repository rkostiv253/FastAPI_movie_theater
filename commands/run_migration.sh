#!/bin/sh
set -e

ALEMBIC_CONFIG="${ALEMBIC_CONFIG:-/usr/src/app/alembic.ini}"
SCRIPT_DIR="/usr/src/app/alembic"
VERSIONS_DIR="$SCRIPT_DIR/versions"

echo "Running migrations..."
echo "Using config: $ALEMBIC_CONFIG"
echo "Script dir: $SCRIPT_DIR"

if [ ! -f "$ALEMBIC_CONFIG" ]; then
  echo "ERROR: alembic.ini not found at: $ALEMBIC_CONFIG"
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/env.py" ]; then
  echo "ERROR: env.py not found at: $SCRIPT_DIR/env.py"
  exit 1
fi

if [ ! -d "$VERSIONS_DIR" ]; then
  echo "ERROR: versions folder not found at: $VERSIONS_DIR"
  exit 1
fi

if [ -z "$(ls -A "$VERSIONS_DIR" 2>/dev/null)" ]; then
  echo "ERROR: No migration files found in: $VERSIONS_DIR"
  exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null

alembic -c "$ALEMBIC_CONFIG" upgrade head

echo "Migrations applied."
