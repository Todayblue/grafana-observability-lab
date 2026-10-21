#!/usr/bin/env python3
"""Bounded, opt-in Alloy outage test; only the named scratch Alloy container is stopped.

Reuses verify.py's backend probes. Never asserts lossless OTLP delivery.
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

import verify as smoke

ALLOY = smoke.PROJECT + "-alloy-1"
API = smoke.PROJECT + "-demo-api-1"
BUSINESS = ('sum(demo_business_operations_total'
            '{service_name="demo-api",business_outcome="failed"})')
WINDOW_SECONDS = 25


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True,
                          text=True, timeout=45).stdout.strip()


def inspect(name, service):
    record = json.loads(docker("inspect", name))[0]
    labels = record["Config"]["Labels"]
    if labels.get("com.docker.compose.project") != smoke.PROJECT or             labels.get("com.docker.compose.service") != service:
        raise RuntimeError("Container identity does not match isolated Compose service")
    return record


def trace_id():
    return os.urandom(16).hex()


def probe(path, expected, trace, canary, method=None, data=None):
    headers = {
        "traceparent": f'00-{trace}-{os.urandom(8).hex()}-01',
        "X-Employee-ID": canary,
        "X-Payroll-Amount": canary,
        "X-Synthetic-Canary": canary,
        "Authorization": "SyntheticOnly " + canary,
        "Cookie": "synthetic_session=" + canary,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    status, body = smoke.request(
        path, smoke.PORTS["api"], params={"employee_id": canary},
        headers=headers, data=data, method=method)
    if status != expected:
        raise RuntimeError(f"{path}: expected HTTP {expected}, got {status}")
    if path == "/business-failure" and json.loads(body).get("businessOutcome") != "failed":
        raise RuntimeError("Business failure lost its semantic outcome")
    if path == "/jobs/run" and json.loads(body).get("status") != "completed":
        raise RuntimeError("Synthetic job did not complete")
    return status


def optional_trace(trace):
    # smoke.request returns HTTP 404 as (status, body), not an exception.
    status, body = smoke.request("/api/traces/" + trace, smoke.PORTS["tempo"])
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError(f"Tempo trace query returned HTTP {status}")
    return json.loads(body)


def has_trace(trace):
    record = optional_trace(trace)
    return bool(record and any(
        scope.get("spans")
        for batch in record.get("batches", [])
        for scope in batch.get("scopeSpans", [])
    ))


def logs(trace, started, event):
    return smoke.logs_for_trace(trace, started, event)


def scan_privacy(canary, start, traces):
    loki = smoke.get_json("/loki/api/v1/query_range", smoke.PORTS["loki"], {
        "query": '{service_name="demo-api"}',
        "start": str(int(start * 1e9)),
        "end": str(time.time_ns()), "limit": "1000"})
    prom = smoke.get_json("/api/v1/series", smoke.PORTS["prometheus"], {
        "match[]": '{service_name="demo-api"}',
        "start": str(int(start)), "end": str(int(time.time()))})
    tempo = []
    checked_server_spans = 0
    for trace in traces:
        record = optional_trace(trace)
        if record is None:
            # Missing outage telemetry is expected to be possible.
            continue
        tempo.append(record)
        for batch in record.get("batches", []):
            for scope in batch.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    if span.get("kind") != "SPAN_KIND_SERVER":
                        continue
                    keys = {entry["key"] for entry in span.get("attributes", [])}
                    denied = {
                        "url.full", "url.query", "url.path", "http.url",
                        "http.target", "user_agent.original",
                        "http.request.header.authorization",
                        "http.request.header.cookie",
                    }
                    if keys & denied:
                        raise RuntimeError("Disallowed HTTP span attribute(s): " +
                                           ", ".join(sorted(keys & denied)))
                    if "http.route" not in keys:
                        raise RuntimeError("HTTP route template absent from server span")
                    checked_server_spans += 1

    since = datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat()
    def container_logs(name):
        result = subprocess.run(
            ["docker", "logs", "--since", since, name], check=True,
            capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr

    app_logs = container_logs(API)
    alloy_logs = container_logs(ALLOY)
    surfaces = {
        "loki": json.dumps(loki),
        "prometheus_series": json.dumps(prom),
        "tempo": json.dumps(tempo),
        "application_console": app_logs,
        "alloy_console": alloy_logs,
    }
    if checked_server_spans < 2:
        raise RuntimeError("Privacy scan did not inspect enough current HTTP server spans")
    for name, payload in surfaces.items():
        if canary in payload:
            raise RuntimeError("Synthetic canary found in " + name)
    print("PASS: synthetic identity/payroll canary absent from five inspected surfaces")
    print("PASS: HTTP spans contain route template without denied request URL/header attributes")
    return {"surfaces": sorted(surfaces), "inspected_server_spans": checked_server_spans,
            "result": "PASS"}


def run():
    smoke.check_configuration()
    smoke.check_health()
    alloy_initial = inspect(ALLOY, "alloy")
    api_initial = inspect(API, "demo-api")
    if not alloy_initial["State"]["Running"] or not api_initial["State"]["Running"]:
        raise RuntimeError("Both Alloy and optional Demo API must be running")
    started = time.time() - 3
    business_before = smoke.metric_value(BUSINESS)
    canary = "SYNTHETIC_PRIVATE_" + os.urandom(18).hex()
    trace_before = trace_id()
    probe("/ok", 200, trace_before, canary)
    smoke.until("pre-outage Trace available", lambda: has_trace(trace_before), seconds=65)
    smoke.until("pre-outage Log available",
                lambda: logs(trace_before, started, "request_completed"), seconds=65)

    outage = {
        "alloy_container": ALLOY,
        "post_recovery_observation_window_seconds": WINDOW_SECONDS,
        "requests": [],
        "api_container_id_unchanged": None,
    }
    attempted_stop = False
    outage_start = None
    try:
        attempted_stop = True
        outage_start = time.monotonic()
        docker("stop", ALLOY)
        if inspect(ALLOY, "alloy")["State"]["Running"]:
            raise RuntimeError("Alloy remained running after scoped stop")
        if not inspect(API, "demo-api")["State"]["Running"]:
            raise RuntimeError("API stopped with Alloy")
        try:
            status, _ = smoke.request("/-/ready", smoke.PORTS["alloy"])
        except OSError:
            status = 0
        if status == 200:
            raise RuntimeError("Alloy readiness remained available during outage")
        print("PASS: only scoped Alloy container stopped, API and backends still running")

        cases = [
            ("ok", "/ok", 200, None, None),
            ("business", "/business-failure", 200, None, None),
            ("job", "/jobs/run", 200, "POST",
             json.dumps({"employee_id": canary, "payroll_amount": canary}).encode()),
        ]
        for kind, path, expected, method, data in cases:
            trace = trace_id()
            code = probe(path, expected, trace, canary, method, data)
            outage["requests"].append({
                "kind": kind, "http_status": code, "trace_id": trace,
                "log_event": "background_job_completed" if kind == "job"
                             else "business_operation_completed" if kind == "business"
                             else "request_completed",
            })
        # Keep Alloy down beyond the configured 5s metric export interval.
        time.sleep(8)
        final_api = inspect(API, "demo-api")
        outage["api_container_id_unchanged"] = final_api["Id"] == api_initial["Id"]
        outage["api_started_at_unchanged"] = (final_api["State"]["StartedAt"] ==
                                                api_initial["State"]["StartedAt"])
        if not outage["api_container_id_unchanged"] or not outage["api_started_at_unchanged"]:
            raise RuntimeError("Application restarted while Collector was down")
        if smoke.request("/healthz", smoke.PORTS["api"])[0] != 200:
            raise RuntimeError("Application health failed during Alloy outage")
        if smoke.request("/-/ready", smoke.PORTS["prometheus"])[0] != 200:
            raise RuntimeError("Prometheus failed independently of Alloy")
        print("PASS: /ok, HTTP 200 business failure and awaited job still respond during Alloy outage")
    finally:
        # Even when an assertion fails, restore ONLY the previously verified Alloy.
        if attempted_stop and not inspect(ALLOY, "alloy")["State"]["Running"]:
            docker("start", ALLOY)
        if outage_start is not None:
            outage["alloy_stop_to_start_seconds"] = round(
                time.monotonic() - outage_start, 2)

    smoke.until("Alloy ready after scoped restart",
                lambda: smoke.request("/-/ready", smoke.PORTS["alloy"])[0] == 200,
                seconds=75)
    if not inspect(API, "demo-api")["State"]["Running"]:
        raise RuntimeError("API not running after Alloy restoration")
    print("PASS: Alloy restored and application remained live")

    recovered = {"ok": trace_id(), "business": trace_id()}
    probe("/ok", 200, recovered["ok"], canary)
    probe("/business-failure", 200, recovered["business"], canary)
    smoke.until("new post-recovery Trace reaches Tempo",
                lambda: has_trace(recovered["ok"]), seconds=75)
    smoke.until("new post-recovery Log reaches Loki",
                lambda: logs(recovered["ok"], started, "request_completed"), seconds=75)
    business_after = smoke.until("post-recovery Prometheus business counter advances",
                                 lambda: (v if (v := smoke.metric_value(BUSINESS)) >
                                         business_before else None), seconds=75)
    smoke.until("post-recovery business outcome log reaches Loki",
                lambda: logs(recovered["business"], started,
                             "business_operation_completed"), seconds=75)
    smoke.until("post-recovery business Trace reaches Tempo",
                lambda: has_trace(recovered["business"]), seconds=75)
    print("PASS: fresh Metrics, Logs and Traces delivered after Alloy recovery")

    # This is an observation window, never a proof of permanent data loss.
    finish = time.monotonic() + WINDOW_SECONDS
    while time.monotonic() < finish:
        found = []
        for item in outage["requests"]:
            try:
                found.append(bool(logs(item["trace_id"], started, item["log_event"])) and
                             has_trace(item["trace_id"]))
            except (urllib.error.HTTPError, OSError):
                found.append(False)
        if all(found):
            break
        time.sleep(2)

    observed = []
    for item in outage["requests"]:
        record = dict(item)
        record["log_seen_after_recovery"] = bool(logs(item["trace_id"], started,
                                                     item["log_event"]))
        record["trace_seen_after_recovery"] = has_trace(item["trace_id"])
        observed.append(record)

    privacy = scan_privacy(canary, started,
                           [trace_before, *recovered.values(),
                            *[r["trace_id"] for r in observed]])
    seen_logs = sum(x["log_seen_after_recovery"] for x in observed)
    seen_traces = sum(x["trace_seen_after_recovery"] for x in observed)
    print(f"OBSERVED: outage-window logs {seen_logs}/3, traces {seen_traces}/3 "
          "(not observed does not prove permanent loss)")
    return {
        "status": "PASS",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "alloy_outage": outage,
        "outage_telemetry_observed_after_restore": observed,
        "outage_logs_seen": seen_logs,
        "outage_traces_seen": seen_traces,
        "outage_metric_caveat": "Cumulative Prometheus counts cannot identify individual requests.",
        "business_metric_before": business_before,
        "business_metric_after_recovery": business_after,
        "fresh_post_recovery_logs_and_traces": "PASS",
        "privacy": privacy,
        "loss_claim": "Bounded visibility only. Missing records are not proven permanently lost.",
    }


def main():
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and not sys.argv[1].startswith("/")):
        raise SystemExit("Usage: ./scripts/verify.sh --reliability [ABSOLUTE_EVIDENCE_DIR]")
    base = (pathlib.Path(sys.argv[1]) if len(sys.argv) == 2 else
            pathlib.Path.home() / "Library/Application Support/GrafanaObservabilityLab/evidence" /
            ("alloy-reliability-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S")))
    base.mkdir(parents=True, exist_ok=True)
    try:
        output = run()
        code = 0
        print("RELIABILITY_VERDICT=PASS")
    except Exception as exc:
        output = {"status": "FAIL",
                  "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "error": repr(exc)}
        code = 1
        print("RELIABILITY_VERDICT=FAIL", repr(exc), file=sys.stderr)
    path = base / "reliability.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print("EVIDENCE", path)
    return code


if __name__ == "__main__":
    sys.exit(main())
