#!/usr/bin/env python3
"""WP3: verify file-provisioned Grafana data sources, panels and fresh data."""
import base64
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAFANA = "http://127.0.0.1:3300"
API = "http://127.0.0.1:8082"
USER = os.getenv("GRAFANA_USER", "admin")
PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")
AUTH = "Basic " + base64.b64encode((USER + ":" + PASSWORD).encode()).decode()
BUILTINS = {"prometheus", "loki", "tempo", "pyroscope"}
LAB = {"prometheus": "lab-otel-prometheus", "loki": "lab-otel-loki",
       "tempo": "lab-otel-tempo"}
DASHBOARDS = ("prometheus-first-look", "demo-api-metrics",
              "demo-api-logs", "demo-api-traces")


def get_json(url, authenticate=True):
    headers = {"Authorization": AUTH} if authenticate else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                timeout=12) as response:
        return json.load(response)


def grafana(path):
    return get_json(GRAFANA + path)


def query(uid, path, params):
    encoded = urllib.parse.urlencode(params)
    return grafana("/api/datasources/proxy/uid/" + uid + path + "?" + encoded)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def probe(route):
    tid = secrets.token_hex(16)
    sid = secrets.token_hex(8)
    request = urllib.request.Request(API + route, headers={
        "traceparent": f"00-{tid}-{sid}-01"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        error.read()
    check(status == (500 if route == "/error" else 200),
          "wrong HTTP status for " + route)
    return tid


def verify_structure():
    datasources = {x["uid"]: x for x in grafana("/api/datasources")}
    check(BUILTINS.issubset(datasources), "LGTM built-in data source disappeared")
    check(set(LAB.values()).issubset(datasources), "experiment data source missing")
    loki = datasources[LAB["loki"]]["jsonData"]
    tempo = datasources[LAB["tempo"]]["jsonData"]["tracesToLogsV2"]
    expected_link = "$" + "{__value.raw}"
    expected_query = '{service_name="demo-api"} | trace_id = "' + "$" + '{__trace.traceId}"'
    check(any(f.get("matcherType") == "label" and
              f.get("matcherRegex") == "^trace_id$" and
              f.get("datasourceUid") == LAB["tempo"] and
              f.get("url") == expected_link for f in loki["derivedFields"]),
          "Loki structured-metadata derived link missing")
    check(tempo.get("datasourceUid") == LAB["loki"] and
          tempo.get("customQuery") is True and tempo.get("query") == expected_query,
          "Tempo trace-to-logs exact-ID query wrong")
    print("PASS WP3 built-ins preserved and isolated two-way correlation data sources")
    checks = []
    for uid in DASHBOARDS:
        response = grafana("/api/dashboards/uid/" + uid)
        dashboard, metadata = response["dashboard"], response["meta"]
        check(metadata.get("provisioned") is True and
              metadata.get("folderTitle") == "Observability Lab OTel",
              "missing file-provisioned dashboard " + uid)
        check(bool(dashboard["panels"]), "no panels in " + uid)
        for panel in dashboard["panels"]:
            data_source = panel["datasource"]
            check(data_source["uid"] in LAB.values(),
                  "non-experiment data source in " + uid)
            for target in panel["targets"]:
                source = target.get("datasource", data_source)
                check(source["uid"] == data_source["uid"],
                      "panel/target UID mismatch")
                expr = target.get("expr") or target.get("query") or ""
                check("demo_http_" not in expr, "legacy prometheus-net query")
                checks.append((uid, panel["id"], source["type"], expr))
        print("PASS WP3 dashboard", uid, "panels", len(dashboard["panels"]))
    return checks


def query_panel(item, started):
    uid, panel_id, data_type, expr = item
    if data_type == "prometheus":
        response = query(LAB[data_type], "/api/v1/query", {"query": expr})
        count = len(response.get("data", {}).get("result", []))
    elif data_type == "loki":
        if uid == "demo-api-logs" and panel_id == 1:
            response = query(LAB[data_type], "/loki/api/v1/query_range", {
                "query": expr, "start": str((started - 10) * 10**9),
                "limit": "200"})
            count = sum(len(s.get("values", []))
                        for s in response.get("data", {}).get("result", []))
        else:
            response = query(LAB[data_type], "/loki/api/v1/query",
                             {"query": expr})
            count = len(response.get("data", {}).get("result", []))
    else:
        response = query(LAB["tempo"], "/api/search", {
            "q": expr, "start": int(time.time() - 900),
            "end": int(time.time()) + 5, "limit": 50})
        count = len(response.get("traces", []))
    check(response.get("status", "success") == "success" and count > 0,
          f"empty/failed query {uid} panel {panel_id}")


def verify_fresh_trace(started, trace_id):
    response = query(LAB["loki"], "/loki/api/v1/query_range", {
        "query": '{service_name="demo-api"} | trace_id="' + trace_id + '"',
        "start": str((started - 10) * 10**9), "limit": "50"})
    count = sum(len(s.get("values", []))
                for s in response.get("data", {}).get("result", []))
    check(count == 1, f"fresh trace log count {count} != 1")
    trace = grafana("/api/datasources/proxy/uid/" + LAB["tempo"] +
                    "/api/traces/" + trace_id)
    check(bool(trace.get("batches") or trace.get("resourceSpans")),
          "fresh Tempo trace has no spans")


def main():
    checks = verify_structure()
    started = int(time.time())
    for route in ("/ok", "/slow"):
        probe(route)
    trace_id = probe("/error")
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        try:
            for item in checks:
                query_panel(item, started)
            verify_fresh_trace(started, trace_id)
            print(json.dumps({"scope": "WP3 API + query smoke",
                              "status": "PASS", "dashboards": len(DASHBOARDS),
                              "queries": len(checks), "fresh_trace_id": trace_id,
                              "ui_clicks": "verified separately"}))
            return
        except (AssertionError, KeyError, urllib.error.HTTPError,
                urllib.error.URLError, TimeoutError):
            time.sleep(2)
    raise AssertionError("WP3 dashboard/trace query deadline exceeded")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("FAIL WP3:", type(error).__name__, str(error), file=sys.stderr)
        sys.exit(1)
