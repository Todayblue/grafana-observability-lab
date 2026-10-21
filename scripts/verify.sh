#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

command -v python3 >/dev/null 2>&1 || {
  printf 'Python 3 is required for telemetry verification.\n' >&2
  exit 2
}
unset COMPOSE_PROFILES
if ! docker compose -p grafana-alloy-observability -f compose.yaml --profile demo ps --status running --services | grep -qx 'demo-api'; then
  printf 'Optional Demo API is not running. Run ./scripts/start.sh --demo before verification.\n' >&2
  exit 2
fi
if [ "${1:-}" = "--reliability" ]; then
  shift
  exec python3 scripts/verify-reliability.py "$@"
fi
exec python3 scripts/verify.py "$@"
