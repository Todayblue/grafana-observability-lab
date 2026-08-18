#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

if [ "${1:-}" != "--yes" ]; then
  printf 'This deletes all Grafana dashboards/settings and Prometheus metrics stored in Docker volumes.\n'
  printf 'Type reset to continue: '
  read -r answer
  [ "$answer" = "reset" ] || { printf 'Reset cancelled.\n'; exit 1; }
fi

docker compose down --volumes --remove-orphans
printf 'Lab data reset. Run ./scripts/start.sh to start fresh.\n'
