# Minimal Portable Alloy Migration-ready Spec

- **Status:** Approved scope / implementation and final acceptance pending
- **Branch:** `experiment/otel-alloy-separated-backends` (baseline `ba12e26ccfd1bc5c3ca20569b6385a0613caa0e7`)
- **Discipline:** Ponytail **ultra** — smallest sufficient change
- **Goal:** A portable reference for later HRM Admin API integration, **not** a production deployment.

## Problem Statement

The earlier Grafana lab has proven Metrics, Logs, Traces, correlation and alerting. We now need a **small, maintainable migration reference** that an HRM-like .NET API can connect to using OTLP. Production infrastructure has not been selected. The current branch also contains partially migrated configuration, obsolete experiment names and stale scripts, so a prior E1 success does not certify the current working tree.

## Solution

Keep one local reference stack and one application telemetry collector:

```text
Optional synthetic .NET Demo API --OTLP--> Grafana Alloy
                                      |--> Prometheus (metrics)
                                      |--> Loki       (logs)
                                      |--> Tempo      (traces)
                           Grafana ---+--- queries each backend
```

Default Compose starts only the observability platform. The Demo API starts only through an **optional profile**. All application Metrics, Logs and Traces use OTLP to Alloy; do not ingest the same app stdout logs or metrics again through Docker or scraping. Reuse existing functioning components. No additional OpenTelemetry Collector.

## User Stories

1. As a maintainer, I want one local Compose configuration and clear start/verify/stop commands, so that I can reproduce the platform without choosing among experiments.
2. As an integrator, I want one configuration-driven OTLP endpoint and minimal .NET guidance, so that HRM can connect later without modifying this platform's source.
3. As an operator, I want application Metrics, Logs and Traces in Prometheus, Loki and Tempo, so that I can investigate the same event across signals.
4. As a reviewer, I want synthetic HTTP success, slow, HTTP 500 and business failure with HTTP 200, so that I can distinguish transport errors from business outcomes.
5. As a reviewer, I want one deterministic synthetic background operation, so that I can verify job-style telemetry without a database, queue or scheduler.
6. As a privacy reviewer, I want telemetry limited to approved technical and low-cardinality business attributes, so that no HRM-like sensitive data leaks.
7. As a maintainer, I want a repeatable automatic PASS/FAIL verification and safe evidence, so that completed training exercises do not need manual repetition.
8. As a future deployment owner, I want deferred infrastructure/security decisions listed explicitly, so that local success is not mistaken for production approval.

## Implementation Decisions

1. **Repository boundary:** Change only this Grafana repository/branch. Do not edit `hrm-repo`. Preserve `main`, the previous LGTM branch, the historical WP6/G11 evidence and handoff stash `28d7f3f0fc4e57a4129ea541f452df7ddbcb3c7e`.
2. **Minimal deployment:** One local Docker Compose project with Alloy, Prometheus, Loki, Tempo and Grafana. An existing one-shot volume initializer may remain if required; optional Demo API must not run by default. No infrastructure provisioning templates.
3. **Collector:** Use Grafana Alloy Default Engine only. Route application OTLP metrics to Prometheus, logs to Loki native OTLP, and traces to Tempo. Preserve a working local metrics conversion/receiver; do **not** treat its ingestion mode as the final Production decision.
4. **App portability:** A future .NET application selects its OTLP endpoint and service identity through configuration. No new shared SDK package, facade, configuration framework or HRM-specific business code.
5. **Smallest simulator:** Reuse the existing `/ok`, `/slow`, `/error` and health behavior. Add one **synthetic business-failure** case that still returns HTTP 200, with explicit queryable outcome telemetry, and one **manually triggered deterministic background operation** with safe log/trace evidence. No real payroll processing, persistence, message broker or cron infrastructure.
6. **Telemetry policy:** Application attributes may include safe service/version/environment identifiers, HTTP route templates/method/status/duration, event type, bounded business outcome, and trace/span identifiers. Review standard automatic instrumentation fields; never intentionally export request/response bodies, raw query strings, Authorization/Cookie values, secrets, employee identifiers, payroll amounts or identifying user data. Keep high-cardinality trace and instance IDs out of Loki's **index labels**.
7. **Security boundary:** Local reference ports bind to loopback; credentials are not committed. This Compose environment does **not** authorize externally exposed unauthenticated OTLP or backend endpoints. Remote TLS/authentication, tenant isolation, durable/object storage, retention, backups and HA will be decided when Production Infrastructure is known.
8. **Grafana scope:** Keep only required Prometheus/Loki/Tempo datasource provisioning. Remove obsolete training dashboards/alerts from the **new branch**, but do not destructively delete dashboards in previously deployed Grafana instances or protected volumes.
9. **Lifecycle:** One reliable start, verify and stop workflow. Stopping preserves volumes and unrelated Docker projects. Remove or replace E1-specific names/references. Destructive cleanup is not part of normal operation.
10. **Documentation:** Maintain one concise README with the topology, local start/verify/stop, optional Demo profile, OTLP integration variables/attributes, privacy policy, limitations and future HRM integration checklist. No duplicate handoffs or new project scaffolding.
11. **Versioning:** Pin and verify the chosen container image versions; do not upgrade unrelated dependencies merely to chase new releases.

## Testing Decisions / Acceptance Criteria

**Primary test seam:** One black-box check: synthetic API request → OTLP → Alloy → actual Prometheus/Loki/Tempo API queries. Prefer the current verifier and standard library; no new test framework unless unavoidable.

- [ ] **Configuration:** One Compose configuration starts the platform; optional Demo profile behaves correctly. All advertised CLI commands run without stale references. Compose and Alloy validation pass.
- [ ] **Requests:** Fresh `/ok`, `/slow`, `/error` return expected status codes and generate identifiable new telemetry (do not pass based on existing data in retained volumes).
- [ ] **Metrics:** Fresh Prometheus request/latency signal changes after a controlled request; HTTP 200 business failure produces a distinct low-cardinality business-failure outcome without being counted as HTTP 5xx.
- [ ] **Logs:** Loki contains exactly one logically corresponding structured completion log for the synthetic error Trace ID; no duplicate ingestion from container logs.
- [ ] **Traces:** Tempo returns the **same exact** trace as the matching Loki log, with appropriate HTTP status and the existing useful child spans.
- [ ] **Background operation:** One deterministic synthetic job-like operation emits queryable, safely correlated telemetry without requiring external infrastructure.
- [ ] **Privacy/cardinality:** Synthetic sensitive sentinels do not appear in inspected Console, Prometheus, Loki or Tempo output; trace/instance IDs are not Loki index labels.
- [ ] **Independence:** A bounded local test of Alloy unavailability does not change successful API responses into failures. Document any dropped telemetry; do not claim lossless delivery.
- [ ] **Isolation and lifecycle:** Stopping the reference preserves its volumes and does not touch other Compose projects, prior evidence or the handoff stash.
- [ ] **Evidence:** A **fresh test after final cleanup** produces a sanitized PASS/FAIL record and reproducible commands. Missing checks are `UNVERIFIED`, never silently PASS.

**Definition of done:** All checks above PASS on the final branch worktree and the README accurately describes that behavior. The verdict is **Portable Migration-ready**, not Production-ready. No manual re-run of previously closed Grafana learning exercises is required.

## Out of Scope

- Any edits to HRM API/Frontend repositories or connection to real HRM services/data.
- Production cutover, deployment credentials, TLS ingress, Kubernetes/Terraform, Cloud-specific configuration, high availability, external storage provisioning, backup automation or production SLO commitments.
- Recreating dashboards, alerts, Telegram drills, learning sessions, or Phase 5/LGTM resource benchmarks already completed.
- Pyroscope, profiling, sampling systems, service graphs, multi-collector topology, real background-job infrastructure or new shared .NET libraries.
- Git stage/commit/push/merge and destructive Docker/volume cleanup unless separately authorized.

## Further Notes

### Agreed decisions

| Decision | Selected |
| --- | --- |
| Q1 | A — Portable Migration-ready |
| Q2 | A — Minimal HRM-like simulator |
| Q3 | C — Production infrastructure unknown |
| Q4 | B — Grafana repository only; no HRM changes |
| Q5 | A — Strict telemetry allowlist |
| Q6 | A — One local reference Compose; optional Demo |
| Q7 | A — Remove unnecessary training dashboards/alerts from this branch |

### Observed worktree at specification time

- Branch already has **uncommitted partial migration changes**. Keep and reconcile these deliberately; do not reset/stash/overwrite unrelated work.
- Main Compose is partly migrated to the portable stack, but lifecycle scripts still reference the **deleted** `compose.e1.yaml`; current scripts therefore are not accepted as ready.
- Old training dashboards remain. The README and verification naming still refer to E1.
- This document records the **target**, not implementation PASS. The earlier Demo E1 PASS was on a different working-tree state.

### Smallest delivery order

1. Reconcile Compose/profile, scripts and the already-edited working tree.
2. Add only missing synthetic business-outcome/background-operation telemetry and privacy checks.
3. Reuse and simplify end-to-end verification; remove obsolete dashboard/alert and experiment artifacts **within this branch only**.
4. Update the README, run one clean fresh verification, report evidence and remaining infrastructure gates.

**Deferred infrastructure gate:** Before actual Production migration, separately approve hosting/network topology, TLS/authentication, tenancy, sensitive-data controls, retention/object storage, backup/restore, capacity and recovery objectives. Do not silently transform the reference stack into a production deployment.

### Official references

- [OpenTelemetry OTLP exporter configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)
- [Grafana Alloy OTLP receiver](https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.receiver.otlp/)
- [Loki OTLP ingestion](https://grafana.com/docs/loki/latest/send-data/otel/)
- [Loki recommended index labels](https://grafana.com/docs/loki/latest/get-started/labels/modify-default-labels/)
