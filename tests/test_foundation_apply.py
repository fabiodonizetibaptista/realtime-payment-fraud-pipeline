import unittest
import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import lab

from lab import FOUNDATION_APPLY_RESOURCES, validate_foundation_plan


def make_plan(addresses=None, actions_by_address=None):
    addresses = (
        sorted(FOUNDATION_APPLY_RESOURCES)
        if addresses is None else addresses
    )
    actions_by_address = actions_by_address or {}

    return {
        "errored": False,
        "resource_changes": [
            {
                "address": address,
                "change": {
                    "actions": actions_by_address.get(address, ["create"])
                },
            }
            for address in addresses
        ],
    }


class FoundationPlanningTests(unittest.TestCase):
    def test_plan_targets_exactly_foundation_and_saves_plan(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured["env"] = kwargs["env"]
            return "Plan: 14 to add."

        with tempfile.TemporaryDirectory() as folder, \
             patch.object(lab, "TF_DIR", Path(folder)), \
             patch.object(lab, "ENV_FILE", Path(folder) / ".env"), \
             patch.object(lab, "run_command", side_effect=fake_run), \
             patch.dict(os.environ, {}, clear=True), \
             redirect_stdout(io.StringIO()):
            lab.plan()

        args = captured["args"]
        targets = {arg.removeprefix("-target=") for arg in args if arg.startswith("-target=")}
        self.assertEqual(targets, FOUNDATION_APPLY_RESOURCES)
        self.assertEqual(sum(arg.startswith("-target=") for arg in args), 14)
        self.assertIn("-input=false", args)
        self.assertEqual(args[-1], "-out=foundation.tfplan")
        self.assertEqual(captured["env"]["TF_LOG"], "OFF")

    def test_plan_does_not_print_provider_output(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(lab, "TF_DIR", Path(folder)), \
             patch.object(lab, "ENV_FILE", Path(folder) / ".env"), \
             patch.object(lab, "run_command", return_value="SENSITIVE_PROVIDER_OUTPUT"), \
             patch.dict(os.environ, {}, clear=True), \
             redirect_stdout(io.StringIO()) as output:
            lab.plan()
        self.assertNotIn("SENSITIVE_PROVIDER_OUTPUT", output.getvalue())


class FoundationApplyTests(unittest.TestCase):
    def test_accepts_exact_foundation_create_plan(self):
        result = validate_foundation_plan(make_plan())
        self.assertEqual(set(result), FOUNDATION_APPLY_RESOURCES)
        self.assertEqual(len(result), 14)

    def test_rejects_missing_resource(self):
        addresses = sorted(FOUNDATION_APPLY_RESOURCES)
        addresses.pop()
        with self.assertRaisesRegex(RuntimeError, "AUSENTES"):
            validate_foundation_plan(make_plan(addresses))

    def test_rejects_unexpected_resource(self):
        addresses = sorted(FOUNDATION_APPLY_RESOURCES)
        addresses.append("confluent_kafka_acl.unauthorized")
        with self.assertRaisesRegex(RuntimeError, "NAO_AUTORIZADOS") as error:
            validate_foundation_plan(make_plan(addresses))
        self.assertIn("python lab.py plan", str(error.exception))

    def test_rejects_update(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["update"]})
            )

    def test_rejects_replacement(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["delete", "create"]})
            )

    def test_rejects_destroy(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["delete"]})
            )


if __name__ == "__main__":
    unittest.main()
