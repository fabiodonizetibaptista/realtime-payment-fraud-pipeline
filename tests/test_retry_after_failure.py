"""Restos de uma tentativa falha nao travam a proxima."""
import tempfile
import unittest
from pathlib import Path

from safety import archive_previous, discard_stale_plan


class RetryHelpersTests(unittest.TestCase):
    def test_stale_plan_is_discarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "pipeline.tfplan"
            self.assertFalse(discard_stale_plan(plan))
            plan.write_text("old")
            self.assertTrue(discard_stale_plan(plan))
            self.assertFalse(plan.exists())

    def test_previous_attempt_is_archived_with_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "stage5-cdc-baseline.json"
            self.assertIsNone(archive_previous(target))
            target.write_text("first")
            first = archive_previous(target)
            target.write_text("second")
            second = archive_previous(target)
            self.assertFalse(target.exists())
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), "first")
            self.assertEqual(second.read_text(), "second")

    def test_runbook_scripts_no_longer_block_on_previous_attempts(self):
        root = Path(__file__).resolve().parents[1]
        blocking = ("EXISTING_PLAN'", 'EXISTING_PLAN"', "PLAN_ALREADY_EXISTS", "SCENARIO_ALREADY_RECORDED",
                    "SCENARIO_RESULT_ALREADY_EXISTS", "REPORT_ALREADY_EXISTS", "OUTPUT_ALREADY_EXISTS",
                    "EVIDENCE_TARGET_ALREADY_EXISTS")
        files = ["lab.py", "scripts/plan_cdc_acls.py", "scripts/plan_cdc_connector.py",
                 "scripts/plan_schema_compatibility_policy.py", "scripts/teardown_cdc_connector.py",
                 "scripts/reconcile_state.py", "scripts/cdc_test_scenario.py", "scripts/fraud_scenarios.py",
                 "scripts/collect_operations_evidence.py", "scripts/collect_schema_evidence.py",
                 "scripts/verify_schema_compatibility.py", "src/consumer/verify_cdc_lifecycle.py"]
        for name in files:
            text = (root / name).read_text(encoding="utf-8")
            for marker in blocking:
                with self.subTest(file=name, marker=marker):
                    self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
