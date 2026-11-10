import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lab
import safety


class ToolValidationTests(unittest.TestCase):
    def test_devcontainer_uses_pinned_python_312_image_and_post_create_installer(self):
        import json
        config = json.loads((ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
        self.assertEqual(config["image"], "mcr.microsoft.com/devcontainers/python:3.3.2-3.12-bookworm")
        self.assertEqual(config["postCreateCommand"], "python .devcontainer/install_tools.py")

    def test_minimum_versions_accept_newer_versions_and_warn(self):
        outputs = iter((
            '{"terraform_version":"1.16.2"}',
            "Version: v4.81.0",
        ))
        with patch.object(lab, "run_command", side_effect=lambda *args, **kwargs: next(outputs)):
            captured = io.StringIO()
            with redirect_stdout(captured):
                lab._check_versions()
        self.assertIn("Terraform encontrado 1.16.2", captured.getvalue())
        self.assertNotIn("Confluent CLI encontrado", captured.getvalue())

    def test_versions_below_minimum_are_rejected(self):
        with patch.object(lab, "run_command", return_value='{"terraform_version":"1.15.9"}'):
            with self.assertRaisesRegex(RuntimeError, "Terraform >= 1.16.0 requerido"):
                lab._check_versions()

    def test_confluent_cli_below_minimum_is_rejected(self):
        outputs = iter((
            '{"terraform_version":"1.16.0"}',
            "Version: v4.80.9",
        ))
        with patch.object(lab, "run_command", side_effect=lambda *args, **kwargs: next(outputs)):
            with self.assertRaisesRegex(RuntimeError, "Confluent CLI >= 4.81.0 requerido"):
                lab._check_versions()

    def test_confluent_cli_newer_version_is_accepted_with_warning(self):
        outputs = iter((
            '{"terraform_version":"1.16.0"}',
            "Version: v4.82.1",
        ))
        with patch.object(lab, "run_command", side_effect=lambda *args, **kwargs: next(outputs)):
            captured = io.StringIO()
            with redirect_stdout(captured):
                lab._check_versions()
        self.assertIn("Confluent CLI encontrado Version: v4.82.1", captured.getvalue())

    def test_cli_help_checks_common_flags_and_defers_cloud_acl_flags(self):
        def fake_help(args, **kwargs):
            command = tuple(args[1:-1])
            if command == ("schema-registry", "schema", "compatibility", "validate"):
                return "--subject --type"
            if command == ("billing", "cost", "list"):
                return "--start-date --end-date"
            return "Usage: confluent " + " ".join(command)

        with patch.object(lab, "run_command", side_effect=fake_help):
            lab.check_cli_help()
        self.assertEqual(len(lab.CLI_HELP_COMMANDS), 11)

    def test_missing_terraform_has_readme_guidance(self):
        with patch("safety.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, "Terraform não encontrado no PATH; veja o README"):
                safety.run_command(["terraform", "version"], cwd=ROOT)

    def test_missing_confluent_has_readme_guidance(self):
        with patch("safety.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, "Confluent CLI não encontrado no PATH; veja o README"):
                safety.run_command(["confluent", "version"], cwd=ROOT)


    def test_setup_initializes_local_state_backend_without_backend_false(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return ""

        with patch.object(lab, "_check_versions"), \
             patch.object(lab, "run_command", side_effect=fake_run), \
             patch.object(lab, "check_cli_help"), \
             patch.dict(os.environ, {}, clear=True), \
             redirect_stdout(io.StringIO()):
            lab.setup()

        init_call = next(call for call in calls if call[0][1] == "init")
        self.assertNotIn("-backend=false", init_call[0])
        self.assertIn("-lockfile=readonly", init_call[0])
        self.assertEqual(init_call[1]["env"]["TF_LOG"], "OFF")

    def test_plan_loads_local_env_and_keeps_tf_debug_logging_off(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "TF_VAR_foundation_kafka_api_key=key-id\n"
                "TF_VAR_foundation_kafka_api_secret=key-secret-value\n",
                encoding="utf-8",
            )
            captured = {}

            def fake_run(args, **kwargs):
                captured["args"] = args
                captured["env"] = kwargs["env"]
                captured["secrets"] = kwargs["secrets"]
                return "Plan: 0 to add, 0 to change, 0 to destroy."

            with patch.object(lab, "ENV_FILE", env_file), \
                 patch.object(lab, "run_command", side_effect=fake_run), \
                 patch.dict(os.environ, {}, clear=True), \
                 redirect_stdout(io.StringIO()):
                lab.plan()

            self.assertIn("foundation.tfplan", captured["args"][-1])
            normalized_env = {
                key.casefold(): value for key, value in captured["env"].items()
            }
            self.assertEqual(normalized_env["tf_var_foundation_kafka_api_key"], "key-id")
            self.assertEqual(captured["env"]["TF_LOG"], "OFF")
            self.assertIn("key-secret-value", captured["secrets"])


if __name__ == "__main__":
    unittest.main()
