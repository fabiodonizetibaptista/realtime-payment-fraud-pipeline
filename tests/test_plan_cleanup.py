"""Planos submetidos ao apply sao removidos (consumidos ou stale).

Na execucao run-20261111, planos aplicados ficaram em infra/terraform e
bloquearam a etapa seguinte (PLAN_ALREADY_EXISTS / EXISTING_PLAN), alem de
conterem dados sensiveis. Um clone novo precisa repetir J1-J6 sem limpeza manual.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


def resource(address, actions):
    return {"address": address, "type": address.split(".")[0], "mode": "managed",
            "change": {"actions": actions, "before": None, "after": {}}}


class PlanCleanupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        for target, value in (("TF_DIR", self.directory),):
            patcher = patch.object(lab, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, kwargs in (("merge_env_file", {}), ("secret_values", {"return_value": []})):
            patcher = patch.object(lab, target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def runner(self, changes, fail_apply=False, plan_name=None):
        def execute(command, **kwargs):
            if "plan" in command and plan_name:
                (self.directory / plan_name).touch()
                return ""
            if "show" in command:
                return json.dumps({"resource_changes": changes})
            if "apply" in command:
                if fail_apply:
                    raise RuntimeError("MOCK_PROVIDER_FAILURE")
                return ""
            raise AssertionError(command)
        return execute

    def test_pipeline_plan_removed_after_success_and_failure(self):
        changes = [resource("confluent_flink_compute_pool.payment_fraud", ["create"])]
        for fail in (False, True):
            with self.subTest(fail_apply=fail):
                plan = self.directory / "pipeline.tfplan"
                plan.touch()
                with patch.object(lab, "run_command", side_effect=self.runner(changes, fail)), \
                     patch("builtins.input", return_value="APPLY PIPELINE"):
                    try:
                        lab.apply_pipeline(confirm=True)
                    except RuntimeError:
                        self.assertTrue(fail)
                self.assertFalse(plan.exists())

    def test_teardown_plan_removed_after_apply_and_on_cancel(self):
        changes = [resource("confluent_service_account.cdc", ["delete"])]
        for answer in ("DESTROY PIPELINE", "nao"):
            with self.subTest(answer=answer):
                with patch.object(lab, "run_command",
                                  side_effect=self.runner(changes, plan_name="teardown.tfplan")), \
                     patch("builtins.input", return_value=answer):
                    lab.teardown(confirm=True)
                self.assertFalse((self.directory / "teardown.tfplan").exists())

    def test_failed_teardown_points_to_reconciliation_not_retry(self):
        changes = [resource("confluent_service_account.cdc", ["delete"])]
        with patch.object(lab, "run_command",
                          side_effect=self.runner(changes, fail_apply=True, plan_name="teardown.tfplan")), \
             patch("builtins.input", return_value="DESTROY PIPELINE"):
            with self.assertRaisesRegex(RuntimeError, "reconcile_state"):
                lab.teardown(confirm=True)
        self.assertFalse((self.directory / "teardown.tfplan").exists())


if __name__ == "__main__":
    unittest.main()
