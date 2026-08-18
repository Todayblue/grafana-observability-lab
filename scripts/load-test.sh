#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

DEMO_API_PORT=${DEMO_API_PORT:-8081}
GRAFANA_PORT=${GRAFANA_PORT:-3000}
DEMO_API_URL="http://localhost:$DEMO_API_PORT"
GRAFANA_URL="http://localhost:$GRAFANA_PORT"

command -v curl >/dev/null 2>&1 || {
  printf 'ERROR: curl is not installed\n' >&2
  exit 1
}

request_many() {
  count=$1
  path=$2
  current=1
  while [ "$current" -le "$count" ]; do
    curl --fail --silent --show-error --output /dev/null "$DEMO_API_URL$path" || {
      printf 'ERROR: request %s/%s to %s failed\n' "$current" "$count" "$path" >&2
      exit 1
    }
    current=$((current + 1))
  done
}

request_many 35 /ok
request_many 10 /slow

expected_error_failures=0
unexpected_error_successes=0
current=1
while [ "$current" -le 5 ]; do
  if curl --fail --silent --output /dev/null "$DEMO_API_URL/error" 2>/dev/null; then
    unexpected_error_successes=$((unexpected_error_successes + 1))
  else
    expected_error_failures=$((expected_error_failures + 1))
  fi
  current=$((current + 1))
done

printf 'Load test complete: 50 sequential requests (35 /ok, 10 /slow, 5 /error)\n'
printf 'Expected /error failures: %s; unexpected /error successes: %s\n' "$expected_error_failures" "$unexpected_error_successes"
printf 'Grafana: %s/d/prometheus-first-look\n' "$GRAFANA_URL"
