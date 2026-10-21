#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

case "${1:-}" in
  "") demo=0 ;;
  --demo) demo=1 ;;
  *) printf 'Usage: ./scripts/start.sh [--demo]\n' >&2; exit 2 ;;
esac

if [ ! -f .env ]; then
  printf 'Missing .env: copy .env.example to .env and set strong GRAFANA_ADMIN_PASSWORD and GRAFANA_SECRET_KEY.\n' >&2
  exit 2
fi

# An opt-in Demo must never start through inherited COMPOSE_PROFILES.
unset COMPOSE_PROFILES
if [ "$demo" -eq 1 ]; then
  docker compose -p grafana-alloy-observability -f compose.yaml --profile demo up -d --build --wait
  printf 'Alloy reference running with optional Demo API at http://127.0.0.1:18085\n'
  printf 'Verify: ./scripts/verify.sh\n'
else
  docker compose -p grafana-alloy-observability -f compose.yaml up -d --wait
  printf 'Alloy platform running (Demo API disabled).\n'
  printf 'Optional Demo: ./scripts/start.sh --demo\n'
fi
printf 'Grafana: http://127.0.0.1:13305 | Alloy: http://127.0.0.1:12355\n'
