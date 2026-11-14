"""Testes sem rede para os gates locais por fase."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts import check_configuration as mod


class ConfigurationCheckTests(unittest.TestCase):
    def test_foundation_does_not_require_pipeline_outputs(self):
        values = {key: "not-a-secret" for key in mod.PHASE_KEYS["foundation"]}
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.report("foundation", Path(tmp), values)
            self.assertEqual(rc, 0)
            self.assertIn("PRESENT_NOT_VERIFIED", out.getvalue())
            self.assertNotIn("not-a-secret", out.getvalue())

    def test_pipeline_lists_missing_output_names_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.report("pipeline", Path(tmp), {"AIVEN_TOKEN": "SENSITIVE_SAMPLE"})
            self.assertEqual(rc, 1)
            self.assertIn("TF_VAR_foundation_environment_id", out.getvalue())
            self.assertIn("export_foundation_env", out.getvalue())
            self.assertNotIn("SENSITIVE_SAMPLE", out.getvalue())

    def test_env_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("PGHOST=from_file\nPGPORT=5432\n", encoding="utf-8")
            found = mod.available_config(root, {"PGHOST": "from_process"})
            self.assertEqual(found["PGHOST"], "from_process")
            self.assertEqual(found["PGPORT"], "5432")

    def test_empty_template_values_do_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("AIVEN_TOKEN=  \n", encoding="utf-8")
            self.assertIn("AIVEN_TOKEN", mod.missing_keys("foundation", mod.available_config(root, {})))

    def test_invalid_env_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("BAD ROW WITH SECRET_SAMPLE\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.report("foundation", root, {})
            self.assertEqual(rc, 2)
            self.assertIn("INVALID_ENV_FILE", out.getvalue())
            self.assertNotIn("SECRET_SAMPLE", out.getvalue())

    def test_cdc_requires_dedicated_credentials(self):
        values = {key: "placeholder" for key in mod.PHASE_KEYS["postgres"]}
        missing = mod.missing_keys("cdc", values)
        self.assertEqual(set(missing), {"CDC_PGUSER", "CDC_PGPASSWORD", "TF_VAR_cdc_connector_password"})


if __name__ == "__main__":
    unittest.main()
