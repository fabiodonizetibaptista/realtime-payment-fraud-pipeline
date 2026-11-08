import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_foundation_env


class FoundationExportTests(unittest.TestCase):
    def test_exports_secrets_to_private_env_without_printing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            env_file.write_text("AIVEN_TOKEN=preserve-this-token\n", encoding="utf-8")
            export_foundation_env.ENV_FILE = env_file
            export_foundation_env.TF_DIR = root / "infra" / "terraform"

            values = {
                output_name: f"safe-test-value-{index}"
                for index, output_name in enumerate(export_foundation_env.OUTPUT_TO_ENV)
            }
            payload = {name: {"value": value, "sensitive": "secret" in name} for name, value in values.items()}
            # O exportador exige o ID da Service Account CDC.
            # Utilizamos um identificador ficticio neste teste.
            payload["service_account_ids"] = {
                "value": {"cdc": "sa-test-cdc"}
            }
            captured = io.StringIO()
            with patch.object(
                export_foundation_env.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
            ), redirect_stdout(captured):
                result = export_foundation_env.main()

            self.assertEqual(result, 0)
            self.assertNotIn("safe-test-value", captured.getvalue())
            written = env_file.read_text(encoding="utf-8")
            self.assertIn("AIVEN_TOKEN=preserve-this-token", written)
            self.assertIn("TF_VAR_enable_kafka_acls=false", written)
            for env_name in export_foundation_env.OUTPUT_TO_ENV.values():
                self.assertIn(f"{env_name}=", written)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)

    def test_failed_terraform_output_does_not_echo_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            export_foundation_env.ENV_FILE = Path(directory) / ".env"
            export_foundation_env.TF_DIR = Path(directory)
            captured = io.StringIO()
            with patch.object(
                export_foundation_env.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=1, stdout="", stderr="sensitive-provider-detail"),
            ), redirect_stdout(captured), redirect_stderr(io.StringIO()):
                result = export_foundation_env.main()
            self.assertEqual(result, 1)
            self.assertNotIn("sensitive-provider-detail", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
