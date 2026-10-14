"""Pure, fail-closed WP4 assertions. Used by live probes and fault injections."""
import base64
import json
import re

ALLOWED_INDEX_LABELS = {"service_name", "deployment_environment_name"}
ALLOWED_SPAN_TAGS = {
    "http.route", "http.request.method", "http.response.status_code",
    "network.protocol.version", "url.scheme",
}
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_metric_delta(before, after, request_time):
    """Count and scrape timestamp must both advance after this run's request."""
    require(before is not None and after is not None, "missing metric signal")
    require(after["ts"] > before["ts"], "metric sample is stale")
    require(after["ts"] >= request_time, "metric sample predates probe")
    require(after["value"] - before["value"] >= 1, "no fresh metric count delta")


def assert_log(rows, probe, service_version):
    """Loki returns [(timestamp_ns, body, merged-labels-and-metadata), ...]."""
    require(len(rows) == 1, "missing or duplicated request_completed log")
    stamp, body, attrs = rows[0]
    require(int(stamp) >= int((probe["started"] - 2) * 1e9),
            "stale log timestamp outside current probe")
    require(int(stamp) <= int((probe["finished"] + 2) * 1e9),
            "log timestamp after current probe window")
    require(isinstance(body, str) and body.startswith("request_completed"),
            "wrong event body")
    require(attrs.get("service_name") == "demo-api" and
            attrs.get("deployment_environment_name") == "lab" and
            attrs.get("service_version") == service_version,
            "log resource identity mismatched")
    require(attrs.get("event_name") == "request_completed",
            "wrong event name")
    require(attrs.get("http_route") == probe["route"] and
            str(attrs.get("http_response_status_code")) == str(probe["status"]),
            "log route/status mismatch")
    require(attrs.get("severity_text") == probe["severity"],
            "log severity mismatch")
    require(attrs.get("trace_id") == probe["trace_id"],
            "wrong/missing log trace context")
    require(isinstance(attrs.get("span_id"), str) and
            HEX16.fullmatch(attrs["span_id"]) is not None,
            "missing/invalid log span context")
    try:
        elapsed = float(attrs.get("duration_ms"))
    except (ValueError, TypeError):
        raise AssertionError("invalid log duration") from None
    require(0 <= elapsed <= 15000, "implausible log duration")
    return attrs["span_id"]


def _val(attributes, key):
    for a in attributes:
        if a.get("key") == key:
            v = a.get("value", {})
            return v.get("stringValue", v.get("intValue", v.get("boolValue")))
    return None


def spans_and_resources(trace):
    spans = []
    resources = []
    if not isinstance(trace, dict):
        return spans, resources
    for batch in trace.get("batches", trace.get("resourceSpans", [])):
        r = batch.get("resource", {}).get("attributes", [])
        resources.append({
            "service.name": _val(r, "service.name"),
            "deployment.environment.name": _val(r, "deployment.environment.name"),
            "service.version": _val(r, "service.version"),
        })
        for group in batch.get(
                "scopeSpans", batch.get("instrumentationLibrarySpans", [])):
            spans.extend(group.get("spans", []))
    return spans, resources


def as_hex(encoded):
    try:
        return base64.b64decode(encoded, validate=True).hex()
    except (TypeError, ValueError, base64.binascii.Error):
        raise AssertionError("invalid encoded span/trace ID") from None


def assert_trace(trace, probe, log_span_id, service_version):
    spans, resources = spans_and_resources(trace)
    require(spans, "missing trace/spans")
    require(any(r.get("service.name") == "demo-api" and
                r.get("deployment.environment.name") == "lab" and
                r.get("service.version") == service_version
                for r in resources), "trace resource identity mismatch")
    require(all(as_hex(s.get("traceId")) == probe["trace_id"] for s in spans),
            "unrelated or stale trace")
    require(all(not s.get("events") for s in spans),
            "unexpected span events/exception data")
    ids = {as_hex(s.get("spanId")) for s in spans}
    require(log_span_id in ids, "log span context missing from Tempo")
    servers = [s for s in spans if s.get("kind") == "SPAN_KIND_SERVER"]
    require(len(servers) == 1, "missing/duplicate server span")
    server = servers[0]
    require(as_hex(server.get("spanId")) == log_span_id,
            "log context points to an unrelated span")
    require(as_hex(server.get("parentSpanId")) == probe["parent_id"],
            "server span did not continue the incoming W3C parent")
    # ASP.NET Core has no matched route template for a method-not-allowed 405.
    method_not_allowed = probe["status"] == 405 and probe.get("method") == "POST"
    if method_not_allowed:
        require(_val(server.get("attributes", []), "http.route") is None,
                "405 unexpectedly contained a route template")
        expected_name = "POST"
    else:
        require(_val(server.get("attributes", []), "http.route") == probe["route"],
                "span route mismatch")
        expected_name = probe.get("method", "GET") + " " + probe["route"]
    require(str(_val(server.get("attributes", []), "http.response.status_code")) ==
            str(probe["status"]), "span response status mismatch")
    require(server.get("name") == expected_name, "HTTP server span name mismatch")
    status = server.get("status", {}).get("code")
    if probe["status"] >= 500:
        require(status == "STATUS_CODE_ERROR", "HTTP 500 not marked Error")
    else:
        require(status != "STATUS_CODE_ERROR", "unexpected Error on non-5xx")
    require(int(server.get("startTimeUnixNano", 0)) >=
            int((probe["started"] - 2) * 1e9), "trace is stale")
    require(int(server.get("startTimeUnixNano", 0)) <=
            int((probe["finished"] + 2) * 1e9), "trace is not from this request")
    if probe["route"] == "/slow":
        require({"ValidateRequest", "SimulatedWork", "BuildResponse"}.issubset(
            {s.get("name") for s in spans}), "missing /slow child span")
        server_id = as_hex(server["spanId"])
        for child in spans:
            if child.get("name") in {"ValidateRequest", "SimulatedWork", "BuildResponse"}:
                require(as_hex(child.get("parentSpanId")) == server_id,
                        "broken child span hierarchy")
    for span in spans:
        for tag in span.get("attributes", []):
            require(tag.get("key") in ALLOWED_SPAN_TAGS,
                    "unapproved span attribute was exported")
    return len(spans)


def assert_index_labels(series):
    require(isinstance(series, list) and series,
            "Loki indexed series unavailable")
    require(all(set(s).issubset(ALLOWED_INDEX_LABELS) for s in series),
            "high-cardinality fields appeared as Loki index labels")


def assert_no_trace(trace):
    require(trace is None, "excluded health/unknown route produced a trace")


def assert_no_secrets(markers, *payloads):
    serialized = "\n".join(x if isinstance(x, str) else
                           json.dumps(x, sort_keys=True) for x in payloads)
    require(all(marker not in serialized for marker in markers),
            "synthetic sensitive data leaked to console, Loki or Tempo")
