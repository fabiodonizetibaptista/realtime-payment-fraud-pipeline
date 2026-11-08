"""Testes locais das protecoes do apply-pipeline.

Todas as chamadas Terraform sao simuladas com mocks.
Nenhuma credencial ou infraestrutura real e utilizada.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


def resource(address, actions=("create",)):
    return {
        "address": address,
        "type": address.split(".")[0],
        "mode": "managed",
        "change": {
            "actions": list(actions),
            "before": None,
            "after": {},
        },
    }


class PipelineApplyTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.directory = Path(self.temp.name)
        self.plan = self.directory / "pipeline.tfplan"
        self.plan.touch()

        patcher = patch.object(lab, "TF_DIR", self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(lab, "merge_env_file")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(lab, "secret_values", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_terraform(self, changes, fail_apply=False):
        def execute(command, **kwargs):
            if "show" in command:
                return json.dumps({"resource_changes": changes})

            if "apply" in command:
                if fail_apply:
                    raise RuntimeError("MOCK_PROVIDER_FAILURE")
                return ""

            raise AssertionError("UNEXPECTED_TERRAFORM_COMMAND")

        return execute

    def test_requires_confirmation(self):
        with patch.object(lab, "run_command") as runner:
            with self.assertRaisesRegex(
                RuntimeError, "CONFIRMATION_REQUIRED"
            ):
                lab.apply_pipeline()
            runner.assert_not_called()

    def test_requires_saved_plan(self):
        self.plan.unlink()

        with patch.object(lab, "run_command") as runner:
            with self.assertRaisesRegex(
                RuntimeError, "PLAN_NOT_FOUND"
            ):
                lab.apply_pipeline(confirm=True)
            runner.assert_not_called()

    def test_blocks_cdc_without_authorization(self):
        changes = [
            resource("confluent_connector.payments_cdc[0]")
        ]

        with patch.object(
            lab, "run_command",
            side_effect=self.fake_terraform(changes)
        ) as runner:
            with self.assertRaisesRegex(
                RuntimeError,
                "CDC_REQUIRES_EXPLICIT_AUTHORIZATION"
            ):
                lab.apply_pipeline(confirm=True)

            self.assertEqual(runner.call_count, 1)

    def test_blocks_destroy(self):
        changes = [
            resource("aiven_pg.payments", ("delete",))
        ]

        with patch.object(
            lab, "run_command",
            side_effect=self.fake_terraform(changes)
        ) as runner:
            with self.assertRaisesRegex(RuntimeError, "UNSAFE_PLAN"):
                lab.apply_pipeline(confirm=True)

            self.assertEqual(runner.call_count, 1)

    def test_blocks_replacement(self):
        changes = [
            resource(
                "confluent_kafka_cluster.basic",
                ("delete", "create")
            )
        ]

        with patch.object(
            lab, "run_command",
            side_effect=self.fake_terraform(changes)
        ) as runner:
            with self.assertRaisesRegex(RuntimeError, "UNSAFE_PLAN"):
                lab.apply_pipeline(confirm=True)

            self.assertEqual(runner.call_count, 1)

    def test_operator_can_cancel(self):
        changes = [
            resource("confluent_kafka_acl.example")
        ]

        with (
            patch.object(
                lab, "run_command",
                side_effect=self.fake_terraform(changes)
            ) as runner,
            patch("builtins.input", return_value="CANCEL"),
        ):
            lab.apply_pipeline(confirm=True)
            self.assertEqual(runner.call_count, 1)

    def test_approved_plan_can_execute(self):
        changes = [
            resource("confluent_kafka_acl.example")
        ]

        with (
            patch.object(
                lab, "run_command",
                side_effect=self.fake_terraform(changes)
            ) as runner,
            patch("builtins.input", return_value="APPLY PIPELINE"),
        ):
            lab.apply_pipeline(confirm=True)
            self.assertEqual(runner.call_count, 2)

            command = runner.call_args.args[0]
            self.assertEqual(command[0:2], ["terraform", "apply"])

    def test_apply_failure_is_sanitized(self):
        changes = [
            resource("confluent_kafka_acl.example")
        ]

        with (
            patch.object(
                lab, "run_command",
                side_effect=self.fake_terraform(
                    changes, fail_apply=True
                )
            ),
            patch("builtins.input", return_value="APPLY PIPELINE"),
        ):
            with self.assertRaises(RuntimeError) as captured:
                lab.apply_pipeline(confirm=True)

            self.assertIn(
                "PIPELINE_APPLY_FAILED",
                str(captured.exception)
            )
            self.assertNotIn(
                "MOCK_PROVIDER_FAILURE",
                str(captured.exception)
            )


if __name__ == "__main__":
    unittest.main()
