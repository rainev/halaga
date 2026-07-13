#!/bin/sh
# Start the full dev stack (frontend, backend, Postgres, Redis, MinIO) with a fresh build.
set -e
. "$(dirname -- "$0")/_lib.sh"

$COMPOSE up --build "$@"
