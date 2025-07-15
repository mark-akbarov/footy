#!/bin/bash
set -e

echo "Starting migrations..."
alembic upgrade head || {
  echo "Migration failed. Exiting."
  exit 1
}

# Fix permissions and create directory
mkdir -p /usr/src/app/uploads/cvs
chmod -R 775 /usr/src/app/uploads

echo "Migrations complete. Starting the application..."
exec "$@"
