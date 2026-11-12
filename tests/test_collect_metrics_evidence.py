"""Coletor da Metrics API: consultas montadas dos modelos, sem credenciais na evidencia."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.collect_metrics_evidence import QUERIES, TEMPLATES, build_query, parse_utc, summarize

START = datetime(2026, 11, 12, 1, 57, tzinfo=timezone.utc)
END = datetime(2026, 11, 12, 2, 39, tzinfo=timezone.utc)


class MetricsCollectorTests(unittest.TestCase):
    def test_templates_are_filled_without_placeholders(self):
        for name in QUERIES.values():
            body = build_query((TEMPLATES / name).read_text(encoding="utf-8"), "lkc-x", START, END)
            text = json.dumps(body)
            self.assertNotIn("__", text)
            self.assertEqual(body["filter"]["value"], "lkc-x")
            self.assertEqual(body["intervals"], ["2026-11-12T01:57:00Z/2026-11-12T02:39:00Z"])

    def test_received_bytes_summary(self):
        summary = summarize("received_bytes", {"data": [
            {"timestamp": "t1", "value": 100.0}, {"timestamp": "t2", "value": 50.0}]})
        self.assertEqual((summary["points"], summary["total_bytes"], summary["peak_bytes_per_minute"]), (2, 150.0, 100.0))
        self.assertEqual(summary["status"], "COM_DADOS")

    def test_lag_summary_groups_and_empty(self):
        summary = summarize("consumer_lag_offsets", {"data": [
            {"metric.consumer_group_id": "desafio-x", "value": 4}, {"metric.consumer_group_id": "desafio-x", "value": 0}]})
        self.assertEqual(summary["groups"], {"desafio-x": {"points": 2, "max_lag": 4.0}})
        self.assertEqual(summarize("consumer_lag_offsets", {"data": []})["status"], "SEM_DADOS")

    def test_start_must_be_utc(self):
        self.assertEqual(parse_utc("2026-11-12T01:57:00Z"), START)
        with self.assertRaises(ValueError):
            parse_utc("2026-11-12T01:57:00")

    def test_metrics_identity_is_terraform_managed_with_minimum_role(self):
        tf = (Path(__file__).resolve().parents[1] / "infra/terraform/metrics-identity.tf").read_text(encoding="utf-8")
        self.assertIn('role_name   = "MetricsViewer"', tf)
        self.assertNotRegex(tf, r"managed_resource\s*\{")  # Cloud API key
        self.assertIn("sensitive   = true", tf)


if __name__ == "__main__":
    unittest.main()
