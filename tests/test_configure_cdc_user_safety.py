"""Regressões locais do usuário CDC; sem acesso a Aiven ou PostgreSQL."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import configure_cdc_user as cdc


class CDCUserSafetyTests(unittest.TestCase):
    def test_help_does_not_call_main(self):
        with patch.object(cdc, "main") as main, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cdc.cli(["--help"])
            self.assertEqual(raised.exception.code, 0)
            main.assert_not_called()

    def test_no_args_does_not_call_main(self):
        with patch.object(cdc, "main") as main, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cdc.cli([])
            self.assertNotEqual(raised.exception.code, 0)
            main.assert_not_called()

    def test_check_is_explicit(self):
        with patch.object(cdc, "main", return_value=0) as main:
            self.assertEqual(cdc.cli(["--check"]), 0)
            main.assert_called_once_with("--check")

    def test_apply_is_explicit(self):
        with patch.object(cdc, "main", return_value=0) as main:
            self.assertEqual(cdc.cli(["--apply"]), 0)
            main.assert_called_once_with("--apply")

    def test_windows_compatible_save_preserves_other_values_and_replaces_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            target.write_text("PGDATABASE=defaultdb\nCDC_PGUSER=cdc_user\nCDC_PGPASSWORD=\nTF_VAR_cdc_connector_password=\n", encoding="utf-8")
            with patch.object(cdc, "ENV_PATH", target):
                cdc._save_credentials("test_dummy_password")
            data = target.read_text(encoding="utf-8")
            self.assertIn("PGDATABASE=defaultdb", data)
            self.assertEqual(data.count("CDC_PGUSER="), 1)
            self.assertEqual(data.count("CDC_PGPASSWORD="), 1)
            self.assertEqual(data.count("TF_VAR_cdc_connector_password="), 1)
            self.assertIn("CDC_PGPASSWORD=test_dummy_password", data)
            self.assertIn("TF_VAR_cdc_connector_password=test_dummy_password", data)

    def test_repeated_save_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            target.write_text("PGDATABASE=defaultdb\n", encoding="utf-8")
            with patch.object(cdc, "ENV_PATH", target):
                cdc._save_credentials("test_dummy_password")
                first = target.read_text(encoding="utf-8")
                cdc._save_credentials("test_dummy_password")
                self.assertEqual(target.read_text(encoding="utf-8"), first)

    def test_process_conflict_blocks_without_leaking_value(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            target.write_text("PGHOST=current.example\nPGPORT=5432\nPGDATABASE=defaultdb\nPGUSER=admin\nPGPASSWORD=test_dummy_password\nPG_CA=dummy\n", encoding="utf-8")
            with patch.object(cdc, "ENV_PATH", target), patch.object(cdc, "GRANTS_PATH", Path(folder) / "grants.sql"):
                with patch.dict(cdc.os.environ, {"PGHOST": "old-host.example"}):
                    with self.assertRaisesRegex(RuntimeError, "POSTGRES_ENV_CONFLICT:PGHOST") as raised:
                        cdc._config()
            self.assertNotIn("old-host.example", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
