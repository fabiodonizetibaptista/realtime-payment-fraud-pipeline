"""Regression: preserve exact Terraform TF_VAR casing on Windows."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


class WindowsStyleEnvironment(dict):
    """Mimic Windows os.environ normalizing inserted keys to uppercase."""

    def __setitem__(self, key, value):
        super().__setitem__(key.upper(), value)


class WindowsTerraformEnvironmentTests(unittest.TestCase):
    def test_plan_passes_exact_tf_var_names_to_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            env_path = Path(folder) / ".env"
            env_path.write_text("TF_VAR_aiven_project=example-project\n", encoding="utf-8")
            windows_env = WindowsStyleEnvironment()
            with (
                patch.object(lab, "ENV_FILE", env_path),
                patch.object(lab.os, "environ", windows_env),
                patch.object(lab, "run_command") as execute,
            ):
                lab.plan()
            passed_env = execute.call_args.kwargs["env"]
            self.assertEqual(passed_env["TF_VAR_aiven_project"], "example-project")
            self.assertNotIn("TF_VAR_AIVEN_PROJECT", passed_env)
            self.assertEqual(passed_env["TF_LOG"], "OFF")
            self.assertEqual(windows_env, {})  # No process-global mutation.


if __name__ == "__main__":
    unittest.main()
