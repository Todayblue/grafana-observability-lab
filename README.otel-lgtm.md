# OTel-Native LGTM Experiment — WP1 / WP2 / WP3

This branch is the local `experiment/otel-lgtm` prototype. The baseline
Phase 5 implementation lives on **`main`**; do not run its legacy
`compose.yaml` or `scripts/reset.sh` from this experimental branch.
See the [Execution-Ready Spec](https://github.com/Todayblue/grafana-observability-lab/issues/9)
for the WP0–WP7 decisions and acceptance gates.

## Architecture

- Exactly **two containers**: .NET 8 `demo-api` and `grafana/otel-lgtm`.
- LGTM image `0.34.0`, pinned at immutable image-index digest
  `sha256:b966ea107831d526d9eb8fe4d2d86c9e5731392fad9dce8296bcf2072031f07c`
  (ARM64 platform manifest: `sha256:bdbc807a21f55a3934d60c318f8270ee6b5aae07d954c83f6668dd64eef1168b`).
- Project `grafana-otel-lgtm-lab` and persistent volume
  `grafana-otel-lgtm-lab_lgtm-data` mounted at `/data`. No old Phase 5
  volumes, no Alloy, no additional Collector container.
- Grafana: `http://127.0.0.1:3300`; API: `http://127.0.0.1:8082`.
  Both host ports are localhost-only. OTLP/gRPC goes to `http://lgtm:4317`
  over the Docker Compose internal network, with no collector host port.
- Development only, not production. Grafana's initial credentials are
  `admin` / `admin`; change them if needed on your local lab.

## WP2: Three OpenTelemetry signals

The .NET API uses one shared resource identity across Metrics, Logs, Traces:

- `service.name=demo-api`
- `deployment.environment.name=lab`
- `service.version=0.1.0-wp2` (explicit application version in the
  experiment Compose; **not** the LGTM image version).

**Metrics:** .NET 8's `Microsoft.AspNetCore.Hosting` meter provides
`http.server.request.duration` (seconds; explicit buckets through 1.5s) and
`http.server.active_requests` (overall in-flight gauge). Export over OTLP
every 5s in this lab. Do not double-count requests with `prometheus-net`;
the old `/metrics` scraping endpoint is no longer part of this branch.

Actual Prometheus series in the pinned LGTM experiment:

- `http_server_request_duration_seconds_bucket`,
  `http_server_request_duration_seconds_count`,
  `http_server_request_duration_seconds_sum`
- `http_server_active_requests`

The standard attributes are normalized for PromQL, e.g. `http_route`,
`http_response_status_code`, `http_request_method`, `service_name` and
`service_version`. `http_route` is not guaranteed on
`http_server_active_requests` while a request is still in flight.
Expect HTTP health checks to appear in Metrics; the acceptance verifier
filters by demo routes.

**Logs:** Only the dedicated `DemoApi.Requests` logger emits a fixed,
structured `request_completed` event with `event.name`, `http.route`,
`http.response.status_code` (integer), and `duration_ms` (numeric).
OpenTelemetry derives TraceId and SpanId from the current HTTP Activity.
Information for 2xx/3xx, Warning for 4xx, Error for 5xx. The same allowlisted
event is written to JSON Console for diagnostics. Docker stdout is **not**
ingested into Loki; no double collection. Other framework logger categories
are disabled here to avoid leaking unbounded values.

Loki stores **index labels only** `service_name` and
`deployment_environment_name` for these demo logs, verified via its
`/loki/api/v1/series` API. High-cardinality `trace_id`, `span_id`,
`duration_ms`, `http_route` and `event_name` are structured metadata,
despite appearing next to labels in some query API responses.

**Traces:** 100% sampling is restricted to this local experiment.
Incoming W3C `traceparent` is continued by ASP.NET Core; `/slow` retains
`ValidateRequest`, `SimulatedWork`, `BuildResponse` child spans.
`/error` emits HTTP 500 and Error span status without fabricating an
exception; `/healthz` and unknown routes are excluded from demo tracing.
`SafeDemoSpanProcessor` removes non-allowlisted automatic span tags such
as raw URL/path/query, user-agent and server address before export; exception
events are disabled in this demo. An exporter or Activity failure must not
break the normal API HTTP response.

## Commands

```sh
./scripts/otel-lgtm.sh start
./scripts/otel-lgtm.sh verify       # WP1 runtime health only
./scripts/otel-lgtm.sh verify-wp2   # Fresh OTLP metrics/logs/traces + privacy
./scripts/otel-lgtm.sh verify-wp3   # Dashboards and two-way UI correlation
./scripts/otel-lgtm.sh verify-wp4   # Live current-run assertions + fault fixtures
./scripts/otel-lgtm.sh status
./scripts/otel-lgtm.sh stop         # Preserve /data volume
```

`verify-wp2` uses macOS Python 3's standard library and Docker. It creates
fresh W3C trace IDs for /ok, /slow, /error and a 405 probe, checks time-series
deltas, nonzero in-progress gauge under concurrent /slow load, exact Loki
LogRecord ↔ Tempo trace identity, minimal Loki indexed labels, no duplicate
logical events, excluded health traces, and absence of **synthetic** secret
values from stdout, Loki and Tempo. It never runs production operations.
Telemetry polling is bounded; a missing signal is FAIL, not an empty PASS.

To delete **only experiment** data, run `./scripts/otel-lgtm.sh reset` and
type the exact requested phrase. Reset intentionally has no `--yes`
bypass. Do not prune Docker globally or remove unrelated SQL Edge / HRM /
Phase 5 containers and volumes.

## Status and remaining work

WP1: two-container localhost runtime and persistent experiment volume.
WP2: OTel-native signals, structured fields, privacy and focused E2E smoke
checks. A WP2 smoke PASS is **not** a portfolio FINAL PASS.

**WP3:** Three experiment-owned Grafana data sources are provisioned:
`lab-otel-prometheus`, `lab-otel-loki` and `lab-otel-tempo`.
Their configuration is version controlled at
`grafana/otel-lgtm/provisioning/datasources/lab.yaml`. LGTM's four original
bundled data sources remain intact. All four dashboards are file-provisioned
from `grafana/otel-lgtm/dashboards` under **Observability Lab OTel**:

- http://127.0.0.1:3300/d/prometheus-first-look
- http://127.0.0.1:3300/d/demo-api-metrics
- http://127.0.0.1:3300/d/demo-api-logs
- http://127.0.0.1:3300/d/demo-api-traces

**Correlation:** Loki `TraceID` reads `trace_id` from structured metadata
(not indexed labels), providing **View Trace**. In Tempo, select the server
span and click **Related logs** (Grafana 13.2.2); Loki returns the exact
same trace ID using a low-cardinality `service_name` selector. Both
directions were verified with actual headless-browser clicks (Q28-Q31).

`verify-wp3` first checks Grafana's API and live panel queries using
`scripts/verify-otel-wp3.py`, then validates all four dashboards and the
two UI click paths with `scripts/verify-otel-wp3-ui.cjs`.
The UI test requires Node.js and an installed `playwright` Node module.
On this Mac, the existing DevBridge workspace supplies Playwright, without
adding a package to the experiment:

~~~sh
NODE_PATH="$HOME/Documents/GitHub/dev-bridge/node_modules"   ./scripts/otel-lgtm.sh verify-wp3
~~~

The browser runs headlessly and does not take foreground focus. Optionally
set `WP3_BROWSER_PATH` if the default Chromium is unavailable, and
`WP3_EVIDENCE_DIR=/tmp/grafana-otel-wp3-evidence` to save a screenshot
outside the source repo. Missing Playwright/browser must not count as PASS.

**WP4 — Deterministic E2E & fail-closed negatives:** The verifier uses fresh
W3C traceparent IDs on /ok, /slow, /error and POST /error (405), followed by
bounded per-signal metrics/logs/traces polling. Prometheus must return a
post-probe scrape timestamp **and an increased histogram count** after its
current-process baseline; historical nonzero time series do not count.
Each Loki record and Tempo server/child span must match the same exact
request/TraceId, status, severity, parent span and UTC event window.

Run the **same** pure validators against controlled fault-injected fixtures
(27 regression cases: stale/missing metrics, stale/duplicate logs, wrong
trace or parent, wrong error status, missing span context/children, privacy
leak, indexed trace label, etc.). Those are *simulation* tests and are
reported separately from live probes. Live negative checks include new
wrong IDs, excluded /healthz and unknown-route traces, and synthetic
secret tokens injected into headers, query strings, cookies and request
body, then checked for absence in current Console, Loki and Tempo data.
These tests never stop services, insert artificial backend records, or
exercise the WP5 outage/recovery/backup/restore scenarios.

WP4 re-runs actual headless Grafana Log → Trace → Logs clicks after checking
all three backends. The run writes an execution-summary.json, sanitized
query and probe evidence, negative-tests results, screenshot and hashed
manifest to /tmp/grafana-otel-wp4-evidence/<run-id> **outside the repo**.
PASS/FAIL/UNVERIFIED must not be conflated. /tmp evidence is temporary;
copy it to a secure, approved evidence store before deleting temp files.

~~~sh
NODE_PATH="$HOME/Documents/GitHub/dev-bridge/node_modules" \
  ./scripts/otel-lgtm.sh verify-wp4
# Fault injections without Docker access:
python3 -B scripts/verify-otel-wp4.py --fixtures-only
~~~

Optional limits: WP4_POLL_SECONDS (default 2), WP4_SIGNAL_DEADLINE
(default 75 seconds per signal), WP4_EVIDENCE_ROOT (default /tmp path).
Increase bounded deadlines if slow local image ingest causes real timeout;
do not replace a failed test with fixed sleep/any-old-data success.

**WP5–WP7:** Controlled LGTM-only outage and recovery, persistent volume
restore/reset drills, benchmark and independent FINAL review remain.
Promotion into `main` requires separate explicit owner approval.

Rollback: stop the experiment with `./scripts/otel-lgtm.sh stop` (volume
preserved). The Phase 5 baseline and old Compose live on `main`, not in
the revised Demo API source code of this branch.
