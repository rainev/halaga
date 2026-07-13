#!/bin/sh
# DANGER: wipe all data (DB + MinIO files) and start fresh.
# Removes the named volumes, so Postgres re-runs its init scripts on next start.
set -e
. "$(dirname -- "$0")/_lib.sh"

printf "This will DELETE the database and all stored files. Continue? [y/N] "
read -r answer
case "$answer" in
  [yY]*) ;;
  *) echo "Aborted."; exit 0 ;;
esac

$COMPOSE down -v
$COMPOSE up --build "$@"
