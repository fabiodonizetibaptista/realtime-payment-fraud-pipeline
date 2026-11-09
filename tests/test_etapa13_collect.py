"""Testes locais do coletor, sem chamadas cloud."""

import unittest
from decimal import Decimal
from unittest.mock import patch

from scripts import etapa13_collect as collector


class Etapa13CollectTests(unittest.TestCase):
    def test_active_environment(self):
        result = collector.active_environment([
            {"id": "env-a", "is_current": False},
            {"id": "env-b", "is_current": True},
        ])
        self.assertEqual(result["id"], "env-b")

    def test_missing_active_environment(self):
        with self.assertRaises(ValueError):
            collector.active_environment([])

    def test_billing_excludes_other_environments(self):
        result = collector.summarize_billing([
            {"environment": "env-a", "product": "FLINK",
             "line_type": "FLINK_NUM_CFUS", "amount": "0.25"},
            {"environment": "env-b", "product": "CONNECT",
             "line_type": "CONNECT_NUM_TASKS", "amount": "9"},
            {"line_type": "PROMO_CREDIT", "amount": "-0.25"},
        ], "env-a")

        self.assertEqual(
            Decimal(result["environment_total_usd"]),
            Decimal("0.25"),
        )
        self.assertEqual(
            result["global_promo_credits_usd"], "-0.25"
        )
        self.assertEqual(result["other_environment_items"], 1)

    def test_unknown_environment_is_not_attributed(self):
        result = collector.summarize_billing([
            {"product": "KAFKA", "amount": "5"}
        ], "env-a")

        self.assertEqual(result["environment_total_usd"], "0")
        self.assertEqual(result["unattributed_items"], 1)

    def test_collect_uses_read_only_queries(self):
        responses = [
            [{"id": "env-a", "name": "test", "is_current": True}],
            [{"id": "lkc-test", "name": "cluster", "status": "UP"}],
            [{"id": "lfcp-test", "status": "PROVISIONED"}],
            [{"id": "sa-test"}],
            [{"operation": "READ"}],
            [{"environment": "env-a", "product": "FLINK",
              "amount": "0.10"}],
        ]

        with patch.object(collector, "query", side_effect=responses) as mocked:
            report = collector.collect("2026-11-01", "2026-11-10")

        self.assertEqual(mocked.call_count, 6)
        self.assertEqual(report["service_account_count"], 1)
        self.assertEqual(report["kafka_acl_count"], 1)
        self.assertEqual(
            report["billing"]["environment_total_usd"], "0.10"
        )


if __name__ == "__main__":
    unittest.main()
