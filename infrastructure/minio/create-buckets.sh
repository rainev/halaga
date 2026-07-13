#!/bin/sh
# Creates the storage bucket in MinIO.
# Run by the one-shot `minio-setup` service in docker-compose.yml on startup.
set -e

mc alias set local "http://minio:9000" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$MINIO_BUCKET"

echo "MinIO bucket ready: $MINIO_BUCKET"
