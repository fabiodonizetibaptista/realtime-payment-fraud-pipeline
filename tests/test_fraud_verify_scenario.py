"""Verificacao dirigida do alerta do cenario sintetico, sem nuvem."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.fraud_stream import VERIFY_SQL, evaluate_scenario, load_manifest, save_scenario_evidence
from scripts.flink_runtime import FlinkRuntimeError

IDS = [-1001, -1002, -1003, -1004]  # legitimo, fraude 1..3


def row(a, b, c):
    return {"first_transaction_id": str(a), "middle_transaction_id": str(b),
            "last_transaction_id": str(c), "transaction_count": "3"}


class VerifyScenarioTests(unittest.TestCase):
    def test_exact_fraud_match_without_legitimate_passes(self):
        result = evaluate_scenario([row(-1002, -1003, -1004)], IDS)
        self.assertTrue(result["FRAUD_SEQUENCE_MATCHED"])
        self.assertFalse(result["LEGITIMATE_IN_ANY_MATCH"])
        self.assertEqual(result["SCENARIO_ALERT_GATE"], "PASS")

    def test_no_match_is_not_pass(self):
        self.assertEqual(evaluate_scenario([], IDS)["SCENARIO_ALERT_GATE"], "PENDING_OR_FAIL")

    def test_legitimate_in_match_fails(self):
        rows = [row(-1002, -1003, -1004), row(-1001, 5, 6)]
        self.assertEqual(evaluate_scenario(rows, IDS)["SCENARIO_ALERT_GATE"], "PENDING_OR_FAIL")

    def test_partial_or_reordered_match_is_not_exact(self):
        self.assertFalse(evaluate_scenario([row(-1003, -1002, -1004)], IDS)["FRAUD_SEQUENCE_MATCHED"])
        self.assertFalse(evaluate_scenario([row(7, -1002, -1003)], IDS)["FRAUD_SEQUENCE_MATCHED"])

    def test_manifest_must_be_completed_with_four_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps({"status": "STARTED", "test_ids": IDS}), encoding="utf-8")
            with self.assertRaises(FlinkRuntimeError):
                load_manifest(path)
            path.write_text(json.dumps({"status": "COMPLETED", "test_ids": IDS}), encoding="utf-8")
            self.assertEqual(load_manifest(path), IDS)

    def test_sql_only_interpolates_integers(self):
        sql = VERIFY_SQL.format(ids=", ".join(str(int(v)) for v in IDS))
        self.assertIn("IN (-1001, -1002, -1003, -1004)", sql)
        self.assertIn("`desafio-final`.`desafio-basic`.`fraud.pattern_matches`", sql)


    def test_evidence_has_no_transaction_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert.json"
            save_scenario_evidence(evaluate_scenario([row(-1002, -1003, -1004)], IDS), path)
            saved = path.read_text(encoding="utf-8")
            for value in IDS:
                self.assertNotIn(str(value), saved)
            self.assertEqual(json.loads(saved)["scenario_alert_gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
