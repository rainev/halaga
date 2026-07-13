#!/bin/sh
# Shared helpers for the dev scripts. Sourced by up.sh / down.sh / reset.sh / seed.sh.

# Repo root = two levels up from this script, regardless of where you run from.
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT_DIR"

# Use `docker compose` (v2 plugin) if present, else the standalone `docker-compose`.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Error: neither 'docker compose' nor 'docker-compose' is installed." >&2
  exit 1
fi
