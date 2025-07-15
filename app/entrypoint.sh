#!/bin/bash
set -e

echo "Starting migrations..."
alembic upgrade head || {
  echo "Migration failed. Exiting."
  exit 1
}

echo "Migrations complete. Starting the application..."
exec "$@"
