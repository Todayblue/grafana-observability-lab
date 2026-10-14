#!/usr/bin/env python3
"""Focused WP2 OTLP smoke checks. WP3 UI and WP4 full gates are separate."""
import base64
import concurrent.futures
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONTAINER = "grafana-otel-lgtm-lab-lgtm-1"
API = "http://127.0.0.1:8082"
SECRET_PREFIX = "WP2_SYNTHETIC_NOT_REAL_"
EXPECTED = (("/ok", 200, "Information"), ("/slow", 200, "Information"),
            ("/error", 500, "Error"))
RUN_START = time.time()


def backend(port, path, params=(), allow_404=False):
    command = ["docker", "exec", CONTAINER, "curl", "-sS", "--max-time", "10",
               "-H", "Accept: application/json", "-G"]
    for key, value in params:
        command.extend(["--data-urlencode", f"{key}={value}"])
    command += ["-w", "\\n%{http_code}", f"http://127.0.0.1:{port}{path}"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=17)
    if result.returncode:
        raise RuntimeError(f"Backend port {port} unreachable: {result.stderr[:100]}")
    body, sep, status = result.stdout.rpartition("\n")
    if not sep:
        raise RuntimeError(f"Invalid HTTP response from backend {port}")
    if status.strip() == "404" and allow_404:
        return None
    if status.strip() != "200":
        raise RuntimeError(f"Backend {port} query failed: HTTP {status.strip()}")
    return json.loads(body)


def promql(expression):
    data = backend(9090, "/api/v1/query", (("query", expression),))
    if data.get("status") != "success":
        raise AssertionError("Prometheus query failed")
    values = data["data"]["result"]
    return sum(float(v["value"][1]) for v in values)


def request(path, method="GET", extra_headers=True):
    trace_id, parent = secrets.token_hex(16), secrets.token_hex(8)
    secret = SECRET_PREFIX + secrets.token_hex(10)
    headers = {"traceparent": f"00-{trace_id}-{parent}-01"}
    if extra_headers:
        headers.update({
            "Authorization": "Bearer " + secret,
            "Cookie": "session=" + secret,
            "User-Agent": "wp2/" + secret,
            "baggage": "probe=" + secret
        })
    url = API + path + ("?synthetic_token=" + secret if extra_headers else "")
    req = urllib.request.Request(url, headers=headers,
                                 data=(secret.encode() if method == "POST" else None),
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        error.read()
    return {"path": path, "trace_id": trace_id, "status": status, "secret": secret}


def query_logs(trace_id):
    response = backend(3100, "/loki/api/v1/query_range", (
        ("query", '{service_name="demo-api"} | trace_id="' + trace_id + '"'),
        ("start", str(int(RUN_START - 10) * 1000000000)),
        ("limit", "100")))
    return [(item["stream"], event[1]) for item in response["data"]["result"]
            for event in item["values"]]


def trace(trace_id):
    return backend(3200, "/api/traces/" + trace_id, allow_404=True)


def spans_and_resource(record):
    spans, resources = [], []
    for batch in record.get("batches", record.get("resourceSpans", [])):
        resource = {a["key"]: next(iter(a.get("value", {}).values()), "")
                    for a in batch.get("resource", {}).get("attributes", [])}
        resources.append(resource)
        for scope in batch.get("scopeSpans", batch.get("instrumentationLibrarySpans", [])):
            spans += scope.get("spans", [])
    return spans, resources


def wait_for(label, condition, timeout=55):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = condition()
            if value:
                return value
        except (RuntimeError, ValueError, KeyError) as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f"{label}: no current-run evidence before deadline ({last or 'missing'})")


def run():
    health = urllib.request.urlopen(API + "/healthz", timeout=5)
    assert health.status == 200
    # Cumulative OTLP series can reset when the API container is recreated.
    # First prove Prometheus has a sample from this running process before
    # taking the baseline. A historical count is never a fresh baseline.
    warmup_started = time.time()
    for route, expected_http, _ in EXPECTED:
        assert request(route, extra_headers=False)["status"] == expected_http
    wait_for("current-process metric baselines", lambda: all(
        promql('max(timestamp(http_server_request_duration_seconds_count'
               '{service_name="demo-api",http_route="' + route +
               '",http_response_status_code="' + str(status) + '"}))') >= warmup_started
        for route, status, _ in EXPECTED))
    before = {
        route: promql('sum(http_server_request_duration_seconds_count'
                      '{service_name="demo-api",http_route="' + route +
                      '",http_response_status_code="' + str(status) + '"})')
        for route, status, _ in EXPECTED
    }
    probes = [request(route) for route, _, _ in EXPECTED]
    warning = request("/error", method="POST")
    health_probe = request("/healthz")
    not_found = request("/unmapped_" + secrets.token_hex(5))
    expected = {route: (status, severity) for route, status, severity in EXPECTED}
    for p in probes:
        assert p["status"] == expected[p["path"]][0], "Unexpected demo HTTP status"
    assert warning["status"] == 405
    assert health_probe["status"] == 200 and not_found["status"] == 404

    wait_for("fresh http metrics", lambda: all(
        promql('sum(http_server_request_duration_seconds_count'
               '{service_name="demo-api",http_route="' + route +
               '",http_response_status_code="' + str(status) + '"})') >= before[route] + 1
        for route, status, _ in EXPECTED))
    assert promql('count({__name__=~"demo_http_.*"})') == 0, "Legacy metrics are still ingested"
    bucket_names = backend(9090, "/api/v1/query", ((
        "query", 'http_server_request_duration_seconds_bucket{http_route="/slow"}'),))
    assert any(row["metric"].get("le") == "1.5"
               for row in bucket_names["data"]["result"]), "Missing explicit 1.5-second bucket"

    all_payloads = []
    for p in probes + [warning]:
        matching_logs = wait_for("fresh log " + p["path"],
                                 lambda p=p: query_logs(p["trace_id"]))
        assert len(matching_logs) == 1, "Missing/duplicate logical request_completed log"
        attrs, body = matching_logs[0]
        assert attrs["event_name"] == "request_completed", "Event name missing"
        assert attrs["http_route"] == p["path"]
        assert int(attrs["http_response_status_code"]) == p["status"]
        assert float(attrs["duration_ms"]) >= 0
        assert len(attrs["span_id"]) == 16
        assert attrs["service_version"] == "0.1.0-wp2"
        if p in probes:
            assert attrs["severity_text"] == expected[p["path"]][1]
        else:
            assert attrs["severity_text"] == "Warning", "4xx severity must be Warning"
        assert body.startswith("request_completed")
        t = wait_for("fresh trace " + p["path"], lambda p=p: trace(p["trace_id"]))
        spans, resources = spans_and_resource(t)
        assert any(resource.get("service.name") == "demo-api" and
                   resource.get("service.version") == "0.1.0-wp2" and
                   resource.get("deployment.environment.name") == "lab"
                   for resource in resources)
        assert all(base64.b64decode(span["traceId"]).hex() == p["trace_id"]
                   for span in spans), "Trace context was not propagated"
        span_ids = {base64.b64decode(span["spanId"]).hex() for span in spans}
        assert attrs["span_id"] in span_ids, "Log span was not in the same trace"
        if p["path"] == "/slow":
            assert {"ValidateRequest", "SimulatedWork", "BuildResponse"}.issubset(
                {span["name"] for span in spans}), "Missing /slow child span"
        if p["status"] == 405:
            assert not any(span.get("status", {}).get("code") == "STATUS_CODE_ERROR"
                           for span in spans), "HTTP server 4xx incorrectly marked Error"
        if p["path"] == "/error" and p["status"] == 500:
            assert any(span.get("status", {}).get("code") == "STATUS_CODE_ERROR"
                       for span in spans), "HTTP 500 did not mark the trace as Error"
            assert not any(span.get("events") for span in spans), "Fabricated exception event"
        all_payloads += [json.dumps(matching_logs), json.dumps(t)]
        print(f"PASS request {p['path']} http={p['status']} trace_id={p['trace_id']}")

    series = backend(3100, "/loki/api/v1/series", (
        ("match[]", '{service_name="demo-api"}'),
        ("start", str(int(RUN_START - 10) * 1000000000))))
    assert series["data"], "No matching Loki streams"
    assert all(set(s).issubset({"service_name", "deployment_environment_name"})
               for s in series["data"]), "Trace or request fields became indexed labels"

    assert query_logs(secrets.token_hex(16)) == [], "Random trace ID unexpectedly matched"
    assert trace(health_probe["trace_id"]) is None, "Health probe produced a demo trace"
    assert trace(not_found["trace_id"]) is None, "Unknown route produced a demo trace"

    console = subprocess.run(["docker", "logs", "grafana-otel-lgtm-lab-demo-api-1"],
                             capture_output=True, text=True, timeout=10)
    assert console.returncode == 0
    payload = console.stdout + console.stderr + "\n".join(all_payloads)
    assert all(p["secret"] not in payload for p in probes + [warning, health_probe, not_found]), (
        "Synthetic secrets leaked into Console, Loki or Tempo")
    print("PASS strict privacy, no duplicate ingestion, health-route exclusion, minimal Loki labels")

    # Keep several /slow requests in flight across the 5s metrics export tick.
    def load():
        end = time.monotonic() + 11
        while time.monotonic() < end:
            urllib.request.urlopen(API + "/slow", timeout=6).read()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(load) for _ in range(8)]
        active = wait_for("in-progress requests",
                          lambda: promql('sum(http_server_active_requests{service_name="demo-api"})') > 0,
                          timeout=13)
        for job in jobs:
            job.result(timeout=20)
    assert active
    print("PASS active HTTP gauge observed >0 during concurrent /slow workload")
    print(json.dumps({"result": "PASS", "scope": "WP2 only", "signals": ["metrics", "logs", "traces"],
                      "log_index_labels": sorted(set().union(*(set(s) for s in series["data"]))),
                      "negative_privacy": "PASS", "source": "fresh W3C traceparent probes"}))


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"FAIL WP2: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
