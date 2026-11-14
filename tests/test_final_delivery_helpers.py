"""Evidencia por execucao, senha CDC e --help seguro, sem nuvem."""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from safety import evidence_path
from scripts.check_configuration import report

ROOT = Path(__file__).resolve().parents[1]

CDC_BASE = {
    "PGHOST": "h", "PGPORT": "1", "PGDATABASE": "d", "PGUSER": "u",
    "PGPASSWORD": "admin-pass", "PG_CA": "ca.pem", "CDC_PGUSER": "cdc_user",
}


class EvidencePathTests(unittest.TestCase):
    def test_without_run_id_keeps_historical_path(self):
        self.assertEqual(
            evidence_path(ROOT, "cdc/x.json", {}),
            ROOT / "evidencias" / "cdc" / "x.json",
        )

    def test_run_id_isolates_execution(self):
        self.assertEqual(
            evidence_path(ROOT, "cdc/x.json", {"EVIDENCE_RUN_ID": "run-20261112"}),
            ROOT / "evidencias" / "runs" / "run-20261112" / "cdc" / "x.json",
        )

    def test_invalid_run_id_or_traversal_is_rejected(self):
        for run_id in ("../x", "a/b", "-x", "x" * 65):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                evidence_path(ROOT, "cdc", {"EVIDENCE_RUN_ID": run_id})
        with self.assertRaises(ValueError):
            evidence_path(ROOT, "../fora", {})


class CdcPasswordMatchTests(unittest.TestCase):
    def run_report(self, cdc_password, connector_password):
        environment = {
            **CDC_BASE,
            "CDC_PGPASSWORD": cdc_password,
            "TF_VAR_cdc_connector_password": connector_password,
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(output):
            code = report("cdc", Path(tmp), environment)
        return code, output.getvalue()

    def test_match_passes_without_printing_values(self):
        code, text = self.run_report("Segredo-CDC-123", "Segredo-CDC-123")
        self.assertEqual(code, 0)
        self.assertIn("CDC_PASSWORD_MATCH=True", text)
        self.assertNotIn("Segredo-CDC-123", text)

    def test_mismatch_blocks_without_printing_values(self):
        code, text = self.run_report("Segredo-CDC-123", "Outro-Valor-456")
        self.assertEqual(code, 1)
        self.assertIn("CDC_PASSWORD_MATCH=False", text)
        self.assertIn("CONFIG_STATUS=CDC_PASSWORD_MISMATCH", text)
        self.assertNotIn("Segredo-CDC-123", text)
        self.assertNotIn("Outro-Valor-456", text)


class SafeHelpTests(unittest.TestCase):
    SCRIPTS = (
        "scripts/verify_schema_compatibility.py",
        "scripts/apply_schema_compatibility_policy.py",
        "scripts/verify_and_teardown_cdc.py",
        "scripts/collect_schema_evidence.py",
    )

    def test_help_exits_before_any_action(self):
        for script in self.SCRIPTS:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, script, "--help"], cwd=ROOT,
                    capture_output=True, text=True, timeout=60, check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn("usage:", result.stdout)
                self.assertNotIn("GATE", result.stdout)
                self.assertNotIn("ERROR_TYPE", result.stdout)


if __name__ == "__main__":
    unittest.main()
