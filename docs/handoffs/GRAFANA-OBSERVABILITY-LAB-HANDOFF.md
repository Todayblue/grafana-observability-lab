# Grafana Observability Lab — Canonical Handoff

Last reconciled: **2026-10-14 (Asia/Bangkok)**  
DevBridge projectId: `grafana-observability-lab`  
Primary continuation: **G0–G10 INDEPENDENTLY REVIEWED PASS / G11 FINAL_PASS / EXPERIMENT_FINAL_PASS=YES / EXPERIMENT_CLOSED — INDEPENDENT_FINAL_PASS** (see Section 0.10; historical Section 0.1–0.9 snapshots remain preserved)  
Implementation lane so far: **ChatGPT**, per user selection; no unrequested agent delegation.  
This file follows the continuity style of `hrm-cicd-lab/docs/handoffs/HRM-CICD-LAB-HANDOFF.md` but is **specific to this observability experiment**.

> **Read this document before resuming in a new ChatGPT Project mcp chat.** Current Git, Docker, and evidence files are the source of truth if any snapshot here becomes stale. This is a handoff, **not permission** to stage, commit, push, merge, delete volumes, or start WP5 automatically.


## 0. CURRENT CHECKPOINT — 2026-10-14 (Asia/Bangkok)

> **This is the current status and next-task authority for this handoff.** Sections 1–10 below preserve the 2026-10-09 WP4 → WP5 historical handoff. Historical statements that WP5/WP6 have not started, or that the next step is WP5, have been superseded. Do not relabel earlier failed evidence as PASS, or conflate an executor result with an independent final acceptance verdict.

### 0.1 Authority, Git and live runtime

- Canonical scope/gates: [Execution-Ready Spec #9](https://github.com/Todayblue/grafana-observability-lab/issues/9), [Wayfinder map #1](https://github.com/Todayblue/grafana-observability-lab/issues/1) and owner decisions #2–#8. Issue #9's planning-only header is an older planning snapshot, not an updated implementation status.
- Sources: the 2026-10-14 conversation export, Mac WP7 review-packet execution-summary.json and read-only Git/Docker checks made on 2026-10-14. Reinspect primary evidence when resuming.
- Repository: ~/Documents/GitHub/grafana-observability-lab; **branch experiment/otel-lgtm**, HEAD **ba12e26ccfd1bc5c3ca20569b6385a0613caa0e7**, **zero staged**. Preserve both modified tracked files and all untracked experiment material. This handoff and the patched dashboard JSON are untracked; a normal git diff does not reveal their content.
- Scratch Grafana LGTM at **127.0.0.1:3302**, Demo API at **127.0.0.1:8084**; fresh read-only inspection shows **grafana-wp6-lgtm** containers **2/2 Healthy**. Original Phase 5 and original LGTM stacks are stopped, and Phase 5 benchmark scratch is stopped. This is a point-in-time observation, not ongoing monitoring.
- This handoff update makes no Docker Runtime, Original Volume, Git history or HRM/CI-CD changes.

### 0.2 Reconciled status (latest primary WP7 packet)

| Work / gate | Latest supported result | Qualification |
|---|---|---|
| WP0–WP2 / G0–G4 | Scoped PASS | Based on previous primary verification |
| WP3 / G5 | **UNVERIFIED_POST_PATCH_UI** | Historical UI pass does not verify the current patched TraceQL table |
| WP4 / G6 | PASS: **11/11 live**, **29/29 fixtures** | Controlled fixtures are not live outages |
| WP5 / G7 | **PASS_EXECUTOR_SCOPED** | LGTM-only outage, API continuity, post-recovery fresh telemetry |
| WP5 / G8 | **PASS_LATER_DISPOSABLE_RECONCILIATION_WITH_LIMITS** | Original volumes retained; disposable reset allowed; restore verified at file/database level, not separate restored-application replay |
| WP6 Phase 5 | Scoped smoke PASS | Isolated 7-service Phase 5 Syslog → Alloy/Loki; no Docker socket mount |
| WP6 LGTM fresh backend | **8/8 PASS** | Post-reboot Metrics, Logs and Traces verified |
| WP6 Benchmark | **6/6 measured trials PASS** | Phase 5 3/3 + LGTM 3/3, **3,600 measured requests**; do not rerun without invalidating evidence |
| WP6 / G9 | **UNVERIFIED_CURRENT_UI_BENCHMARK_PASS** | Benchmark complete; four-dashboard + two-way UI acceptance after patch still missing |
| WP7 / G10 | **PARTIAL_REVIEW_PACKET_READY** | Review documentation/evidence prepared, G9 evidence absent |
| G11 Independent FINAL Gate | **NOT_STARTED** | Independent reviewer has not issued verdict |
| Experiment FINAL PASS | **NO** | No automatic promotion/commit/push/merge |

These exact G5/G9/G10/G11 statuses match the Mac WP7 packet's execution-summary.json: result **REVIEW_READY_G9_G10_INCOMPLETE**, final_pass **false**. Do not silently upgrade them.

### 0.3 Benchmark comparability and patch

Historical matched benchmark: 3 runs per architecture at 5 RPS, with 30s idle, 60s warm-up and 120s measured windows; request mix /ok 70%, /slow 20%, /error 10% (HTTP 500 expected on /error).

| Container-level measure | Phase 5 Syslog-isolated scratch | LGTM scratch |
|---|---:|---:|
| Median CPU | 7.18% | 8.58% (+19.50%) |
| Median RAM | 1.56 GB | 1.08 GB (-30.65%) |
| Scratch volume disk | 73.69 MB | 642.90 MB (approximately +772%) |

Do not mistake container CPU/RAM for complete Docker Desktop VM overhead, or conclude that LGTM saves disk. Phase 5 used a **socket-free Syslog variant**, not the unmodified original Docker-socket collector, which limits architectural comparability.

On 2026-10-14 the source dashboard **grafana/otel-lgtm/dashboards/demo-api-traces.json** was minimally changed from panel type **traces** to **table**. Local read-only inspection confirms the file now contains type table. Earlier tests confirmed the dashboard JSON/mount and fresh Tempo search, but **post-patch actual table rows and two-way UI clicks remain UNVERIFIED**. Preserve the previous failed UI result.

Grafana references: [TraceQL Search](https://grafana.com/docs/grafana/latest/datasources/tempo/query-editor/traceql-search/) explains search-result rows; [Trace-to-Logs](https://grafana.com/docs/grafana/latest/datasources/tempo/configure-tempo-data-source/configure-trace-to-logs/) documents the two required Loki↔Tempo correlation directions. Documentation support is not a substitute for a live UI click.

### 0.4 Protected evidence on Mac

Base: ~/Library/Application Support/GrafanaObservabilityLab/evidence/

- Durable WP4/WP5: **retention-20261009T085536Z-ad1e30d2/** (earlier hash check 49/49 PASS).
- WP6/WP7 work: **wp6-wp7-one-pass-20261012/**, including fresh 2026-10-14 LGTM telemetry and prior benchmark.
- Historical **pre-patch UI failure**: wp6-wp7-one-pass-20261012/wp6-g9-ui-verdict-20261012T103404845125Z-014cb1/; preserve as failed historical evidence.
- WP7 packet: **wp6-wp7-one-pass-20261012/wp7-review-packet-20261014T045830578989Z-7963e3/**. Contains Architecture Spec, Runbook, Sanitized Evidence Index, Rollback Guide, execution-summary.json, independent-review.md and manifest. Prior verification reported 25/25 packet SHA-256 and 12/12 referenced evidence SHA-256 PASS. This is a review-ready packet, **not** an independent G11 verdict.
- Never overwrite hashed old evidence when adding current UI checks; create a new, sanitized addendum and regenerate the applicable manifest/index.

### 0.5 Browser context and exact next actions

- Historical user/agent session: Playwright CLI **brave**, PLAYWRIGHT_SOCKETS_DIR set to **$HOME/.pwcli-sockets**, @playwright/cli version **0.1.22**. On 2026-10-14 the user reported GRAFANA_TAB_VISIBLE, and the prior ChatGPT reported Remote Desktop **tab-list** working. This confirms visibility only, **not** Trace Table or cross-signal UI acceptance. Recheck on resumption.
- The existing operator-wp6-grafana-trace-table-ui-check.py under the WP6 work directory can emit up to three synthetic API requests if data is stale; it is not a strictly read-only check.
- The historic browser export contained a token-bearing Extension URL. Treat it as sensitive; rotate privately, never echo tokens/URLs/cookies/passwords into chat or evidence. No gratuitous Attach/Detach.
- **Next 1:** read-only preflight for branch/HEAD/untracked files, Docker scratch health, evidence manifests and Brave session.
- **Next 2 (G5/G9):** verify the **actual** post-patch TraceQL search table contains rows with no query error; check **all four Grafana dashboards** and real **Logs → exact Trace → Related Logs** navigation with the same fresh W3C TraceId. Capture sanitized screenshots/DOM and traceable evidence. Backend success alone is insufficient.
- **Next 3 (G10):** reconcile G0–G10, update review packet/evidence hashes, retain historical fail artifacts, and record all limitations.
- **Next 4 (G11):** independent reviewer (separate from implementation executor) inspects primary evidence and issues an explicit PASS/FAIL/UNVERIFIED verdict. Until then, **EXPERIMENT_FINAL_PASS=NO**.
- No WP5 re-run or WP6 benchmark re-run without new evidence of invalidation. No routine A/B/C micro-approval requests; stop only on a genuine scope/safety decision.

### 0.6 Safety and fresh-chat bootstrap

- ChatGPT Direct is the user-selected documentation executor; preserve the current simplicity preference (Ponytail Ultra) without expanding lifecycle authority. Original work remains uncommitted.
- **No** Git stage/commit/push/merge/reset/clean/stash; no Docker global cleanup, original Phase 5/LGTM resource mutation, volume deletion, unapproved scratch lifecycle, HRM or CI/CD changes, Build/Pull, or safety-tool bypass.
- Use the already-authorized Brave connection only for scoped Grafana UI evidence; previous approval to retry Playwright through Remote Desktop was **not** blanket authorization to start/stop Docker.
- Start new work in **Project Gafana** (the older section 9 refers to Project mcp and is historical). Read this file's Section 0, Issue #9, actual Mac/Git/Docker/Evidence; do not assume the historical snapshot is live.

**Suggested new-chat prompt:** Continue grafana-observability-lab from docs/handoffs/GRAFANA-OBSERVABILITY-LAB-HANDOFF.md **Section 0 (2026-10-14)**. ChatGPT Direct, Ponytail Ultra, evidence-first. Read-only preflight of experiment/otel-lgtm, Mac Docker scratch, WP7 evidence and Brave session brave. WP5 executor-scoped PASS, WP6 6/6 benchmark PASS (3,600 requests), fresh LGTM backend 8/8 PASS: **do not rerun benchmark**. Main blocker: G5/G9 post-patch real UI table rows, Grafana 4/4 and Logs↔Traces exact-ID clicks. If UI passes, finalize G10 packet and request independent G11 review; do not declare final pass or Commit/Push/Merge. No token access, duplicate Attach, unauthorized Docker mutation, original Volume or HRM/CI-CD changes.

### 0.7 Live continuation checkpoint — 2026-10-14 13:04 Asia/Bangkok

ChatGPT Direct, Ponytail Ultra, inspected the actual authorized Mac with strict read-only preflight before preparing a **new additive evidence report**. Branch `experiment/otel-lgtm` and HEAD `ba12e26ccfd1bc5c3ca20569b6385a0613caa0e7` match Section 0.1; staged = 0. Scratch `grafana-wp6-lgtm` still has 2/2 healthy containers. Prior WP5/WP6 successes are retained, not rerun.

Newly recalculated SHA-256 **and byte lengths**: original WP7 review packet **25/25 PASS**, linked external files **12/12 PASS**, protected retention **49/49 PASS**. The source trace dashboard still uses `type: table`; actual post-patch UI remains unverified.

Brave itself was running, but the named Playwright CLI session `brave` returned `SESSION_NOT_OPEN`. An approved token-free Attach attempt failed to establish an accessible session; recheck was still `SESSION_NOT_OPEN`. Its pending process was terminated without closing Brave. No secrets were retrieved or printed. No real 4/4 fresh dashboard inspection, TraceQL table-row screenshot, or exact-ID Loki -> Tempo -> related Loki click occurred.

**Gate status remains G5 UNVERIFIED, G9 UNVERIFIED, G10 PARTIAL and G11 NOT_STARTED; EXPERIMENT_FINAL_PASS=NO.** A new sanitized, hashed reconciliation and independent-review preparation bundle was created **without replacing** the frozen WP7 packet:

`~/Library/Application Support/GrafanaObservabilityLab/evidence/wp6-wp7-one-pass-20261012/wp7-g10-g11-readiness-20261014T060437Z/`

It contains `G10-RECONCILIATION.md`, `G11-INDEPENDENT-REVIEW-BRIEF.md`, `execution-summary.json`, and `manifest.json`. G10 cannot be marked complete without genuinely observed post-patch G5/G9 UI acceptance. G11 is ready for a **different** independent reviewer once missing UI evidence is available; no verdict has been issued.

**Next:** user-managed reauthorization/recovery of the existing scoped Playwright Extension session (without exposing tokens), then real fresh UI checks, an additive hashed G5/G9 packet, G10 final reconciliation, and only then G11 independent verdict. Do not rerun WP5/WP6 benchmark, self-approve browser consent, or mutate Docker/Git history.

### 0.8 Live Chrome G5/G9/G10 executor closeout — 2026-10-14 18:14 Asia/Bangkok

**THIS SECTION SUPERSEDES the older G5/G9/G10 UNVERIFIED snapshots above while retaining them as historical states. G11 is still an independent gate, and EXPERIMENT_FINAL_PASS=NO.**

- Owner confirmed headed Google Chrome Automation visible; ChatGPT Direct controlled authenticated dedicated Playwright Chrome MCP through private tunnel. No Brave Extension reuse needed.
- Live read-only preflight: experiment/otel-lgtm, HEAD ba12e26ccfd1bc5c3ca20569b6385a0613caa0e7, staged 0; existing 2 tracked modifications and untracked experiment files untouched. Docker scratch 2/2 healthy; no Docker lifecycle mutation.
- Three **new bounded W3C traceparent GETs** at 2026-10-14 10:59:27 UTC: /ok=200, /slow=200, /error=500 all matched expectations; **not** a benchmark.
- Four Grafana dashboards inspected via real UI: Prometheus First Look (Collector UP); Demo API Metrics (all expected panels), Demo API Logs (3 fresh request_completed lines, errors 1), and Demo API Traces (patched TraceQL Table, 3/3 new Trace IDs as clickable rows).
- Real Chrome click chain: fresh Loki /error log → View Trace → Tempo demo-api GET /error root span, then Related logs → bounded Loki query with **same exact Trace ID 334826301cb25049259c1f0e346b2f66** and **one matching line**.
- UI limitation: TraceQL result-table Service cells still display <root span not yet received> although Tempo detail page shows actual root span; instant metrics after sparse probes may read 0 req/s. Preserve and have independent reviewer assess rather than altering scope.
- Six real Chrome screenshots and sanitized structured observation copied into a **new additive** hashed evidence packet (none of the original packet, historical failed artifacts or protected retention overwritten):
  ~/Library/Application Support/GrafanaObservabilityLab/evidence/wp6-wp7-one-pass-20261012/wp7-g5-g9-chrome-ui-20261014T105927118709Z/
- New G10 packet hashes **12/12 PASS**; original WP7 packet **25/25 PASS**, original external references **12/12 PASS**, protected retention **49/49 PASS**. Contains G10-EVIDENCE-RECONCILIATION.md, G11-INDEPENDENT-REVIEW-REQUEST.md, execution-summary.json, manifest.json, README-TH.md, probes.json and grafana-ui/.
- Final scoped results: **G5=PASS_EXECUTOR_SCOPED**, **G9=PASS_EXECUTOR_SCOPED** (existing WP6 benchmark reused), **G10=PASS_EXECUTOR_SCOPED**, **G11=NOT_STARTED_INDEPENDENT_REVIEW_REQUIRED**, **EXPERIMENT_FINAL_PASS=NO**.
- Next and only remaining mandatory acceptance gate: genuinely independent reviewer (not ChatGPT Direct executor) rehashes and inspects primary packet, privacy, negative tests, recovery/restore, benchmarks, UI screenshots, exact trace-ID proof and Root Service-column discrepancy. Reviewer issues attributed G11 FINAL PASS/FAIL/UNVERIFIED. Do not relabel G11 without independent evidence. No Git staging/commit/push/merge, Docker runtime changes, WP5 or WP6 benchmark rerun.

### 0.9 G11 reviewer-attempt outcome — 2026-10-14

- G11 independent review was requested through DevBridge Codex (different executor from ChatGPT Direct) with STRICT READ-ONLY instructions.
- Direct review run: agent_ef14e61a7a82c7ef0185958d57676088, FAILED exit code 1 before any reviewer stdout/verdict; only sanitized diagnostic returned.
- One attempted durable alternative was BLOCKED: current verified capability evidence false, provider unavailable. It never produced a review verdict.
- **G11 = UNVERIFIED_REVIEWER_INFRASTRUCTURE_BLOCKED; EXPERIMENT_FINAL_PASS=NO.** Do not misrepresent an attempted review as completed, and do not infer a failed experiment from the failed reviewer transport.
- Existing G5/G9/G10 executor-scoped evidence packet remains valid and hashed; the next action is a genuinely independent, strict read-only reviewer when the Codex provider/alternate independent reviewer is available. No WP5/WP6 benchmark replay or Git/Docker mutations are required merely for this blocker.


### 0.10 G11 independent final closeout — 2026-10-14 (Asia/Bangkok)

**CURRENT AND AUTHORITATIVE FINAL CHECKPOINT — supersedes the G11 PENDING/UNVERIFIED snapshots in 0.1–0.9, while preserving those historical findings.**

- **G11=FINAL_PASS** by **GPT-6 in an Owner-designated new ChatGPT conversation** acting as Independent Reviewer; executor was the earlier ChatGPT Direct conversation. Independence is **a separate review conversation and fresh primary-source examination**, not a different human/model provider. The prior DevBridge Codex failure in 0.9 produced no verdict and remains a preserved historical infrastructure event.
- **G0–G10=PASS**, each independently mapped to original primary evidence. Reviewer inspected Git, Docker isolation, pinned ARM64 LGTM digest, WP4 live/fault-injection checks, WP5 G7 resilience, later G8 isolated scoped reset/file-and-SQLite restore, six WP6 matched benchmark trials, all four live Grafana dashboards, historical UI failure and postpatch current evidence.
- Fresh SHA-256 **and byte-size** recomputation: original WP7 **25/25**, its external references **12/12**, new Chrome G5/G9 packet **12/12**, protected retention **49/49**, WP6 raw benchmark entries **7/7**, latest WP4 **5/5**, WP5 **10/10**, G8 **6/6**, G10/G11 readiness **3/3**. Independently rehashed Oct 14 fresh MLT summary; all checked hashes matched. Frozen originals were not modified.
- Reviewer personally replayed authenticated Chrome UI navigation (not a new probe): **Loki /error log -> View Trace -> Tempo demo-api GET /error root span (HTTP 500) -> Related logs**. All links maintained exact W3C Trace ID `334826301cb25049259c1f0e346b2f66`; bounded LogQL returned **one** matching `request_completed` log. Four dashboards were inspected through actual Chrome DOM; two additional independent screenshots were preserved.
- **Findings openly retained:** TraceQL table Service displays `<root span not yet received>`, Name may be blank and raw nested frame JSON visible, but Tempo detail/root and exact-ID navigation work. G8 proven through 1,587 file SHA matches and Grafana SQLite integrity, **not separate restored-app replay**. WP6 comparator used socket-free Syslog; container CPU/RAM exclude Docker Desktop VM; LGTM scratch disk was significantly larger (~+772%); startup/restart numeric trial timing not extracted; sparse instant Request Rate may read zero after the 3-probe cohort.
- **Documentation/evidence-only Phase C completed:** independent review report, evidence addendum, two new reviewer UI screenshots, machine-readable summary, new SHA-256 `manifest.json`, and closeout summary created separately. Original WP7/Chrome/retention/historical failed packets retained unchanged.
- Canonical final evidence directory:
  `~/Library/Application Support/GrafanaObservabilityLab/evidence/wp6-wp7-one-pass-20261012/g11-independent-final-20261014T132044Z/`
  Read `G11-INDEPENDENT-REVIEW.md`, `G11-EVIDENCE-ADDENDUM.md`, `G11-CLOSEOUT-SUMMARY.md`, `execution-summary.json`, and `manifest.json`.
- **EXPERIMENT_FINAL_PASS=YES**. **EXPERIMENT_CLOSED — INDEPENDENT_FINAL_PASS**. Closure is strictly scoped to this local experiment; **NOT** production readiness, main merge, deploy, automatic promotion or Git release. No stage/commit/push/merge/reset/clean/stash, no Docker lifecycle, app code, Grafana config, credentials or original volume changes.
- The explicit `G11 FINAL_PASS` finding was issued **before** any new documentation/evidence write; post-write SHA-256, consistency and Git/Compose read-only verification seal this additive closeout. If comparing historic sections, use this Section 0.10 as the authoritative later status, not by retroactively editing earlier reports.

---

## 1. Authority, decisions, and safety boundaries

- Canonical Wayfinder [Decision Map — Q1–Q46](https://github.com/Todayblue/grafana-observability-lab/issues/1); seven design Decision Tickets resolved and closed.
- Canonical [Execution-Ready Spec — WP0–WP7, G0–G11](https://github.com/Todayblue/grafana-observability-lab/issues/9) (**planning artifact**; actual independent FINAL PASS is separate).
- [Runtime/isolation decision](https://github.com/Todayblue/grafana-observability-lab/issues/2), [metrics contract](https://github.com/Todayblue/grafana-observability-lab/issues/3), [logging/privacy contract](https://github.com/Todayblue/grafana-observability-lab/issues/4), [trace identity](https://github.com/Todayblue/grafana-observability-lab/issues/5), [Grafana two-way correlation](https://github.com/Todayblue/grafana-observability-lab/issues/6), [fresh-data/recovery verifier](https://github.com/Todayblue/grafana-observability-lab/issues/7), [benchmark/independent gate](https://github.com/Todayblue/grafana-observability-lab/issues/8).
- **In scope:** isolated local Grafana Observability Lab on the Mac, ASP.NET Core .NET 8 Demo API, and `grafana/otel-lgtm` OpenTelemetry-native Metrics/Logs/Traces.
- **Out of scope:** Jenkins, GitHub Actions, webhook/CI/CD, cloud VM, Linux production deployment, PostgreSQL provider, HRM production, HRM source changes, credentials/real employee data, production observability, Kubernetes, additional Alloy in this experiment, Prometheus exemplars, and zero-loss telemetry promises.
- **Protect `main`:** full-stack Phase 5 remains baseline; do not modify original `compose.yaml` or original Phase 5 volumes. Experiment runs on `experiment/otel-lgtm`.
- **Git:** do not stage/commit/push/merge/reset/clean/stash without separate explicit user approval. WP1–WP4 code is currently **uncommitted local work**, and must be preserved exactly.
- **Docker:** no `docker system prune` or other global cleanup, no changes to unrelated HRM or legacy SQL Edge containers/images/data. Never run `scripts/reset.sh` from the Phase 5 stack against this experiment.
- **Destructive operations:** only after a separately approved, scoped plan that names the specific experiment resource(s) and validates backups/isolation. Current live experiment `/data` and evidence must not be discarded.
- **Executor:** preserve user choice (ChatGPT did WP1–WP4). Engineering Execution skill governs repository edits; default simplicity lens is `full` unless user explicitly changes it.

## 2. Historical goal and 2026-10-09 stop point (superseded by Section 0)

Experiment with **2 containers** instead of Phase 5's multi-container Alloy stack, while improving the learning/verification quality:

1. `demo-api`: .NET 8 Application with OpenTelemetry-native Metrics, structured Logs, and Traces.
2. `lgtm`: official pinned `grafana/otel-lgtm` all-in-one image, containing bundled OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana (and Pyroscope, out of acceptance scope).

**As of the latest verified evidence: WP0, WP1, WP2, WP3 and WP4 have passed their respective scoped tests.** WP4 has machine-readable current-run results and fault-injection tests. **WP5 outage/recovery, volume reset/restore, WP6 benchmarking and WP7 independent FINAL gate are NOT STARTED.**

```text
WP0  Read-only preflight / compatibility         PASS (historical snapshot; recheck)
WP1  Isolated LGTM + Demo API 2-container runtime PASS (focused)
WP2  Native OTel Metrics/Logs/Traces              PASS (focused)
WP3  Grafana dashboards + 2-way UI correlation   PASS (reproduced by user)
WP4  Deterministic live E2E + fail-closed faults  PASS (11/11 live checks; 29/29 fixtures)
WP5  Recovery, persistence/reset/restore drills  NOT STARTED — NEXT, new approval required
WP6  Controlled 3-run benchmark + usability      NOT STARTED
WP7  Four deliverables + independent FINAL gate  NOT STARTED
Main promotion / commit / push / PR / merge       NOT AUTHORIZED
```

**Do not describe this as the entire experiment FINAL PASS.** A WP4 PASS is not the G11 independent verdict.

## 3. Repository and last verified Git snapshot

Local repository:

```text
/Users/todayisblue/Documents/GitHub/grafana-observability-lab
```

Public GitHub repo: [Todayblue/grafana-observability-lab](https://github.com/Todayblue/grafana-observability-lab).

At handoff creation, the inspected branch and HEAD were:

```text
branch: experiment/otel-lgtm
HEAD:   ba12e26ccfd1bc5c3ca20569b6385a0613caa0e7
staged: none reported
worktree: dirty (intended local WP1–WP4 changes, not committed)
```

Two modified tracked files: `demo-api/Program.cs` and `demo-api/demo-api.csproj`.

Untracked experiment files/directories (preserve all):

```text
README.otel-lgtm.md
compose.otel-lgtm.yaml
demo-api/SafeDemoSpanProcessor.cs
grafana/otel-lgtm/                          # new dashboard JSONs and provisioned YAML
scripts/otel-lgtm.sh
scripts/otel_wp4_checks.py
scripts/test_otel_wp4_checks.py
scripts/verify-otel-wp2.py
scripts/verify-otel-wp3.py
scripts/verify-otel-wp3-ui.cjs
scripts/verify-otel-wp4.py
docs/handoffs/GRAFANA-OBSERVABILITY-LAB-HANDOFF.md  # THIS new handoff
```

Never assume the above snapshot still holds in a new chat: check live `git status --short`, `git rev-parse HEAD`, and `git branch --show-current`. Do **not** reset to the historical HEAD or discard untracked files.

The current `README.otel-lgtm.md` contains an older “27 regression cases” WP4 sentence. That was an **earlier count**; the authoritative latest test/evidence has **29 fixture cases**. This handoff records the reconciliation without rewriting the already-hashed README in the WP4 evidence source snapshot.

## 4. Local runtime and architecture

Most recent live inspection showed two healthy experiment containers, not an assumption about future availability:

| Item | Value |
|---|---|
| Compose file | `compose.otel-lgtm.yaml` |
| Compose project | `grafana-otel-lgtm-lab` |
| Container 1 | `grafana-otel-lgtm-lab-demo-api-1` |
| Container 2 | `grafana-otel-lgtm-lab-lgtm-1` |
| LGTM image | `grafana/otel-lgtm:0.34.0@sha256:b966ea107831d526d9eb8fe4d2d86c9e5731392fad9dce8296bcf2072031f07c` |
| ARM64 platform manifest | `sha256:bdbc807a21f55a3934d60c318f8270ee6b5aae07d954c83f6668dd64eef1168b` |
| Mac | Apple Silicon ARM64; Docker Desktop with ~7.65 GiB engine memory at WP0 |
| Grafana | http://127.0.0.1:3300 (localhost host binding) |
| Demo API | http://127.0.0.1:8082 (localhost host binding) |
| OTLP collector | `http://lgtm:4317` on internal Compose network, not published on Mac |
| LGTM volume | `grafana-otel-lgtm-lab_lgtm-data` mounted at `/data` |
| App resource identity | `service.name=demo-api`, `deployment.environment.name=lab`, `service.version=0.1.0-wp2` |
| Legacy Phase 5 Compose | `compose.yaml`; previously observed stopped; must not be mutated |
| HRM Compose | `hrmwebapi`; unrelated and previously stopped; must not be mutated |

```text
              experiment/otel-lgtm
.NET Demo API (8082 on localhost)
    |-- OTel standard HTTP Metrics --------+
    |-- structured ILogger Logs -----------+--> OTLP/gRPC --> LGTM Collector
    |-- OTel spans / W3C traceparent -------+                      |
    |                                                  +-----------+------------+
    |                                                  |           |            |
    |                                               Prometheus    Loki         Tempo
    |                                                  |           |            |
    +--> JSON Console diagnostics (NO stdout re-ingest into Loki)   |
                                                       +-----------+------------+
                                                                   |
                                                                Grafana :3300
```

**Instrumentation contract (WP2):**
- ASP.NET Core `http.server.request.duration` (seconds, explicit Histogram Buckets) and `http.server.active_requests`, no duplicate legacy `prometheus-net` HTTP Counters.
- Observed Prometheus classic series: `http_server_request_duration_seconds_count`, `_sum`, `_bucket`; and `http_server_active_requests`. Metrics freshness uses before/after deltas, not historical nonzero counts.
- Structured `request_completed` event: `http.route`, `http.response.status_code`, `duration_ms`, `TraceId`/`SpanId`. HTTP 2xx/3xx Information, 4xx Warning, 5xx Error; local JSON console is diagnostic only, not a second Loki ingest pipeline.
- Loki Indexed Labels verified: `service_name` and `deployment_environment_name`. High-cardinality `trace_id`, `span_id` and request-specific attributes are structured metadata, not Index Labels.
- Local 100% trace sampling; unique W3C `traceparent` per probe; `/slow` preserves `ValidateRequest` / `SimulatedWork` / `BuildResponse` children; HTTP 500 server span is Error with no fake exception; `/healthz` excluded from demo traces.
- Strict allowlist for span/log attributes; synthetic sensitive tokens must not appear in Console, Loki or Tempo. No production identifiers.
- During outages, API responses must remain independent of telemetry backend. Loss of **outage-period** telemetry can occur and is not automatically a failure; **post-recovery fresh** telemetry must return.

**Grafana contract (WP3):**
- Built-in LGTM Prometheus/Loki/Tempo/Pyroscope Datasources preserved.
- Added UID-isolated `lab-otel-prometheus`, `lab-otel-loki` and `lab-otel-tempo` using file provisioning in `grafana/otel-lgtm/provisioning/`.
- Four version-controlled dashboards live in `grafana/otel-lgtm/dashboards/` and render under **Observability Lab OTel**:
  - http://127.0.0.1:3300/d/prometheus-first-look
  - http://127.0.0.1:3300/d/demo-api-metrics
  - http://127.0.0.1:3300/d/demo-api-logs
  - http://127.0.0.1:3300/d/demo-api-traces
- Loki derived `TraceID` reads structured metadata and opens **View Trace** in Tempo; selecting Tempo request span exposes **Related logs** to Loki via exact W3C trace ID and service filter.
- The user independently repeated `verify-wp3`: all four Dashboards, 14 Query Targets and headless **Log → Trace → Logs** clicks PASS on a fresh trace ID.

## 5. WP4 — verified live results and provenance

### What was implemented

- `scripts/otel_wp4_checks.py` — pure, fail-closed validators shared by live probes and injected fixtures.
- `scripts/test_otel_wp4_checks.py` — in-memory synthetic fault cases (do **not** mutate live Prometheus/Loki/Tempo).
- `scripts/verify-otel-wp4.py` — fresh live W3C requests, per-signal bounded polling, Prometheus before/after metric sample delta, exact Loki/Tempo context, negative cases, real Grafana UI links and sanitized evidence.
- `scripts/otel-lgtm.sh verify-wp4` — wrapper command.
- `README.otel-lgtm.md` — WP4 instructions (note older fixture-count sentence flagged above).

**Historical troubleshooting (resolved, not current blockers):**
1. First fixture version had 27 cases; the final suite has **29/29 PASS**.
2. Early live run did not obtain current-process Prometheus baseline by the deadline; freshness/baseline logic was corrected without permitting stale-data PASS.
3. Another early live run failed on a Tempo 404 with empty Body; `http_backend` response parsing was fixed to preserve raw leading newline and distinguish genuine expected 404.
4. Later full WP4 runs are **PASS**; do not treat earlier failed experimental runs as current PASS, or erase their history.

### Independently inspected evidence bundles on the authorized Mac

All paths below are **Mac filesystem paths**, not ChatGPT sandbox download links.

| Run directory suffix under `/private/tmp/grafana-otel-wp4-evidence/` | Result | Live checks | Fixture cases |
|---|---|---:|---:|
| `20261009T071430498770Z-55c3cb3f` | FAIL (historic metric baseline) | 2 recorded | 27/27 fixtures in that earlier run |
| `20261009T072244709887Z-70d0b170` | FAIL (historic HTTP 404 parser) | 7 recorded | 29/29 |
| `20261009T072416321064Z-7604d040` | **PASS** | **11/11** | **29/29** |
| `20261009T072922212249Z-ae3e91a0` | **PASS** | **11/11** | **29/29** |
| `20261009T073044389843Z-ea78b657` | **PASS (LATEST INSPECTED)** | **11/11** | **29/29** |

Latest inspected canonical run:

```text
/private/tmp/grafana-otel-wp4-evidence/20261009T073044389843Z-ea78b657
```

The user also supplied an earlier successful path: `/private/tmp/grafana-otel-wp4-evidence/20261009T072416321064Z-7604d040`. It is valid, but **not the latest inspected PASS bundle**.

Read and validate:
- `execution-summary.json` — `result=PASS`, `scope=WP4_ONLY`, **11/11 checks PASS**, current-run HTTP probes, per-signal status/polling, screenshot reference, and `NOT_STARTED` markers for WP5, WP6, WP7.
- `negative-tests/results.json` — 29/29 controlled fault tests plus live negative checks; tests use same validators as live but **do not inject faults into running backends**.
- `probes/requests.json` — sanitized generated W3C Trace IDs, routes, methods and HTTP status evidence.
- `queries/query-contract.json` — sanitized PromQL/LogQL/Tempo query contract and observed metrics summary.
- `grafana-ui/wp3-related-logs.png` — actual Headless UI correlation result from a fresh probe.
- `manifest.json` — hash manifest (5 artifact files; manifest excluded from its own list).

**Integrity check performed during this handoff:** all five artifact file SHA-256 digests and recorded lengths in the **latest PASS bundle matched the actual files**; all **18 source file SHA-256 values in its execution summary matched the then-current worktree**. This is an integrity/provenance check, **not an independent acceptance review**. Do not modify those source files and then reuse the old hash proof as if nothing changed. The new Handoff file was created **after** that evidence run and was not among those 18 hashed files.

Latest WP4 `checks` (all `PASS`):
1. `preflight`
2. `fault_injection_fixtures`
3. `fresh_probe_context`
4. `fresh_metric_deltas`
5. `exact_log_trace_context`
6. `minimal_loki_index_labels`
7. `live_sensitive_data_negative`
8. `excluded_health_and_unknown_traces`
9. `live_wrong_trace_id_negative`
10. `two_way_grafana_ui`
11. `wp4_live_end_to_end`

**Evidence retention:** `/private/tmp` is not permanent. Avoid losing the verified bundles; later propose an approved secure evidence location **outside source repo**, copy while retaining hashes, and keep temporary artifacts until safe migration. Do not paste fake secret values or any real tokens/credentials into the Handoff.

## 6. Test commands and environment assumptions

Run from the correct Mac, not from an unrelated cloud/container session:

```sh
cd ~/Documents/GitHub/grafana-observability-lab

# Read-only reconciliation (before any new WP):
git branch --show-current
git rev-parse HEAD
git status --short
./scripts/otel-lgtm.sh status

# Runtime and focused validation (generate safe local probe traffic):
./scripts/otel-lgtm.sh verify
./scripts/otel-lgtm.sh verify-wp2

# WP3/4 headless UI require the existing Playwright installation on this Mac:
NODE_PATH="$HOME/Documents/GitHub/dev-bridge/node_modules" \
  ./scripts/otel-lgtm.sh verify-wp3

NODE_PATH="$HOME/Documents/GitHub/dev-bridge/node_modules" \
  ./scripts/otel-lgtm.sh verify-wp4

# Pure fixtures; no Docker/backend mutations:
python3 -B scripts/verify-otel-wp4.py --fixtures-only
```

- `verify-wp4` produces a new run directory under `/tmp/grafana-otel-wp4-evidence`. Defaults: `WP4_POLL_SECONDS=2` and `WP4_SIGNAL_DEADLINE=75` seconds per signal. Bounded retries; NEVER treat stale data as success.
- Grafana's WP3 browser test uses Node.js Playwright. `NODE_PATH` points to an existing DevBridge install; **no install required** to continue on this Mac if it is still present.
- Use Headless Browser; do not steal foreground window/focus while user works.
- Do not use a default-Docker-project command without explicitly verifying the Compose file and project name.

## 7. Historical acceptance gates (2026-10-09; superseded by Section 0)

| Gate | Current evidence |
|---|---|
| G0 Preflight/version/isolation | WP0 passed when run; current Git/ports/Docker must be rechecked |
| G1 Two-container runtime | WP1 PASS |
| G2 Native Metrics | WP2 PASS + WP4 fresh metric delta PASS |
| G3 Structured Logs/privacy | WP2 PASS + WP4 synthetic-secret negative PASS |
| G4 Trace identity and sampling | WP2 PASS + WP4 exact context/span assertions PASS |
| G5 Grafana provisioning/correlation | WP3 PASS; user reran; WP4 UI PASS |
| G6 Deterministic current-run tests | WP4 PASS, 11/11 live checks, 29/29 fixture tests |
| G7 Backend outage/API continuity/new telemetry recovery | **NOT STARTED (WP5)** |
| G8 Persistence/reset/isolated restore | WP1 basic volume recreate passed; **full WP5 gate NOT STARTED** |
| G9 Same-Mac repeated benchmark/4-dashboard usability | **WP6 NOT STARTED** (WP3 dashboard UI is only partial) |
| G10 Complete sanitized final evidence/handoff/rollback | **PARTIAL**; WP4 has a validated scoped evidence bundle |
| G11 Independent FINAL acceptance review | **NOT STARTED** |

`PASS`/`FAIL`/`UNVERIFIED` must remain distinct. No claim that WP4 simulated fault cases proved a live backend outage. No independent FINAL PASS until G0–G10 evidence is examined by a reviewer different from the executor.

## 8. Historical WP5 plan (2026-10-09; already executed)

**Next work package: controlled LGTM-only outage, post-recovery fresh telemetry, persistence/confirmation-scoped reset and one isolated backup/restore trial.** WP5 has **not** been authorized in this handoff-writing turn.

Recommended next-chat workflow:

1. **Read this handoff and [Execution-Ready Spec](https://github.com/Todayblue/grafana-observability-lab/issues/9)**; inspect latest WP4 `execution-summary.json`, `manifest.json` and real `git status`. Do not overwrite or clean uncommitted WP1–WP4.
2. Reconcile live Docker Compose ownership, Ports, container health, Volume names and free disk **read-only**. Phase 5, HRM and historic SQL Edge are out of scope. Check the environment is still isolated.
3. Confirm WP4 has a verified PASS bundle. If source/runtime has changed since that bundle, rerun scoped tests first rather than reusing stale evidence.
4. Explain proposed **WP5-only** actions/side effects, choose safe ordering, and ask for the user's explicit implementation approval if not already present.
5. On later authorization, stop **only experiment LGTM** (not Demo API or Docker daemon), verify API continues serving, restart LGTM and generate new fresh M/L/T cohort under bounded deadlines. No zero-loss claim for outage telemetry.
6. Validate persistence through stop/start/recreate of the **experiment-owned** LGTM container and `/data`. Define and check safe reset preview and confirmation. **Do not wipe live experiment volume or perform `reset` solely because a gate mentions it.**
7. For required isolated backup/restore, use a separate test volume/project to avoid overwriting the live experiment or the Phase 5 baseline, and require separate approval for any destructive step.
8. Record machine-readable evidence and blockers; STOP on conflicts; once WP5 passes, proceed to WP6 3-run same-Mac benchmark and WP7 independent review **only under their own approved scope**.

Explicit exclusions for WP5:
- Do not run `docker system prune`, cleanup unrelated disk, or delete the old SQL Edge container (~18.95 GB writable layer observed earlier); its database content may be unrecoverable if deleted.
- Do not infer that a reduction from 6 to 2 containers means LGTM will save disk. Image, Volume, Writable Layer and Build Cache sizes must be compared separately during WP6.
- Do not broaden to CI/CD, Jenkins, webhook, production Linux VM, PostgreSQL or HRM pilot yet.

## 9. Historical fresh-chat bootstrap (superseded by Section 0.6)

When starting a **new chat in Project mcp**:

1. Open ChatGPT → Project **mcp** → New chat.
2. Attach/refer to the **local** file `docs/handoffs/GRAFANA-OBSERVABILITY-LAB-HANDOFF.md` (or ask the assistant to read it using the connected Mac/DevBridge project).
3. Ask the assistant to inspect the actual current Git/Docker state and newest WP4 evidence **read-only first**. A chat-context summary is not sufficient proof.
4. State whether WP5 is authorized to mutate the experiment and whether a destructive reset/restore is separately approved. Do not assume authority from a handoff.
5. Ensure the assistant continues in Thai and stays focused on **Observability**, not CI/CD.

Suggested starter message:

> ทำต่อ `grafana-observability-lab` โดยอ่าน `docs/handoffs/GRAFANA-OBSERVABILITY-LAB-HANDOFF.md` บน Mac ก่อน แล้วอ่าน GitHub Execution-Ready Spec Issue #9 และ WP4 evidence bundle ล่าสุด ตรวจ Git/Containers/Volumes/Evidence แบบ Read-only และสรุปสถานะจริงของ WP1–WP4 จากนั้นเสนอ WP5 LGTM-only Recovery, Persistence, Scoped Reset และ Isolated Backup/Restore พร้อมข้อควรระวัง ก่อนเริ่มเปลี่ยน Runtime ให้รอการอนุมัติ WP5 เพิ่ม ใช้ ChatGPT เป็น executor, ไม่ใช้ Alloy, ไม่แตะ `main`/Phase 5/HRM/CI/CD, ไม่ Commit/Push/Merge/Global Cleanup และไม่ประกาศ Experiment FINAL PASS ก่อน Independent Gate

Expected acknowledgment from new chat: `OBSERVABILITY_HANDOFF_RECEIVED`, `WP4_EVIDENCE_RECONCILED` (only if independently verified in that session), and a scoped WP5 plan with explicit approval boundary.

## 10. References

- [Grafana docker-otel-lgtm official README](https://github.com/grafana/docker-otel-lgtm/blob/main/README.md): all-in-one **development/demo/testing** backend, Collector, `/data` persistence and dashboard provisioning.
- [Grafana Tempo trace-to-logs correlation](https://grafana.com/docs/grafana/latest/datasources/tempo/configure-tempo-data-source/configure-trace-to-logs/): Loki derived link + Tempo `tracesToLogsV2` both required.
- [Wayfinder Execution-Ready Spec](https://github.com/Todayblue/grafana-observability-lab/issues/9) and [Decision Map](https://github.com/Todayblue/grafana-observability-lab/issues/1) define gates/authority.

### สรุปจาก 2026-10-09 (ข้อมูลประวัติ; โปรดอ่าน Section 0 ล่าสุด)

WP0–WP3 สำเร็จและ WP3 ทดสอบซ้ำบน Mac ของผู้ใช้ผ่านทั้ง 4 Dashboards, 14 Queries และ Correlation สองทิศทาง; WP4 มี **PASS 11/11** และ Fault-Injection **29/29** พร้อม JSON/Manifest/Screenshot และตรวจ Hash ล่าสุดถูกต้อง ตัว Experiment รัน **2 Healthy Containers** ณ การตรวจล่าสุด ขณะที่ Local Source ของ WP1–WP4 ยังไม่ Commit. งานต่อไปคือ **WP5** ซึ่งจะทดลองให้ LGTM หยุดและฟื้นพร้อมตรวจข้อมูลใหม่ แต่ **ยังไม่อนุมัติให้เริ่ม WP5, ลบ Volume หรือเปลี่ยนโครงสร้าง Docker** จากคำขอสร้าง Handoff นี้ ส่วน WP6 Benchmark และ WP7 Independent Gate ยังไม่เริ่ม.
