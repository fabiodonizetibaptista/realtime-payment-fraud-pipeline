"""Testes locais para o preflight portavel, sem CLI ou rede reais."""
import json
import subprocess
import unittest
from unittest.mock import patch
from scripts import check_environment as mod


class CheckEnvironmentTests(unittest.TestCase):
    def test_parses_version(self):
        self.assertEqual(mod.parse_version("Terraform v1.16.2"), (1, 16, 2))
        self.assertIsNone(mod.parse_version("unknown"))

    def test_checks_minimum_versions(self):
        self.assertEqual(mod.check_status((4, 81, 0), (4, 81, 0)), "OK")
        self.assertEqual(mod.check_status((4, 80, 9), (4, 81, 0)), "BELOW_MINIMUM")
        self.assertEqual(mod.check_status(None, (4, 81, 0)), "MISSING_OR_UNAVAILABLE")

    @patch.object(mod.shutil, "which", return_value=None)
    def test_missing_cli_never_invokes_process(self, _which):
        with patch.object(mod.subprocess, "run") as runner:
            self.assertIsNone(mod.tool_version("confluent", ["version"]))
            runner.assert_not_called()

    @patch.object(mod.shutil, "which", return_value="terraform")
    def test_parses_terraform_json(self, _which):
        completed = subprocess.CompletedProcess(
            args=["terraform"], returncode=0,
            stdout=json.dumps({"terraform_version": "1.16.2"}), stderr="",
        )
        with patch.object(mod.subprocess, "run", return_value=completed):
            self.assertEqual(mod.tool_version("terraform", ["version", "-json"], "terraform_version"), (1, 16, 2))

    @patch.object(mod.shutil, "which", return_value="confluent")
    def test_failed_tool_does_not_print_stderr(self, _which):
        completed = subprocess.CompletedProcess(
            args=["confluent"], returncode=1,
            stdout="", stderr="SECRET_SHOULD_NOT_BE_LOGGED",
        )
        with patch.object(mod.subprocess, "run", return_value=completed):
            self.assertIsNone(mod.tool_version("confluent", ["version"]))


if __name__ == "__main__":
    unittest.main()
