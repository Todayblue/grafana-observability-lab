#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

GRAFANA_PORT=${GRAFANA_PORT:-3000}

docker compose up -d --build --force-recreate --wait

printf '\nLab started. Open Grafana: http://localhost:%s\n' "$GRAFANA_PORT"
printf 'Sign in with the development credentials documented in README.md.\n'
