"""Pure fault-injection tests against the exact validators used by live WP4."""
import base64
import copy
import unittest

from otel_wp4_checks import (
    assert_index_labels, assert_log, assert_metric_delta, assert_no_secrets,
    assert_no_trace, assert_trace,
)

TID = "a" * 32
PARENT = "b" * 16
SPAN = "c" * 16
VERSION = "0.1.0-wp2"
START = 1000000.0


def enc(h):
    return base64.b64encode(bytes.fromhex(h)).decode()


def attr(key, value):
    return {"key": key, "value": {"stringValue": str(value)}}


def valid():
    probe = {
        "route": "/error", "status": 500, "severity": "Error",
        "trace_id": TID, "parent_id": PARENT, "method": "GET",
        "started": START, "finished": START + 0.1,
    }
    metadata = {
        "service_name": "demo-api", "service_version": VERSION,
        "deployment_environment_name": "lab", "event_name": "request_completed",
        "http_route": "/error", "http_response_status_code": "500",
        "severity_text": "Error", "trace_id": TID, "span_id": SPAN,
        "duration_ms": "50.1",
    }
    rows = [(str(int((START + 0.05) * 1e9)),
             "request_completed structured log", metadata)]
    trace = {
        "batches": [{
            "resource": {"attributes": [
                attr("service.name", "demo-api"),
                attr("service.version", VERSION),
                attr("deployment.environment.name", "lab"),
            ]},
            "scopeSpans": [{"spans": [{
                "traceId": enc(TID), "spanId": enc(SPAN),
                "parentSpanId": enc(PARENT), "name": "GET /error",
                "kind": "SPAN_KIND_SERVER",
                "startTimeUnixNano": str(int((START + 0.01) * 1e9)),
                "attributes": [
                    attr("http.route", "/error"),
                    {"key": "http.response.status_code",
                     "value": {"intValue": "500"}},
                ],
                "status": {"code": "STATUS_CODE_ERROR"},
            }]}],
        }]
    }
    return probe, rows, trace


class VerifierFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.probe, self.rows, self.trace = valid()

    def valid_log(self):
        return assert_log(self.rows, self.probe, VERSION)

    def valid_trace(self):
        return assert_trace(self.trace, self.probe, SPAN, VERSION)

    def test_control_valid_fixture_passes(self):
        self.assertEqual(self.valid_log(), SPAN)
        self.assertEqual(self.valid_trace(), 1)
        assert_metric_delta({"value": 8, "ts": START - 2},
                            {"value": 9, "ts": START + 2}, START)
        assert_index_labels([{
            "service_name": "demo-api", "deployment_environment_name": "lab"}])
        assert_no_trace(None)
        assert_no_secrets(["SECRET_42"], self.trace, self.rows)

    def test_wrong_trace_id_rejected(self):
        self.probe["trace_id"] = "d" * 32
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_prior_run_trace_id_rejected(self):
        self.rows[0][2]["trace_id"] = "e" * 32
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_old_log_timestamp_rejected(self):
        stamp, body, attrs = self.rows[0]
        self.rows = [(str(int((START - 90) * 1e9)), body, attrs)]
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_missing_log_signal_rejected(self):
        self.rows = []
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_duplicate_log_rejected(self):
        self.rows.append(copy.deepcopy(self.rows[0]))
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_missing_activity_context_rejected(self):
        self.rows[0][2]["span_id"] = ""
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_wrong_http_status_rejected(self):
        self.rows[0][2]["http_response_status_code"] = "200"
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_wrong_severity_rejected(self):
        self.rows[0][2]["severity_text"] = "Information"
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_wrong_event_name_rejected(self):
        self.rows[0][2]["event_name"] = "different_event"
        with self.assertRaises(AssertionError):
            self.valid_log()

    def test_missing_trace_signal_rejected(self):
        with self.assertRaises(AssertionError):
            assert_trace(None, self.probe, SPAN, VERSION)

    def test_mismatched_tempo_trace_id_rejected(self):
        self.trace["batches"][0]["scopeSpans"][0]["spans"][0]["traceId"] = enc("f" * 32)
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_wrong_parent_span_rejected(self):
        self.trace["batches"][0]["scopeSpans"][0]["spans"][0]["parentSpanId"] = enc("f" * 16)
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_http_500_without_error_span_rejected(self):
        self.trace["batches"][0]["scopeSpans"][0]["spans"][0]["status"] = {}
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_unapproved_span_attribute_rejected(self):
        self.trace["batches"][0]["scopeSpans"][0]["spans"][0]["attributes"].append(
            attr("url.full", "https://test.invalid/?token=leak"))
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_method_not_allowed_405_without_route_is_valid(self):
        self.probe.update({"status": 405, "method": "POST"})
        server = self.trace["batches"][0]["scopeSpans"][0]["spans"][0]
        server["name"] = "POST"
        server["attributes"] = [a for a in server["attributes"]
                                if a["key"] != "http.route"]
        server["attributes"][0]["value"]["intValue"] = "405"
        server["status"] = {}
        self.assertEqual(self.valid_trace(), 1)

    def test_method_not_allowed_cannot_fake_route_template(self):
        self.probe.update({"status": 405, "method": "POST"})
        server = self.trace["batches"][0]["scopeSpans"][0]["spans"][0]
        server["name"] = "POST"
        server["status"] = {}
        server["attributes"][1]["value"]["intValue"] = "405"
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_otel_4xx_error_span_rejected(self):
        self.probe["status"] = 405
        server = self.trace["batches"][0]["scopeSpans"][0]["spans"][0]
        server["attributes"][1]["value"]["intValue"] = "405"
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_missing_slow_child_span_rejected(self):
        self.probe["route"] = "/slow"
        server = self.trace["batches"][0]["scopeSpans"][0]["spans"][0]
        server["name"] = "GET /slow"
        server["attributes"][0]["value"]["stringValue"] = "/slow"
        with self.assertRaises(AssertionError):
            self.valid_trace()

    def test_stale_metric_timestamp_rejected(self):
        with self.assertRaises(AssertionError):
            assert_metric_delta({"value": 10, "ts": START - 1},
                                {"value": 12, "ts": START - 1}, START)

    def test_no_fresh_metric_delta_rejected(self):
        with self.assertRaises(AssertionError):
            assert_metric_delta({"value": 10, "ts": START - 1},
                                {"value": 10, "ts": START + 2}, START)

    def test_missing_metric_signal_rejected(self):
        with self.assertRaises(AssertionError):
            assert_metric_delta(None, {"value": 1, "ts": START + 1}, START)

    def test_metric_count_reset_does_not_pass(self):
        with self.assertRaises(AssertionError):
            assert_metric_delta({"value": 100, "ts": START - 1},
                                {"value": 1, "ts": START + 2}, START)

    def test_trace_id_not_allowed_as_loki_index_label(self):
        with self.assertRaises(AssertionError):
            assert_index_labels([{"service_name": "demo-api", "trace_id": TID}])

    def test_missing_loki_series_rejected(self):
        with self.assertRaises(AssertionError):
            assert_index_labels([])

    def test_health_trace_noise_rejected(self):
        with self.assertRaises(AssertionError):
            assert_no_trace(self.trace)

    def test_synthetic_secret_in_console_rejected(self):
        with self.assertRaises(AssertionError):
            assert_no_secrets(["FAKE_SECRET_1"], "sample FAKE_SECRET_1")

    def test_synthetic_secret_in_loki_rejected(self):
        self.rows[0][2]["unsafe"] = "FAKE_SECRET_1"
        with self.assertRaises(AssertionError):
            assert_no_secrets(["FAKE_SECRET_1"], self.rows)

    def test_synthetic_secret_in_tempo_rejected(self):
        self.trace["batches"][0]["scopeSpans"][0]["spans"][0]["attributes"].append(
            attr("custom", "FAKE_SECRET_1"))
        with self.assertRaises(AssertionError):
            assert_no_secrets(["FAKE_SECRET_1"], self.trace)


if __name__ == "__main__":
    unittest.main()
