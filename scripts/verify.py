#!/usr/bin/env python3
"""OTLP-native Alloy smoke verification of the local reference stack.

Requires Python 3 standard library only. Generates synthetic requests and records
only safe verification evidence, never request bodies or credentials.
"""
import base64
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORTS = {"api": 18085, "alloy": 12355, "prometheus": 19095,
         "loki": 13105, "tempo": 13205, "grafana": 13305}
PROJECT = "grafana-alloy-observability"
TIMEOUT = 90

def request(path, port, params=None, headers=None, method=None, data=None):
    url = "http://127.0.0.1:" + str(port) + path
    if params is not None:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {}, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()

def get_json(path, port, params=None):
    status, body = request(path, port, params)
    if status != 200:
        raise RuntimeError(f"HTTP {status} from {port}{path}: {body[:220]!r}")
    return json.loads(body)

def until(message, fn, seconds=TIMEOUT):
    end = time.monotonic() + seconds
    latest = None
    while time.monotonic() < end:
        try:
            result = fn()
            if result:
                print("PASS:", message, flush=True)
                return result
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            latest = str(exc)
        time.sleep(2)
    raise RuntimeError(message + " did not verify" + (": " + latest if latest else ""))

def metric_value(expr=None):
    if expr is None:
        expr = ('sum(http_server_request_duration_seconds_count'
                '{service_name="demo-api",http_route="/error",'
                'http_response_status_code="500"})')
    payload = get_json("/api/v1/query", PORTS["prometheus"], {"query": expr})
    assert payload["status"] == "success"
    result = payload["data"]["result"]
    return float(result[0]["value"][1]) if result else 0.0

def logs_for_trace(trace_id, start, event_name="request_completed"):
    expr = ('{service_name="demo-api",deployment_environment_name="lab"}'
            f' | trace_id="{trace_id}" | event_name="{event_name}"')
    payload = get_json("/loki/api/v1/query_range", PORTS["loki"],
                       {"query": expr, "start": str(int(start * 1e9)),
                        "end": str(time.time_ns()), "limit": "100"})
    assert payload["status"] == "success"
    return [(stream["stream"], value) for stream in payload["data"]["result"]
            for value in stream["values"]]

def span_set(trace_id):
    payload = get_json("/api/traces/" + trace_id, PORTS["tempo"])
    result = []
    for batch in payload.get("batches", []):
        for scope in batch.get("scopeSpans", []):
            result.extend(scope.get("spans", []))
    if not result:
        return None
    for span in result:
        if base64.b64decode(span["traceId"]).hex() != trace_id:
            raise RuntimeError("TraceId mismatch inside Tempo")
    return result

def attr(span, name):
    for item in span.get("attributes", []):
        if item["key"] == name:
            return next(iter(item["value"].values()))
    return None

def check_configuration():
    config = (ROOT / "alloy/config.alloy").read_text()
    for token in ('otelcol.receiver.otlp "application"',
                  'otelcol.exporter.prometheus "application"',
                  'otelcol.exporter.otlphttp "loki"',
                  'otelcol.exporter.otlp "tempo"'):
        if token not in config:
            raise RuntimeError("Missing Alloy OTLP component " + token)
    for token in ('loki.source.docker', 'prometheus.scrape "demo_api"', 'discovery.docker'):
        if token in config:
            raise RuntimeError("Duplicate-application-ingest component " + token)
    mounts = json.loads(subprocess.check_output([
        "docker", "inspect", PROJECT + "-alloy-1"], text=True))[0]["Mounts"]
    if any("docker.sock" in mount.get("Source", "") for mount in mounts):
        raise RuntimeError("Alloy must not mount Docker socket for OTLP app logs")
    print("PASS: OTLP-only application ingestion and no Docker socket", flush=True)

def check_health():
    for name, route in [("api", "/healthz"), ("alloy", "/-/ready"),
                        ("prometheus", "/-/ready"), ("loki", "/ready"),
                        ("tempo", "/ready"), ("grafana", "/api/health")]:
        def healthy():
            status, _ = request(route, PORTS[name])
            return status == 200
        until(f"{name} ready", healthy, seconds=65)
    grafana = get_json("/api/health", PORTS["grafana"])
    if grafana.get("version") != "13.2.4" or grafana.get("database") != "ok":
        raise RuntimeError("Grafana version/database not as expected: " + str(grafana))
    print("PASS: Grafana OSS 13.2.4 and database ready", flush=True)

def check_loki_cardinality(start):
    payload = get_json("/loki/api/v1/series", PORTS["loki"],
                       {"match[]": '{service_name="demo-api"}',
                        "start": str(int(start * 1e9)),
                        "end": str(time.time_ns())})
    series = payload.get("data", [])
    if not series:
        raise RuntimeError("Loki has no indexed demo-api series")
    for labels in series:
        for key in ("trace_id", "span_id", "service_instance_id", "http_route"):
            if key in labels:
                raise RuntimeError(f"High-cardinality indexed label {key}")
    print("PASS: low-cardinality Loki indexed labels", flush=True)
    return series

def run():
    check_configuration()
    check_health()
    baseline = metric_value()
    traces = {route: os.urandom(16).hex() for route in ("/ok", "/slow", "/error")}
    since = time.time() - 2
    for route, expected in (("/ok", 200), ("/slow", 200), ("/error", 500)):
        trace_id = traces[route]
        hdr = {"traceparent": f"00-{trace_id}-{os.urandom(8).hex()}-01"}
        status, _ = request(route, PORTS["api"], headers=hdr)
        if status != expected:
            raise RuntimeError(f"{route}: expected HTTP {expected}; got {status}")
        print("PASS: request", route, expected, flush=True)
    metric_after = until("Prometheus HTTP 500 OTLP metric increment",
                         lambda: (n if (n := metric_value()) > baseline else None),
                         seconds=75)
    error_trace = traces["/error"]
    def log_match():
        logs = logs_for_trace(error_trace, since)
        return logs if logs else None
    logs = until("Loki correlated /error log", log_match)
    if len(logs) != 1:
        raise RuntimeError(f"Expected exactly 1 request_completed log; got {len(logs)}")
    metadata, entry = logs[0]
    for key, value in (("event_name", "request_completed"), ("http_route", "/error"),
                       ("http_response_status_code", "500"), ("severity_text", "Error")):
        if metadata.get(key) != value:
            raise RuntimeError(f"Loki metadata {key} does not match: {metadata.get(key)}")
    if metadata.get("trace_id") != error_trace or "request_completed" not in entry[1]:
        raise RuntimeError("Loki Body/Trace ID mismatch")
    if "http_route=/error" not in entry[1]:
        raise RuntimeError("Loki LogRecord body is not formatted")
    print("PASS: single nonduplicated readable /error log and structured fields", flush=True)
    def trace_match():
        spans = span_set(error_trace)
        return spans if spans else None
    spans = until("Tempo exact Trace ID", trace_match)
    if not any(sp.get("kind") == "SPAN_KIND_SERVER" and
               attr(sp, "http.route") == "/error" and
               str(attr(sp, "http.response.status_code")) == "500"
               for sp in spans):
        raise RuntimeError("Tempo /error HTTP server span/status missing")
    print("PASS: Log Trace ID joins exact HTTP 500 Tempo trace", flush=True)
    slow_spans = until("Tempo /slow trace with child spans",
                       lambda: span_set(traces["/slow"]))
    child_names = {"ValidateRequest", "SimulatedWork", "BuildResponse"}
    if not child_names.issubset({sp.get("name") for sp in slow_spans}):
        raise RuntimeError("Custom child spans missing from /slow trace")
    print("PASS: /slow custom child spans", flush=True)
    # HRM-like business failure and awaited worker operation; no external jobs.
    business_expr = ('sum(demo_business_operations_total'
                     '{service_name="demo-api",business_outcome="failed"})')
    business_http_200 = ('sum(http_server_request_duration_seconds_count'
                         '{service_name="demo-api",http_route="/business-failure",'
                         'http_response_status_code="200"})')
    business_http_500 = ('sum(http_server_request_duration_seconds_count'
                         '{service_name="demo-api",http_route="/business-failure",'
                         'http_response_status_code="500"})')
    business_before = metric_value(business_expr)
    http_200_before = metric_value(business_http_200)
    http_500_before = metric_value(business_http_500)
    probe_start = time.time() - 2
    # Synthetic values only: none of these should appear in telemetry.
    canary = "SYNTHETIC_PRIVATE_" + os.urandom(16).hex()
    probe_traces = {name: os.urandom(16).hex() for name in ("business", "job")}

    def probe_headers(name):
        return {
            "traceparent": f'00-{probe_traces[name]}-{os.urandom(8).hex()}-01',
            "X-Synthetic-Canary": canary,
        }

    business_status, business_body = request(
        "/business-failure", PORTS["api"],
        params={"employee_id": canary}, headers=probe_headers("business"))
    if business_status != 200 or json.loads(business_body).get("businessOutcome") != "failed":
        raise RuntimeError("Synthetic business failure must be HTTP 200 with failed outcome")
    print("PASS: business failure returns HTTP 200 and failed outcome", flush=True)

    job_status, job_body = request(
        "/jobs/run", PORTS["api"], method="POST",
        params={"employee_id": canary},
        data=json.dumps({"employee_id": canary, "payroll_amount": canary}).encode(),
        headers={**probe_headers("job"), "Content-Type": "application/json"})
    if job_status != 200 or json.loads(job_body).get("status") != "completed":
        raise RuntimeError("Synthetic job trigger did not complete successfully")
    print("PASS: deterministic manually triggered ThreadPool job", flush=True)

    business_after = until("distinct OTel business failure metric",
                           lambda: (n if (n := metric_value(business_expr)) > business_before else None))
    until("business failure counted as HTTP 200",
          lambda: metric_value(business_http_200) > http_200_before)
    if metric_value(business_http_500) != http_500_before:
        raise RuntimeError("HTTP 200 business failure must not increment HTTP 5xx")
    print("PASS: business failure distinguished from HTTP 5xx", flush=True)

    business_logs = until("Loki business event with exact Trace ID",
                          lambda: logs_for_trace(probe_traces["business"], probe_start,
                                                 "business_operation_completed"))
    job_logs = until("Loki background-job event with exact Trace ID",
                     lambda: logs_for_trace(probe_traces["job"], probe_start,
                                            "background_job_completed"))
    if len(business_logs) != 1 or business_logs[0][0].get("business_outcome") != "failed":
        raise RuntimeError("Business log missing structured failed outcome or duplicated")
    if len(job_logs) != 1 or job_logs[0][0].get("job_outcome") != "completed":
        raise RuntimeError("Job log missing structured completed outcome or duplicated")
    business_spans = until("Tempo synthetic business span",
                           lambda: span_set(probe_traces["business"]))
    job_spans = until("Tempo synthetic background-job span",
                      lambda: span_set(probe_traces["job"]))
    if not any(sp.get("name") == "SyntheticBusinessOperation" and
               attr(sp, "business.outcome") == "failed" for sp in business_spans):
        raise RuntimeError("Business span/outcome missing from exact Tempo trace")
    if not any(sp.get("name") == "SyntheticBackgroundJob" and
               attr(sp, "job.kind") == "synthetic" for sp in job_spans):
        raise RuntimeError("Background-job span missing from exact Tempo trace")
    print("PASS: both synthetic events correlated in Loki and Tempo", flush=True)

    # Search the outputs, but NEVER record or print the synthetic secret itself.
    log_data = get_json("/loki/api/v1/query_range", PORTS["loki"], {
        "query": '{service_name="demo-api"}',
        "start": str(int(probe_start * 1e9)),
        "end": str(time.time_ns()), "limit": "1000"})
    if log_data["status"] != "success":
        raise RuntimeError("Loki privacy scan query failed")
    label_data = get_json("/api/v1/series", PORTS["prometheus"], {
        "match[]": '{service_name="demo-api"}',
        "start": str(int(probe_start)), "end": str(int(time.time()))})
    if label_data["status"] != "success":
        raise RuntimeError("Prometheus privacy scan failed")
    trace_data = [
        get_json("/api/traces/" + trace_id, PORTS["tempo"])
        for trace_id in probe_traces.values()
    ]
    for trace in trace_data:
        for batch in trace.get("batches", []):
            for scope in batch.get("scopeSpans", []):
                for sp in scope.get("spans", []):
                    if sp.get("kind") != "SPAN_KIND_SERVER":
                        continue
                    attribute_keys = {a["key"] for a in sp.get("attributes", [])}
                    disallowed = {"url.query", "url.path", "user_agent.original"} & attribute_keys
                    if disallowed:
                        raise RuntimeError("Disallowed HTTP span attributes: " +
                                           ", ".join(sorted(disallowed)))
                    if "http.route" not in attribute_keys:
                        raise RuntimeError("Safe route template must remain in HTTP span")
    console_data = subprocess.run(
        ["docker", "logs", "--since",
         datetime.datetime.fromtimestamp(probe_start, datetime.timezone.utc).isoformat(),
         PROJECT + "-demo-api-1"], check=True, capture_output=True, text=True)
    leak_sources = {
        "loki": json.dumps(log_data),
        "prometheus_series": json.dumps(label_data),
        "tempo": json.dumps(trace_data),
        "console_stdout": console_data.stdout + console_data.stderr,
    }
    for source, payload in leak_sources.items():
        if canary in payload:
            raise RuntimeError("Synthetic sensitive canary leaked to " + source)
    print("PASS: synthetic private query/header/body canary absent from four telemetry surfaces",
          flush=True)
    label_series = check_loki_cardinality(since)
    return {
        "status": "PASS",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_branch_expected": "experiment/otel-alloy-separated-backends",
        "compose_project": PROJECT,
        "grafana_version": "13.2.4",
        "trace_ids": traces,
        "request_statuses": {"/ok": 200, "/slow": 200, "/error": 500},
        "metric_name": "http_server_request_duration_seconds_count",
        "http_500_metric_before": baseline,
        "http_500_metric_after": metric_after,
        "loki_error_logs_count": len(logs),
        "loki_indexed_series": label_series,
        "tempo_error_span_count": len(spans),
        "tempo_slow_span_names": sorted({sp.get("name") for sp in slow_spans}),
        "docker_socket_mount": False,
        "duplicate_request_completed": False,
        "business_http_status": business_status,
        "business_outcome": "failed",
        "business_metric": "demo_business_operations_total",
        "business_metric_before": business_before,
        "business_metric_after": business_after,
        "business_http_500_unchanged": True,
        "background_job_http_status": job_status,
        "business_event_log_count": len(business_logs),
        "background_event_log_count": len(job_logs),
        "business_trace_id": probe_traces["business"],
        "job_trace_id": probe_traces["job"],
        "synthetic_privacy_probe": {
            "sentinel_injected": True,
            "channels_checked": sorted(leak_sources),
            "result": "PASS",
        },
    }

def main():
    args = sys.argv[1:]
    if len(args) > 1 or (args and not args[0].startswith("/")):
        raise SystemExit("Usage: verify.py [ABSOLUTE_EVIDENCE_DIRECTORY]")
    evidence = (pathlib.Path(args[0]) if args else
                pathlib.Path.home() / "Library/Application Support/GrafanaObservabilityLab/evidence" /
                ("alloy-reference-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S")))
    evidence.mkdir(parents=True, exist_ok=True)
    output = evidence / "verification.json"
    try:
        result = run()
        print("VERIFICATION_VERDICT=PASS", flush=True)
        code = 0
    except Exception as exc:
        result = {"status": "FAIL", "error": repr(exc),
                  "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        print("VERIFICATION_VERDICT=FAIL", repr(exc), file=sys.stderr, flush=True)
        code = 1
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("EVIDENCE", output, flush=True)
    return code

if __name__ == "__main__":
    sys.exit(main())
