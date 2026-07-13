#!/bin/sh
# Seed the admin user, default PH market assumptions, and PSE companies into the
# running DB. The stack must already be up.
set -e
. "$(dirname -- "$0")/_lib.sh"

$COMPOSE exec backend python -m app.seed.admin
$COMPOSE exec backend python -m app.seed.market
$COMPOSE exec backend python -m app.seed.companies
