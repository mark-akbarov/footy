#!/bin/bash
set -e  # Exit immediately if any command fails

echo "Starting migrations..."
alembic upgrade head || {
  echo "Migration failed. Exiting."
  exit 1
}

mkdir -p /usr/src/app/uploads/cvs

echo "Migrations complete. Starting the application..."
exec "$@"  # Passes CMD from Dockerfile to execute it