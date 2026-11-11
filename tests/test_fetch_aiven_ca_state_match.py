"""Testes sem cloud para gate de correspondencia do projeto Aiven."""
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import fetch_aiven_ca as ca


def result_for(project):
    return subprocess.CompletedProcess(
        args=["terraform", "show", "-json"],
        returncode=0,
        stdout=json.dumps({"values": {"root_module": {"resources": [
            {"address": "aiven_pg.payments", "values": {"project": project}}
        ]}}}),
        stderr="",
    )


class AivenStateMatchTests(unittest.TestCase):
    @patch.object(ca.subprocess, "run")
    def test_matching_project(self, run):
        run.return_value = result_for("fresh-project")
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "PASS")
        self.assertEqual(run.call_args.kwargs["cwd"], ca.ROOT / "infra" / "terraform")
        self.assertEqual(run.call_args.kwargs["env"]["TF_LOG"], "OFF")

    @patch.object(ca.subprocess, "run")
    def test_mismatch_is_blocked(self, run):
        run.return_value = result_for("old-project")
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "PROJECT_MISMATCH")

    @patch.object(ca.subprocess, "run")
    def test_missing_resource_is_blocked(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps({"values": {"root_module": {"resources": []}}}), ""
        )
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "POSTGRES_RESOURCE_MISSING")

    @patch.object(ca.subprocess, "run")
    def test_missing_state_is_blocked(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "private_error")
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "STATE_UNAVAILABLE")

    @patch.object(ca.subprocess, "run")
    def test_malformed_state_is_blocked(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "not-json", "")
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "STATE_UNAVAILABLE")

    @patch.object(ca.subprocess, "run")
    def test_timeout_is_blocked(self, run):
        run.side_effect = subprocess.TimeoutExpired(["terraform"], 30)
        self.assertEqual(ca._validate_aiven_project_state("fresh-project"), "STATE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
