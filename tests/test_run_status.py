"""`lab.py status`: cada situacao de retomada, sem nuvem."""
import tempfile
import unittest
from pathlib import Path

from lab import FOUNDATION_APPLY_RESOURCES as FOUNDATION
from safety import evidence_path
from scripts.run_status import (
    CDC_ACL, CONNECTOR, POOL, POSTGRES, SUBJECT, Snapshot, assess, render, window_start,
)

J1_KEYS = {"TF_VAR_foundation_kafka_api_key"}
J2_KEYS = J1_KEYS | {"PGHOST", "CDC_PGPASSWORD"}
PIPELINE = set(FOUNDATION) | {POSTGRES, POOL}


def text(snapshot, outputs=None):
    return "\n".join(render(snapshot, FOUNDATION, outputs or {}))


class RunStatusTests(unittest.TestCase):
    def test_not_initialized(self):
        self.assertEqual(assess(Snapshot(state_available=False), FOUNDATION)["next"], "J0.1")

    def test_nothing_provisioned_yet(self):
        result = assess(Snapshot(), FOUNDATION)
        self.assertEqual((result["situation"], result["next"]), ("NADA_PROVISIONADO", "J0.2"))

    def test_after_foundation_only(self):
        result = assess(Snapshot(state=set(FOUNDATION)), FOUNDATION)
        self.assertEqual(result["next"], "J1.2")
        self.assertTrue(any("Kafka" in item for item in result["billing"]))

    def test_after_j3_next_is_connector(self):
        snap = Snapshot(state=PIPELINE | {CDC_ACL}, env_keys=J2_KEYS)
        self.assertEqual(assess(snap, FOUNDATION)["next"], "J4.1")

    def test_connector_up_shows_billing_and_restores_window(self):
        snap = Snapshot(state=PIPELINE | {CDC_ACL, CONNECTOR}, env_keys=J2_KEYS, run_id="run-20261112",
                        connector_created_at="2026-11-12T17:59:14.5+00:00", running_statements=0)
        out = text(snap, {"environment_id": "env-x", "kafka_cluster_id": "lkc-x"})
        self.assertIn("PROXIMO_BLOCO=J4.1", out)
        self.assertIn("conector CDC ativo desde 2026-11-12T17:59:14.5+00:00", out)
        self.assertIn("export WINDOW_START=2026-11-12T17:59:00Z", out)
        self.assertIn("export EVIDENCE_RUN_ID=run-20261112", out)
        self.assertIn("export ENV_ID=env-x", out)
        self.assertIn("J5 e ao J6", out)

    def test_all_proofs_done_connector_still_up_next_is_j5(self):
        evidence = {"cdc/stage5-cdc-lifecycle.json", "schemas/stage6-compatibility-summary.json",
                    "flink/fraud-scenario-alert.json", "observability/metrics-api-20261112T181401Z.json"}
        snap = Snapshot(state=PIPELINE | {CDC_ACL, CONNECTOR, SUBJECT}, env_keys=J2_KEYS, evidence=evidence,
                        running_statements=1)
        result = assess(snap, FOUNDATION)
        self.assertEqual(result["next"], "J5")
        self.assertTrue(any("statement" in item for item in result["billing"]))

    def test_connector_removed_next_is_teardown(self):
        evidence = {"cdc/stage5-cdc-lifecycle.json", "schemas/stage6-compatibility-summary.json",
                    "flink/fraud-scenario-alert.json", "observability/metrics-api-x.json"}
        snap = Snapshot(state=PIPELINE | {CDC_ACL, SUBJECT}, env_keys=J2_KEYS, evidence=evidence)
        self.assertEqual(assess(snap, FOUNDATION)["next"], "J6 (teardown total)")

    def test_everything_torn_down(self):
        result = assess(Snapshot(evidence={"flink/fraud-scenario-alert.json"}), FOUNDATION)
        self.assertEqual((result["situation"], result["next"]), ("TUDO_DERRUBADO", "J7 (custo)"))

    def test_lock_plans_and_unverified_statements_are_reported(self):
        out = text(Snapshot(state=PIPELINE, state_lock=True, leftover_plans=["pipeline.tfplan"]))
        self.assertIn("STATE_TRAVADO", out)
        self.assertIn("pipeline.tfplan", out)
        self.assertIn("STATEMENTS_FLINK=NAO_VERIFICADO", out)

    def test_window_start_invalid_is_empty(self):
        self.assertEqual(window_start("not-a-date"), "")


class SavedRunIdTests(unittest.TestCase):
    def test_evidence_uses_saved_run_id_when_terminal_lost(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".local").mkdir()
            (root / ".local" / "evidence_run_id").write_text("run-20261112\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(evidence_path(root, "cdc/x.json"),
                                 root / "evidencias" / "runs" / "run-20261112" / "cdc" / "x.json")
            # ambiente explicito continua soberano (testes e chamadas deliberadas)
            self.assertEqual(evidence_path(root, "cdc/x.json", {}), root / "evidencias" / "cdc" / "x.json")


if __name__ == "__main__":
    unittest.main()
