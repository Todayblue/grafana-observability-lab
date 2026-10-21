#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

# The explicit profile also stops the optional Demo if it was enabled.
unset COMPOSE_PROFILES
docker compose -p grafana-alloy-observability -f compose.yaml --profile demo stop
printf 'Alloy reference stopped; named volumes and other Docker projects preserved.\n'
