# Grafana Observability Lab — Phase 0–5

This is a deliberately small, beginner-friendly observability stack:

- **Demo API** exposes application metrics.
- **Demo API** also writes structured JSON request-completion logs.
- **Grafana Alloy** collects the Demo API metrics and container logs, then forwards them to the matching backend.
- **Prometheus** receives the remote-written metrics and provides metrics storage and querying.
- **Loki** receives the logs and provides log storage and querying.
- **OpenTelemetry tracing** instruments Demo API HTTP requests and its `/slow` work steps.
- **Grafana Alloy** receives OTLP traces and forwards them to Tempo.
- **Tempo** receives the traces and provides trace storage and querying.
- **Grafana** queries Prometheus, Loki, and Tempo and is the UI you open in your browser.

The current data flows are:

```text
Demo API -> Alloy -> Prometheus ─┐
                                 ├-> Grafana
Demo API container logs -> Alloy -> Loki ─┘
Demo API OTLP traces -> Alloy -> Tempo ──┘
```

Prometheus no longer directly scrapes `demo-api`; Alloy owns that scrape and sends the metrics to Prometheus's remote-write receiver. This local Prometheus remote-write receiver topology is intentional for this low-volume learning lab and is not a universal production default.

For logs, Alloy uses a read-only Docker socket in this lab to discover and tail only the `demo-api` container logs, then sends them to Loki. Loki's local port and no-auth setup are for this lab only; do not expose Loki directly in production.

For traces, Demo API uses OpenTelemetry's ASP.NET Core instrumentation and sends OTLP/gRPC to Alloy. The `/slow` endpoint adds `ValidateRequest`, `SimulatedWork`, and `BuildResponse` child spans so a single request has an easy-to-explore trace. Alloy batches and forwards traces to Tempo using OTLP/gRPC.

Tempo stores trace blocks and WAL data on a local Docker volume. This is intentionally lab-only local filesystem storage: it has no production durability, scaling, authentication, or retention design.

Grafana is already configured with Prometheus, Loki, and Tempo datasources and the **Prometheus: First Look**, **Demo API Metrics**, **Demo API Logs**, and **Demo API Traces** dashboards. You do not need to add anything in the UI.

## Prerequisites

- Docker Desktop (or Docker Engine) with Docker Compose
- `curl` (used by the verification script)

## Start and inspect the lab

From this repository, run:

```sh
./scripts/start.sh
./scripts/verify.sh
```

Then open:

- Prometheus: First Look dashboard: <http://localhost:3000/d/prometheus-first-look>
- Demo API dashboard: <http://localhost:3000/d/demo-api-metrics>
- Demo API Logs dashboard: <http://localhost:3000/d/demo-api-logs>
- Demo API Traces dashboard: <http://localhost:3000/d/demo-api-traces>
- Grafana home: <http://localhost:3000>
- Demo API: <http://localhost:8081>
- Alloy UI: <http://localhost:12345>
- Prometheus (optional): <http://localhost:9090>
- Loki (local lab only): <http://localhost:3100>
- Tempo (local lab only): <http://localhost:3200>

Sign in to Grafana with the development-only defaults:

- Username: `admin`
- Password: `admin`

Grafana may ask you to change this development password. For different local ports or credentials, copy `.env.example` to `.env` and edit it before the first start. `.env` is ignored by Git and is read by both Docker Compose and the scripts; `start.sh` prints the configured Grafana URL. If you change credentials after Grafana's volume already exists, run reset so Grafana initializes again.

## Stop or reset

Stop containers while keeping dashboards, settings, and metrics:

```sh
./scripts/stop.sh
```

Delete all lab data and return to a fresh state (the script asks for confirmation):

```sh
./scripts/reset.sh
```

For non-interactive use, run `./scripts/reset.sh --yes`.

## What is persisted?

Docker named volumes retain Grafana data, Prometheus metrics, Loki logs, and Tempo traces across stops. Provisioning files and the starter dashboards remain version-controlled under `grafana/`; Prometheus, Loki, and Tempo configuration is under `prometheus/`, `loki/`, and `tempo/`.
