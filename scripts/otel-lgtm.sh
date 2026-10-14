#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROJECT="grafana-otel-lgtm-lab"
FILE="$ROOT/compose.otel-lgtm.yaml"

dc() {
  docker compose --project-name "$PROJECT" -f "$FILE" "$@"
}

case "${1:-}" in
  start)
    dc up -d --build
    printf 'LGTM experiment started. Grafana: http://127.0.0.1:3300  API: http://127.0.0.1:8082\n'
    printf 'Run: ./scripts/otel-lgtm.sh verify\n'
    ;;
  verify)
    command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }
    i=1
    until curl --fail --silent --max-time 3 http://127.0.0.1:3300/api/health >/dev/null 2>&1; do
      if [ "$i" -ge 60 ]; then
        echo "FAIL: LGTM Grafana did not become ready within the bounded wait" >&2
        exit 1
      fi
      i=$((i + 1))
      sleep 2
    done
    i=1
    until curl --fail --silent --max-time 3 http://127.0.0.1:8082/healthz >/dev/null 2>&1; do
      if [ "$i" -ge 30 ]; then
        echo "FAIL: Demo API did not become ready within the bounded wait" >&2
        exit 1
      fi
      i=$((i + 1))
      sleep 2
    done
    count=$(dc ps --services --status running | wc -l | tr -d '[:space:]')
    [ "$count" = "2" ] || { echo "FAIL: expected 2 running services, found $count" >&2; dc ps; exit 1; }
    dc ps
    echo "PASS: WP1 runtime health, two services and localhost endpoints"
    echo "NOTE: Metrics/Logs/Traces parity and Grafana correlation belong to WP2-WP4."
    ;;
  verify-wp2)
    command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
    python3 -B "$ROOT/scripts/verify-otel-wp2.py"
    ;;
  verify-wp3)
    command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
    command -v node >/dev/null 2>&1 || { echo "node is required for the UI gate" >&2; exit 1; }
    python3 -B "$ROOT/scripts/verify-otel-wp3.py"
    node "$ROOT/scripts/verify-otel-wp3-ui.cjs"
    ;;
  verify-wp4)
    command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
    python3 -B "$ROOT/scripts/verify-otel-wp4.py"
    ;;
  status)
    dc ps
    ;;
  stop)
    dc down
    echo "Experiment containers stopped; dedicated LGTM volume retained."
    ;;
  reset)
    printf 'This deletes ONLY the %s experiment containers and named volume.\n' "$PROJECT"
    printf 'Phase 5 containers and volumes are NOT targets.\n'
    printf 'Type RESET %s to confirm: ' "$PROJECT"
    IFS= read -r answer
    [ "$answer" = "RESET $PROJECT" ] || { echo "Reset cancelled."; exit 1; }
    dc down --volumes
    echo "Experiment project and its volume removed."
    ;;
  *)
    echo "Usage: ./scripts/otel-lgtm.sh {start|verify|verify-wp2|verify-wp3|verify-wp4|status|stop|reset}" >&2
    exit 2
    ;;
esac
