# Grafana Alloy — Portable Observability Reference

Small local reference for a future HRM-like .NET API migration.
**No HRM repository changes; not a Production deployment.**
Final acceptance is still pending against the
[Minimal Migration-ready Spec](docs/specs/MINIMAL-ALLOY-MIGRATION-READY.md).

## Architecture

```text
Optional .NET Demo API -- OTLP metrics/logs/traces --> Grafana Alloy
                                                        |--> Prometheus (metrics)
                                                        |--> Loki       (logs)
                                                        |--> Tempo      (traces)
Grafana -------------------------------------------- queries all three backends
```

Alloy is the **only collector**. Demo API stdout is not re-ingested into Loki,
and application metrics are not scraped. Production storage, network security,
TLS/authentication and HA are intentionally not selected here.

## Local lifecycle

Requires Docker Compose, Python 3 for verification, and a local untracked
`.env`. On a new clone, copy `cp .env.example .env` then set strong, unique
`GRAFANA_ADMIN_PASSWORD` and `GRAFANA_SECRET_KEY` yourself.
`start.sh` does **not** generate them. Never commit `.env`.

```sh
./scripts/start.sh          # platform only; Demo API stays off
./scripts/start.sh --demo   # opt in to synthetic Demo API
./scripts/verify.sh         # backend OTLP smoke test; requires Demo
./scripts/verify.sh --reliability  # bounded Alloy outage + recovery + privacy
./scripts/stop.sh           # stop both platform and optional Demo; keep volumes
```

These scripts use **one** Compose configuration (`compose.yaml`) and project
`grafana-alloy-observability`. Host ports bind to `127.0.0.1`; the verifier
uses the **default ports below**. Demo API is optional via the `demo` profile.

| Service | Default local URL |
| --- | --- |
| Grafana OSS 13.2.4 | http://127.0.0.1:13305 |
| Demo API (opt-in) | http://127.0.0.1:18085 |
| Alloy UI | http://127.0.0.1:12355 |
| Prometheus | http://127.0.0.1:19095 |
| Loki | http://127.0.0.1:13105 |
| Tempo | http://127.0.0.1:13205 |
| Alloy OTLP gRPC | 127.0.0.1:14317 |
| Alloy OTLP HTTP | 127.0.0.1:14318 |

Grafana administrator credentials are stored locally in `.env`, not in source.
`./scripts/verify.sh` runs synthetic `/ok`, `/slow`, `/error`,
`/business-failure` and `/jobs/run` requests; it checks Prometheus Metrics,
Loki Logs, Tempo Traces, exact Trace ID correlation and a synthetic
query/header/body privacy canary across Console and the three Backends.
The opt-in `--reliability` mode verifies HTTP responses while **only the
project's Alloy container is stopped**, restores Alloy even on a failed assertion,
checks that **new** telemetry reaches all three backends, and reports which
in-outage Logs/Traces are **observed within a bounded window**. It also probes
synthetic identity/payroll values in headers (including fake authentication and
cookie fields), query parameters and an ignored JSON body, scanning Application
and Alloy Console, Loki, Prometheus series and Tempo; this is a bounded negative
test, **not** proof of comprehensive PII protection. Missing events in the
observation window do **not** prove permanent loss; cumulative metrics do not
identify individual requests.

Both verification modes write evidence outside the repo under
`~/Library/Application Support/GrafanaObservabilityLab/evidence/`.
Run `./scripts/start.sh --demo` first; verification fails clearly without it.
Run fault injection **only** in this isolated local Compose project, not
against live HRM or a shared Production Collector.

`./scripts/stop.sh` stops only this project's containers and preserves all
named volumes. No destructive reset command is provided. Prior experiments,
the historical handoff stash, and unrelated Docker projects are out of scope.

## Future .NET API integration contract (reference only)

**Nothing is installed in `hrm-repo`.** For later integration, use the working
`demo-api/Program.cs` and `demo-api/demo-api.csproj` as the small .NET 8
example, not as a shared package or a replacement for HRM business logic.

- **SDK:** `OpenTelemetry.Extensions.Hosting`, `OpenTelemetry.Instrumentation.AspNetCore`
  and `OpenTelemetry.Exporter.OpenTelemetryProtocol`. Use the .NET
  `AddOpenTelemetry()` pipeline for ASP.NET Core **Metrics**, `ILogger`
  **Logs**, and ASP.NET Core + custom-Activity **Traces**.
- **Identity:** set a stable `service.name` for the actual API and
  `deployment.environment.name` for the environment. Do not identify a
  service by an employee, account, request ID, or any other high-cardinality value.
- **Endpoint:** set `OTEL_EXPORTER_OTLP_ENDPOINT` for **OTLP/gRPC**.
  Within this Compose network: `http://alloy:4317`. For a **separate
  application on this same Mac**: `http://127.0.0.1:14317`.
  These are local, **unauthenticated** endpoints, not remotely usable
  Production addresses. TLS/auth and the reachable endpoint are deferred.
- **Business outcome:** for failures still returning HTTP 200, use a
  bounded metric dimension such as `business_outcome=failed`, plus a safe
  structured log and span. Do not treat HTTP 5xx as the only failure signal.
  The `demo.business.operations` meter is synthetic; HRM event names
  and approved labels must be defined with its owners later.
- **Correlation and privacy:** preserve trace context and use
  `trace_id`/`span_id` as Loki **structured metadata**, not index labels.
  Exclude request/response bodies, raw query strings, auth headers,
  employee identifiers, payroll values and secrets. The Demo verifier
  checks synthetic values only; **actual HRM logging requires its own
  code and data review before any integration**.

On a fresh Grafana volume, the only dashboards provisioned are **none**;
Prometheus, Loki and Tempo are the three provisioned data sources.
The branch contains no training Dashboard JSON or Alert Rules.
An **empty, retention-only dashboard provider** remains in
`grafana/provisioning/dashboards/dashboards.yml`: removing that provider
during this migration caused Grafana 13.2.4 to remove the four earlier
dashboards from its local database. They were recovered from the tracked
Git originals; the provider now keeps them in the **existing local Grafana
volume** without re-shipping their JSON. Do not delete the provider or
the persistent volume as part of source cleanup.

Official references: [OpenTelemetry .NET exporters](https://opentelemetry.io/docs/languages/dotnet/exporters/),
[OTLP endpoint configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/),
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).

## Telemetry queries

Prometheus:

```promql
sum(http_server_request_duration_seconds_count{service_name="demo-api",http_route="/error",http_response_status_code="500"})
```

Loki (trace IDs are structured metadata, not index labels):

```logql
{service_name="demo-api",deployment_environment_name="lab"} | event_name="request_completed"
```

Tempo:

```traceql
{ resource.service.name = "demo-api" }
```

## Minimal HRM-like simulator (synthetic only)

- `GET /business-failure` returns HTTP **200** with `businessOutcome=failed`.
  An OpenTelemetry Counter `demo_business_operations_total{business_outcome="failed"}`,
  structured warning log and `SyntheticBusinessOperation` span record the failure
  independently of HTTP 5xx metrics.
- `POST /jobs/run` executes a deterministic, **awaited ThreadPool task**, with
  a `background_job_completed` log and `SyntheticBackgroundJob` child span.
  It is **not** a detached job, scheduler, retry mechanism or durable queue.

Neither endpoint processes employee records or financial data. The verifier
injects only synthetic canary values into a query, test header and ignored JSON
body and checks their absence from Console Logs, Prometheus series labels, Loki
records and Tempo traces. Passing this bounded test **does not establish**
complete Production PII protection or validate all possible log sources.

## Remaining before Migration-ready

Local Alloy outage/recovery and synthetic privacy checks are automated but
do **not** establish lossless delivery, complete data minimization, HA or
Production reliability. Legacy training Dashboard JSON and the old manual load-test script
have been removed from this branch. The empty dashboard provider remains
**only to preserve prior Grafana database dashboards**.
**Final acceptance remains pending**:
run fresh verification against this cleaned-up tree and review Git/isolation,
README accuracy and the remaining infrastructure gates. HRM code and
Production infrastructure are unchanged.
