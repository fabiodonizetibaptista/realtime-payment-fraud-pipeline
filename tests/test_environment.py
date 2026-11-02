import io
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


class EnvironmentTests(unittest.TestCase):
    def test_env_parser_reads_values_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# comment\nTOKEN='value with spaces'\nEMPTY=\n", encoding="utf-8")
            self.assertEqual(safety.load_env_file(path), {"TOKEN": "value with spaces", "EMPTY": ""})
    def test_env_parser_rejects_duplicate_keys_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TOKEN=first-secret\nTOKEN=second-secret\n", encoding="utf-8")
            with self.assertRaises(ValueError) as raised:
                safety.load_env_file(path)
            self.assertNotIn("first-secret", str(raised.exception))
            self.assertNotIn("second-secret", str(raised.exception))

    def test_nonempty_environment_secret_is_not_overwritten_by_empty_env_file_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("AIVEN_TOKEN=\nNEW_VALUE=from-file\n", encoding="utf-8")
            environment = {"AIVEN_TOKEN": "already-set-secret"}
            safety.merge_env_file(path, environment)
            self.assertEqual(environment["AIVEN_TOKEN"], "already-set-secret")
            self.assertEqual(environment["NEW_VALUE"], "from-file")

    def test_env_file_never_overwrites_an_existing_environment_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("EXISTING=from-file\n", encoding="utf-8")
            environment = {"EXISTING": ""}
            safety.merge_env_file(path, environment)
            self.assertEqual(environment["EXISTING"], "")

    def test_setup_does_not_create_optional_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            with patch.object(lab, "ENV_FILE", env_file), \
                 patch.object(lab, "_check_versions"), \
                 patch.object(lab, "run_command", return_value=""), \
                 patch.object(lab, "check_cli_help"), redirect_stdout(io.StringIO()):
                lab.setup()
            self.assertFalse(env_file.exists())


if __name__ == "__main__":
    unittest.main()
