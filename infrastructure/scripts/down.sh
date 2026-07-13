#!/bin/sh
# Stop the dev stack. Data (DB + files) is preserved.
set -e
. "$(dirname -- "$0")/_lib.sh"

$COMPOSE down "$@"
