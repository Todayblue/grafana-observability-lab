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
PROMETHEUS_PORT=${PROMETHEUS_PORT:-9090}
LOKI_PORT=${LOKI_PORT:-3100}
TEMPO_PORT=${TEMPO_PORT:-3200}
ALLOY_PORT=${ALLOY_PORT:-12345}
DEMO_API_PORT=${DEMO_API_PORT:-8081}
GRAFANA_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
GRAFANA_URL="http://localhost:$GRAFANA_PORT"
PROMETHEUS_URL="http://localhost:$PROMETHEUS_PORT"
LOKI_URL=${LOKI_URL:-http://localhost:$LOKI_PORT}
TEMPO_URL=${TEMPO_URL:-http://localhost:$TEMPO_PORT}
ALLOY_URL=${ALLOY_URL:-http://localhost:$ALLOY_PORT}
DEMO_API_URL="http://localhost:$DEMO_API_PORT"

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v curl >/dev/null 2>&1 || fail "curl is not installed"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable"

for service in prometheus grafana demo-api alloy loki tempo; do
  container_id=$(docker compose ps -q "$service")
  [ -n "$container_id" ] || fail "$service container does not exist"
  state=$(docker inspect --format '{{.State.Status}}' "$container_id")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
  if [ "$service" = "alloy" ] || [ "$service" = "loki" ] || [ "$service" = "tempo" ]; then
    if [ "$state" != "running" ]; then
      docker compose logs --no-color --tail=100 "$service" >&2 || :
      fail "$service is state=$state health=$health"
    fi
    pass "$service container is running"
  else
    [ "$state" = "running" ] && [ "$health" = "healthy" ] || fail "$service is state=$state health=$health"
    pass "$service container is running and healthy"
  fi
done

loki_ready=false
loki_attempt=1
while [ "$loki_attempt" -le 30 ]; do
  if curl --fail --silent --show-error "$LOKI_URL/ready" >/dev/null 2>/dev/null; then
    loki_ready=true
    break
  fi
  if [ "$loki_attempt" -lt 30 ]; then
    sleep 1
  fi
  loki_attempt=$((loki_attempt + 1))
done

if [ "$loki_ready" = true ]; then
  pass "Loki HTTP readiness endpoint is reachable"
else
  docker compose logs --no-color --tail=100 loki >&2 || :
  fail "Loki HTTP readiness endpoint is unreachable after 30 seconds"
fi

tempo_ready=false
tempo_attempt=1
while [ "$tempo_attempt" -le 30 ]; do
  if curl --fail --silent --show-error "$TEMPO_URL/ready" >/dev/null 2>/dev/null; then
    tempo_ready=true
    break
  fi
  if [ "$tempo_attempt" -lt 30 ]; then
    sleep 1
  fi
  tempo_attempt=$((tempo_attempt + 1))
done

if [ "$tempo_ready" = true ]; then
  pass "Tempo HTTP readiness endpoint is reachable"
else
  docker compose logs --no-color --tail=100 tempo >&2 || :
  fail "Tempo HTTP readiness endpoint is unreachable after 30 seconds"
fi

if curl --fail --silent "$ALLOY_URL/-/ready" >/dev/null 2>&1; then
  pass "Alloy HTTP readiness endpoint is reachable"
else
  curl --fail --silent --show-error "$ALLOY_URL/" >/dev/null || fail "Alloy HTTP endpoint is unreachable"
  pass "Alloy HTTP endpoint is reachable"
fi

curl --fail --silent --show-error "$PROMETHEUS_URL/-/ready" >/dev/null || fail "Prometheus HTTP endpoint is unreachable"
pass "Prometheus HTTP endpoint is reachable"

targets=$(curl --fail --silent --show-error "$PROMETHEUS_URL/api/v1/targets?state=active") || fail "Prometheus targets API request failed"
printf '%s' "$targets" | grep -q '"job":"prometheus"' || fail "Prometheus self target is missing"
printf '%s' "$targets" | grep -q '"health":"up"' || fail "Prometheus self target is not UP"
pass "Prometheus self target is UP"

if printf '%s' "$targets" | grep -q '"job":"demo-api"'; then
  fail "Prometheus active targets unexpectedly contain the demo-api job"
fi
pass "Prometheus active targets do not contain the demo-api job"

curl --fail --silent --show-error "$DEMO_API_URL/healthz" >/dev/null || fail "demo-api health endpoint is unreachable"
pass "demo-api health endpoint is reachable"

metrics=$(curl --fail --silent --show-error "$DEMO_API_URL/metrics") || fail "demo-api metrics endpoint is unreachable"
printf '%s' "$metrics" | grep -q 'demo_http_requests_total' || fail "demo-api requests metric is missing"
printf '%s' "$metrics" | grep -q 'demo_http_request_duration_seconds' || fail "demo-api request duration metric is missing"
pass "demo-api metrics are exposed"

curl --fail --silent --show-error "$DEMO_API_URL/ok" >/dev/null || fail "demo-api /ok request failed"
curl --fail --silent --show-error "$DEMO_API_URL/slow" >/dev/null || fail "demo-api /slow request failed"
error_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$DEMO_API_URL/error") || fail "demo-api /error request failed"
[ "$error_status" = "500" ] || fail "demo-api /error returned HTTP $error_status instead of 500"
pass "demo-api test requests returned expected statuses"

sleep 6

tempo_traces=
tempo_traces_ready=false
tempo_traces_attempt=1
while [ "$tempo_traces_attempt" -le 30 ]; do
  if tempo_traces=$(curl --fail --silent --show-error --get \
    --data-urlencode 'q={ resource.service.name = "demo-api" }' \
    --data-urlencode 'limit=20' \
    "$TEMPO_URL/api/search"); then
    if printf '%s' "$tempo_traces" | grep -Eq '"traces"[[:space:]]*:[[:space:]]*\[[[:space:]]*\{'; then
      tempo_traces_ready=true
      break
    fi
  fi
  if [ "$tempo_traces_attempt" -lt 30 ]; then
    sleep 1
  fi
  tempo_traces_attempt=$((tempo_traces_attempt + 1))
done

if [ "$tempo_traces_ready" = true ]; then
  pass "Tempo contains demo-api traces"
else
  docker compose logs --no-color --tail=100 tempo >&2 || :
  fail "Tempo TraceQL search did not return a demo-api trace after 30 seconds"
fi

slow_span_traces=
slow_span_ready=false
slow_span_attempt=1
while [ "$slow_span_attempt" -le 30 ]; do
  if slow_span_traces=$(curl --fail --silent --show-error --get \
    --data-urlencode 'q={ resource.service.name = "demo-api" && name = "SimulatedWork" }' \
    --data-urlencode 'limit=20' \
    "$TEMPO_URL/api/search"); then
    if printf '%s' "$slow_span_traces" | grep -Eq '"traces"[[:space:]]*:[[:space:]]*\[[[:space:]]*\{'; then
      slow_span_ready=true
      break
    fi
  fi
  if [ "$slow_span_attempt" -lt 30 ]; then
    sleep 1
  fi
  slow_span_attempt=$((slow_span_attempt + 1))
done

if [ "$slow_span_ready" = true ]; then
  pass "Tempo TraceQL search finds the /slow SimulatedWork child span"
else
  fail "Tempo TraceQL search did not find the /slow SimulatedWork child span after 30 seconds"
fi

loki_logs=
loki_logs_ready=false
loki_logs_attempt=1
while [ "$loki_logs_attempt" -le 30 ]; do
  loki_start=$((($(date +%s) - 120) * 1000000000))
  if loki_logs=$(curl --fail --silent --show-error --get \
    --data-urlencode 'query={service="demo-api", environment="lab", event_name="request_completed", endpoint="/error", level="Error"}' \
    --data-urlencode "start=$loki_start" \
    --data-urlencode 'limit=100' \
    "$LOKI_URL/loki/api/v1/query_range"); then
    if printf '%s' "$loki_logs" | grep -q 'request_completed' &&
      printf '%s' "$loki_logs" | grep -q 'endpoint=/error statusCode=500' &&
      printf '%s' "$loki_logs" | grep -q '"status_code":"500"' &&
      printf '%s' "$loki_logs" | grep -q '"duration_ms":'; then
      loki_logs_ready=true
      break
    fi
  fi
  if [ "$loki_logs_attempt" -lt 30 ]; then
    sleep 1
  fi
  loki_logs_attempt=$((loki_logs_attempt + 1))
done

printf '%s' "$loki_logs" | grep -q 'request_completed' || fail "Loki query did not return request_completed logs"
printf '%s' "$loki_logs" | grep -q 'endpoint=/error statusCode=500' || fail "Loki query did not return the intentional /error status 500 raw log"
printf '%s' "$loki_logs" | grep -q '"status_code":"500"' || fail "Loki query did not return structured metadata status_code=500"
printf '%s' "$loki_logs" | grep -q '"duration_ms":' || fail "Loki query did not return structured metadata duration_ms"
[ "$loki_logs_ready" = true ] || fail "Loki request log query failed after 30 seconds"
pass "Loki contains the labeled /error request log and structured metadata"

requests_ready=false
requests_attempt=1
while [ "$requests_attempt" -le 30 ]; do
  requests_value=
  if requests_query=$(curl --fail --silent --show-error --get \
    --data-urlencode 'query=sum(demo_http_requests_total)' \
    "$PROMETHEUS_URL/api/v1/query"); then
    requests_value=$(printf '%s' "$requests_query" | awk -F'"value":\\[' '
      NF > 1 {
        split($2, parts, ",")
        split(parts[2], value, "]")
        gsub(/["[:space:]]/, "", value[1])
        print value[1]
        exit
      }
    ')
  fi
  if printf '%s\n' "$requests_value" | awk '
    /^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ && ($1 + 0) > 0 { found = 1 }
    END { exit(found ? 0 : 1) }
  '; then
    requests_ready=true
    break
  fi
  if [ "$requests_attempt" -lt 30 ]; then
    sleep 1
  fi
  requests_attempt=$((requests_attempt + 1))
done

if [ "$requests_ready" = true ]; then
  pass "Prometheus contains demo-api request metrics"
else
  docker compose logs --no-color --tail=100 alloy >&2 || :
  fail "Prometheus request-total query did not return a nonzero numeric result after 30 seconds"
fi

errors_ready=false
errors_attempt=1
while [ "$errors_attempt" -le 30 ]; do
  errors_value=
  if errors_query=$(curl --fail --silent --show-error --get \
    --data-urlencode 'query=sum(demo_http_requests_total{status_code="500"})' \
    "$PROMETHEUS_URL/api/v1/query"); then
    errors_value=$(printf '%s' "$errors_query" | awk -F'"value":\\[' '
      NF > 1 {
        split($2, parts, ",")
        split(parts[2], value, "]")
        gsub(/["[:space:]]/, "", value[1])
        print value[1]
        exit
      }
    ')
  fi
  if printf '%s\n' "$errors_value" | awk '
    /^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ && ($1 + 0) > 0 { found = 1 }
    END { exit(found ? 0 : 1) }
  '; then
    errors_ready=true
    break
  fi
  if [ "$errors_attempt" -lt 30 ]; then
    sleep 1
  fi
  errors_attempt=$((errors_attempt + 1))
done

if [ "$errors_ready" = true ]; then
  pass "Prometheus contains demo-api 500 request metrics"
else
  docker compose logs --no-color --tail=100 alloy >&2 || :
  fail "Prometheus 500 request-total query did not return a nonzero numeric result after 30 seconds"
fi

curl --fail --silent --show-error "$GRAFANA_URL/api/health" >/dev/null || fail "Grafana HTTP endpoint is unreachable"
pass "Grafana HTTP endpoint is reachable"

auth="$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD"
datasource=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/prometheus") || fail "Provisioned Prometheus datasource is missing"
printf '%s' "$datasource" | grep -q '"name":"Prometheus"' || fail "Provisioned Prometheus datasource has unexpected data"
pass "Provisioned Prometheus datasource exists"

datasource_health=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/prometheus/health") || fail "Grafana cannot query Prometheus through the datasource"
printf '%s' "$datasource_health" | grep -q '"status":"OK"' || fail "Prometheus datasource health check did not return OK"
pass "Grafana datasource can query Prometheus"

loki_datasource=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/loki") || fail "Provisioned Loki datasource is missing"
printf '%s' "$loki_datasource" | grep -q '"name":"Loki"' || fail "Provisioned Loki datasource has unexpected data"
pass "Provisioned Loki datasource exists"

loki_datasource_health=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/loki/health") || fail "Grafana cannot query Loki through the datasource"
printf '%s' "$loki_datasource_health" | grep -Eq '"status":"(OK|success)"' || fail "Loki datasource health check did not return OK/success"
pass "Grafana datasource can query Loki"

tempo_datasource=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/tempo") || fail "Provisioned Tempo datasource is missing"
printf '%s' "$tempo_datasource" | grep -q '"name":"Tempo"' || fail "Provisioned Tempo datasource has unexpected data"
pass "Provisioned Tempo datasource exists"

tempo_datasource_health=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/datasources/uid/tempo/health") || fail "Grafana cannot query Tempo through the datasource"
printf '%s' "$tempo_datasource_health" | grep -Eq '"status":"(OK|success)"' || fail "Tempo datasource health check did not return OK/success"
pass "Grafana datasource can query Tempo"

dashboard=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/dashboards/uid/prometheus-first-look") || fail "Provisioned dashboard is missing"
printf '%s' "$dashboard" | grep -q '"title":"Prometheus: First Look"' || fail "Provisioned dashboard has unexpected data"
pass "Provisioned dashboard exists"

demo_dashboard=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/dashboards/uid/demo-api-metrics") || fail "Demo API Metrics dashboard is missing"
printf '%s' "$demo_dashboard" | grep -q '"title":"Demo API Metrics"' || fail "Demo API Metrics dashboard has unexpected data"
pass "Demo API Metrics dashboard exists"

logs_dashboard=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/dashboards/uid/demo-api-logs") || fail "Demo API Logs dashboard is missing"
printf '%s' "$logs_dashboard" | grep -q '"title":"Demo API Logs"' || fail "Demo API Logs dashboard has unexpected data"
pass "Demo API Logs dashboard exists"

traces_dashboard=$(curl --fail --silent --show-error --user "$auth" "$GRAFANA_URL/api/dashboards/uid/demo-api-traces") || fail "Demo API Traces dashboard is missing"
printf '%s' "$traces_dashboard" | grep -q '"title":"Demo API Traces"' || fail "Demo API Traces dashboard has unexpected data"
pass "Demo API Traces dashboard exists"

printf '\nAll checks passed. Grafana Demo API Traces: %s/d/demo-api-traces (Tempo: %s)\n' "$GRAFANA_URL" "$TEMPO_URL"
