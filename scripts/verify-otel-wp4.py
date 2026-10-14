#!/usr/bin/env python3
"""WP4 deterministic E2E, fail-closed fault tests and sanitized JSON evidence.

Operates only on the already running local grafana-otel-lgtm-lab project.
Does not change Compose, Docker container lifecycle, Git or backend data.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

from otel_wp4_checks import (
    assert_index_labels, assert_log, assert_metric_delta,
    assert_no_secrets, assert_no_trace, assert_trace, require,
)

ROOT = Path(__file__).resolve().parent.parent
SERVICE = "demo-api"
PROJECT = "grafana-otel-lgtm-lab"
LGTM = PROJECT + "-lgtm-1"
DEMO = PROJECT + "-demo-api-1"
API = "http://127.0.0.1:8082"
EXPECT = [("/ok", "GET", 200, "Information"),
          ("/slow", "GET", 200, "Information"),
          ("/error", "GET", 500, "Error"),
          ("/error", "POST", 405, "Warning")]
IMAGE_DIGEST = "sha256:b966ea107831d526d9eb8fe4d2d86c9e5731392fad9dce8296bcf2072031f07c"


def utc(ts=None):
    return datetime.fromtimestamp(time.time() if ts is None else ts,
                                  timezone.utc).isoformat().replace("+00:00", "Z")


def shell(args, timeout=18):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("read-only command failed: " + args[0] +
                           " (exit " + str(result.returncode) + ")")
    return result.stdout.strip()


def http_backend(port, path, params=(), allow_404=False):
    args = ["docker", "exec", LGTM, "curl", "--silent", "--show-error",
            "--max-time", "10", "--get"]
    for key, value in params:
        args += ["--data-urlencode", key + "=" + str(value)]
    args += ["--write-out", "\\n%{http_code}",
             "http://127.0.0.1:" + str(port) + path]
    raw = subprocess.run(args, capture_output=True, text=True, timeout=17)
    if raw.returncode:
        raise RuntimeError("backend curl failed on port " + str(port))
    # Do not strip: a 404 with an empty body starts with a newline.
    body, sep, status = raw.stdout.rpartition("\n")
    status = status.strip()
    if not sep:
        raise RuntimeError("backend returned no HTTP status")
    if status == "404" and allow_404:
        return None
    if status != "200":
        raise RuntimeError("backend HTTP " + status + " port " + str(port))
    try:
        return json.loads(body)
    except ValueError:
        raise RuntimeError("backend response was not JSON") from None


def prom_sample(route, status):
    expr = ('sum(http_server_request_duration_seconds_count'
            '{service_name="demo-api",http_route="' + route +
            '",http_response_status_code="' + str(status) + '"})')
    data = http_backend(9090, "/api/v1/query", (("query", expr),))
    require(data.get("status") == "success", "Prometheus query failed")
    rows = data["data"]["result"]
    if not rows:
        return None
    require(len(rows) == 1, "Prometheus aggregate returned duplicate vectors")
    return {"ts": float(rows[0]["value"][0]),
            "value": float(rows[0]["value"][1])}


def loki_rows(trace_id, since):
    expr = '{service_name="demo-api"} | trace_id="' + trace_id + '"'
    data = http_backend(3100, "/loki/api/v1/query_range", (
        ("query", expr), ("start", str(int((since - 3) * 1e9))),
        ("end", str(int((time.time() + 5) * 1e9))), ("limit", "100")))
    require(data.get("status") == "success", "Loki query failed")
    items = []
    for stream in data["data"]["result"]:
        for row in stream["values"]:
            attrs = dict(stream["stream"])
            if len(row) > 2 and isinstance(row[2], dict):
                attrs.update(row[2])
            items.append((row[0], row[1], attrs))
    return items


def tempo_trace(trace_id):
    return http_backend(3200, "/api/traces/" + trace_id, allow_404=True)


def request_probe(route, method="GET", sensitive=False):
    started = time.time()
    trace_id = secrets.token_hex(16)
    parent_id = secrets.token_hex(8)
    # Fake secrets are intentionally synthetic; never write them to evidence.
    marker = "WP4_FAKE_ONLY_" + secrets.token_hex(14)
    headers = {"traceparent": "00-" + trace_id + "-" + parent_id + "-01"}
    if sensitive:
        headers.update({
            "Authorization": "Bearer " + marker,
            "Cookie": "session=" + marker,
            "User-Agent": "WP4/" + marker,
            "X-Probe-Email": marker + "@example.invalid",
            "baggage": "sensitive=" + marker,
        })
    address = API + route
    if sensitive:
        address += "?" + urllib.parse.urlencode({"synthetic_probe": marker})
    payload = (marker + "@example.invalid").encode() if method == "POST" else None
    req = urllib.request.Request(address, headers=headers,
                                 data=payload, method=method)
    try:
        with urllib.request.urlopen(req, timeout=9) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        error.read()
    return {"route": route, "method": method, "status": status,
            "started": started, "finished": time.time(),
            "trace_id": trace_id, "parent_id": parent_id,
            "_marker": marker if sensitive else None}


def poll(name, attempts, interval, deadline, assertion):
    start = time.monotonic()
    failures = []
    count = 0
    while True:
        count += 1
        try:
            result = assertion()
            attempts[name] = {"status": "PASS", "attempts": count,
                              "elapsed_seconds": round(time.monotonic() - start, 2),
                              "deadline_seconds": deadline}
            return result
        except (AssertionError, RuntimeError, ValueError, KeyError,
                subprocess.TimeoutExpired) as error:
            failures.append(type(error).__name__ + ": " + str(error))
        elapsed = time.monotonic() - start
        if elapsed >= deadline:
            attempts[name] = {"status": "FAIL", "attempts": count,
                              "elapsed_seconds": round(elapsed, 2),
                              "deadline_seconds": deadline,
                              "last_error": failures[-1][:180]}
            raise AssertionError(name + " failed by bounded deadline: " +
                                 failures[-1][:160])
        time.sleep(min(interval, max(0, deadline - elapsed)))


def run_fixture_tests():
    cmd = [sys.executable, "-B", "-m", "unittest", "discover",
           "-s", str(ROOT / "scripts"), "-p", "test_otel_wp4_checks.py", "-v"]
    outcome = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    result = outcome.stdout + outcome.stderr
    match = re.search(r"Ran (\d+) tests", result)
    count = int(match.group(1)) if match else 0
    test_ids = [line.split(" ", 1)[0] for line in result.splitlines()
                if line.startswith("test_") and line.rstrip().endswith(" ... ok")]
    # Names are extracted from unittest verbose PASS lines, not test summaries.
    require(outcome.returncode == 0 and count >= 20 and
            len(test_ids) == count and len(set(test_ids)) == count,
            "fail-closed fault-injection fixture suite failed")
    return {"status": "PASS", "mode": "controlled_fixture_fault_injection",
            "cases": count,
            "assertions": [{"id": name, "status": "PASS"} for name in test_ids],
            "note": "Mutations exercise the same validators as live; "
                    "no faults were injected into running services"}


def host_preflight():
    branch = shell(["git", "-C", str(ROOT), "branch", "--show-current"])
    require(branch == "experiment/otel-lgtm", "wrong Git branch")
    head = shell(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    staged = shell(["git", "-C", str(ROOT), "diff", "--cached", "--name-only"])
    require(not staged, "staged changes not allowed during WP4")
    project = shell(["docker", "compose", "-p", PROJECT, "-f",
                     str(ROOT / "compose.otel-lgtm.yaml"),
                     "ps", "--services", "--status", "running"])
    require(set(project.splitlines()) == {"lgtm", "demo-api"},
            "expected precisely 2 running experiment services")
    app_env = shell(["docker", "inspect", DEMO, "--format",
                     "{{json .Config.Env}}"])
    version = next((s.partition("=")[2] for s in json.loads(app_env)
                    if s.startswith("OTEL_SERVICE_VERSION=")), None)
    require(bool(version), "Demo API app version not configured")
    image = shell(["docker", "inspect", LGTM,
                   "--format", "{{.Config.Image}}"])
    require(IMAGE_DIGEST in image, "LGTM image is not the verified digest")
    # HEAD alone does not identify this uncommitted experiment worktree.
    source_rel = [
        "README.otel-lgtm.md", "compose.otel-lgtm.yaml",
        "demo-api/Program.cs", "demo-api/SafeDemoSpanProcessor.cs",
        "demo-api/demo-api.csproj", "scripts/otel-lgtm.sh",
        "scripts/otel_wp4_checks.py", "scripts/test_otel_wp4_checks.py",
        "scripts/verify-otel-wp2.py", "scripts/verify-otel-wp3.py",
        "scripts/verify-otel-wp3-ui.cjs", "scripts/verify-otel-wp4.py",
    ]
    source_rel += [str(p.relative_to(ROOT)) for p in sorted(
        (ROOT / "grafana/otel-lgtm").rglob("*")) if p.is_file()]
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in source_rel}
    dirty = bool(shell(["git", "-C", str(ROOT), "status", "--porcelain"]))
    return {"branch": branch, "git_head": head, "app_version": version,
            "lgtm_image_ref": image, "lgtm_digest": IMAGE_DIGEST,
            "compose_project": PROJECT, "worktree_has_changes": dirty,
            "source_file_sha256": hashes}


def log_and_trace(probes, now, deadline, interval, attempts, version):
    def logs_check():
        output = []
        for probe in probes:
            rows = loki_rows(probe["trace_id"], now)
            probe["_log_span"] = assert_log(rows, probe, version)
            output.extend(rows)
        return output
    logs = poll("logs", attempts, interval, deadline, logs_check)

    def traces_check():
        output = []
        for probe in probes:
            tree = tempo_trace(probe["trace_id"])
            assert_trace(tree, probe, probe["_log_span"], version)
            output.append(tree)
        return output
    traces = poll("traces", attempts, interval, deadline, traces_check)
    return logs, traces


def metric_check(before, probes, deadline, interval, attempts):
    def evaluate():
        after = {}
        for route, method, status, _ in (x for x in EXPECT if x[1] == "GET"):
            key = method + " " + route + ":" + str(status)
            after[key] = prom_sample(route, status)
            match = next(p for p in probes if p["route"] == route and
                         p["method"] == method and p["status"] == status)
            assert_metric_delta(before[key], after[key], match["finished"])
        return after
    return poll("metrics", attempts, interval, deadline, evaluate)


def verify_no_sensitive_values(probes, logs, traces, started):
    markers = [probe["_marker"] for probe in probes if probe["_marker"]]
    stamp = utc(started)
    console = shell(["docker", "logs", "--since", stamp, DEMO], timeout=15)
    assert_no_secrets(markers, console, logs, traces)
    return len(markers)


def check_index_series(started):
    response = http_backend(3100, "/loki/api/v1/series", (
        ("match[]", '{service_name="demo-api"}'),
        ("start", str(int((started - 3) * 1e9))),))
    require(response.get("status") == "success", "Loki series request failed")
    assert_index_labels(response["data"])
    return sorted({k for series in response["data"] for k in series})


def check_absence(excluded, delay):
    # This is a bounded negative window after successful positive trace ingest.
    # It cannot claim absence for all future time.
    end = time.monotonic() + delay
    while time.monotonic() < end:
        for probe in excluded:
            assert_no_trace(tempo_trace(probe["trace_id"]))
            require(loki_rows(probe["trace_id"], probe["started"]) == [],
                    "excluded route unexpectedly logged request_completed")
        time.sleep(2)
    return len(excluded)


def write_json(destination, record):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.chmod(destination, 0o600)


def evidence_root():
    home = Path(os.getenv("WP4_EVIDENCE_ROOT",
                          "/tmp/grafana-otel-wp4-evidence")).expanduser().resolve()
    require(home != ROOT and ROOT not in home.parents,
            "evidence must stay outside the source repository")
    return home


def create_evidence(run_id):
    directory = evidence_root() / run_id
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    return directory


def collect_artifacts(directory):
    items = []
    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            items.append({"path": str(f.relative_to(directory)),
                          "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                          "size_bytes": f.stat().st_size})
    write_json(directory / "manifest.json", {"artifacts": items})
    return items


def run_ui_check(directory):
    script = ROOT / "scripts" / "verify-otel-wp3-ui.cjs"
    env = dict(os.environ)
    env["WP3_EVIDENCE_DIR"] = str(directory / "grafana-ui")
    cmd = ["node", str(script)]
    try:
        outcome = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=110, env=env)
    except FileNotFoundError:
        raise RuntimeError("headless UI prerequisite: Node.js unavailable") from None
    stdout = outcome.stdout
    require(outcome.returncode == 0 and
            "PASS Log -> Trace UI click" in stdout and
            "PASS Trace -> Logs UI click" in stdout and
            '"result":"PASS"' in stdout,
            "WP3 headless Grafana UI correlation test failed")
    return {"status": "PASS", "log_to_trace": True, "trace_to_logs": True,
            "dashboards": 4, "screenshot": "grafana-ui/wp3-related-logs.png"}


def run_live(summary, directory, args):
    require(1 <= args.poll <= 20 and 15 <= args.deadline <= 300,
            "poll/deadline outside safe bounded values")
    summary.update(host_preflight())
    summary["checks"]["preflight"] = "PASS"
    summary["negative_tests"].append(run_fixture_tests())
    summary["checks"]["fault_injection_fixtures"] = "PASS"
    started = time.time()
    for route, method, code, _ in EXPECT:
        warm = request_probe(route, method)
        require(warm["status"] == code, "warmup status unexpected")

    def baseline_fresh():
        records = {}
        for route, method, status, _ in (x for x in EXPECT if x[1] == "GET"):
            key = method + " " + route + ":" + str(status)
            records[key] = prom_sample(route, status)
            require(records[key] is not None and
                    records[key]["ts"] >= started,
                    "current-process baseline not exported")
        return records
    before = poll("baseline", summary["polling"], args.poll,
                  args.deadline, baseline_fresh)
    probe_start = time.time()
    probes = []
    for route, method, code, severity in EXPECT:
        probe = request_probe(route, method, sensitive=True)
        probe["severity"] = severity
        require(probe["status"] == code, "unexpected HTTP probe status")
        probes.append(probe)
    excluded = [request_probe("/healthz"),
                request_probe("/unmapped_" + secrets.token_hex(4))]
    require(excluded[0]["status"] == 200 and excluded[1]["status"] == 404,
            "excluded-route HTTP responses unexpected")
    require(len({p["trace_id"] for p in probes + excluded}) ==
            len(probes) + len(excluded), "W3C trace IDs reused")
    summary["requests"] = [{
        k: v for k, v in p.items() if k in
        ("route", "method", "status", "trace_id", "parent_id", "started", "finished")
    } for p in probes]
    summary["checks"]["fresh_probe_context"] = "PASS"
    after = metric_check(before, probes, args.deadline, args.poll,
                         summary["polling"])
    summary["signals"]["metrics"] = {"status": "PASS", "before": before,
                                     "after": after}
    summary["checks"]["fresh_metric_deltas"] = "PASS"
    logs, traces = log_and_trace(probes, probe_start, args.deadline, args.poll,
                                 summary["polling"], summary["app_version"])
    summary["signals"]["logs"] = {"status": "PASS", "validated_records": len(logs)}
    summary["signals"]["traces"] = {"status": "PASS", "validated_traces": len(traces)}
    summary["checks"]["exact_log_trace_context"] = "PASS"
    indexed = check_index_series(probe_start)
    summary["checks"]["minimal_loki_index_labels"] = "PASS"
    summary["signals"]["logs"]["index_labels"] = indexed
    marker_count = verify_no_sensitive_values(probes, logs, traces, started)
    summary["checks"]["live_sensitive_data_negative"] = "PASS"
    summary["negative_tests"].append({
        "status": "PASS", "mode": "live_synthetic_inputs",
        "case": "no fake secrets in current Console/Loki/Tempo",
        "markers_checked": marker_count
    })
    check_absence(excluded, 8)
    summary["checks"]["excluded_health_and_unknown_traces"] = "PASS"
    summary["negative_tests"].append({
        "status": "PASS", "mode": "live_probe",
        "case": "healthz/unknown routes excluded from demo traces"
    })
    bogus = secrets.token_hex(16)
    require(loki_rows(bogus, probe_start) == [] and tempo_trace(bogus) is None,
            "random non-existent trace ID matched backend")
    summary["negative_tests"].append({
        "status": "PASS", "mode": "live_probe",
        "case": "wrong random trace ID rejected by Loki/Tempo"
    })
    summary["checks"]["live_wrong_trace_id_negative"] = "PASS"
    summary["grafana_ui"] = run_ui_check(directory)
    summary["checks"]["two_way_grafana_ui"] = "PASS"
    summary["checks"]["wp4_live_end_to_end"] = "PASS"
    write_json(directory / "queries" / "query-contract.json", {
        "prometheus": "sum(http_server_request_duration_seconds_count{service_name=\"demo-api\",http_route=\"<route>\",http_response_status_code=\"<code>\"})",
        "loki": '{service_name="demo-api"} | trace_id="<fresh W3C ID>"',
        "tempo": "GET /api/traces/<fresh W3C ID>",
        "freshness_policy": "exported baseline + post-request newer sample/count delta",
        "signals": summary["signals"],
    })
    write_json(directory / "probes" / "requests.json", summary["requests"])
    write_json(directory / "negative-tests" / "results.json",
               summary["negative_tests"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-only", action="store_true")
    parser.add_argument("--poll", type=float,
                        default=float(os.getenv("WP4_POLL_SECONDS", "2")))
    parser.add_argument("--deadline", type=float,
                        default=float(os.getenv("WP4_SIGNAL_DEADLINE", "75")))
    args = parser.parse_args()
    if args.fixtures_only:
        print(json.dumps(run_fixture_tests(), sort_keys=True))
        return 0
    run_id = utc().replace(":", "").replace("-", "").replace(".", "") + "-" + secrets.token_hex(4)
    directory = create_evidence(run_id)
    summary = {
        "schema_version": 1, "run_id": run_id, "start_utc": utc(),
        "end_utc": None, "result": "UNVERIFIED", "scope": "WP4_ONLY",
        "checks": {}, "requests": [], "signals": {},
        "polling": {}, "negative_tests": [], "grafana_ui": {},
        "wp5_recovery_and_restore": "NOT_STARTED",
        "wp6_benchmark": "NOT_STARTED",
        "wp7_independent_final_gate": "NOT_STARTED",
    }
    code = 0
    try:
        run_live(summary, directory, args)
        summary["result"] = "PASS"
    except Exception as exc:
        summary["result"] = ("UNVERIFIED" if
            "headless UI prerequisite" in str(exc) or
            "read-only command failed" in str(exc) else "FAIL")
        summary["failure"] = {"type": type(exc).__name__,
                              "reason": str(exc)[:220]}
        code = 2 if summary["result"] == "UNVERIFIED" else 1
    finally:
        summary["end_utc"] = utc()
        write_json(directory / "execution-summary.json", summary)
        artifacts = collect_artifacts(directory)
        print(json.dumps({"result": summary["result"],
                          "run_id": run_id,
                          "checks": summary["checks"],
                          "artifact_count": len(artifacts),
                          "evidence_directory": str(directory),
                          "failure": summary.get("failure")},
                         sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
