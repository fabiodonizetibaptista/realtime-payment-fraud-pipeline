"""Offline regression tests for portable Aiven CA configuration."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import fetch_aiven_ca


class AivenCAConfigTests(unittest.TestCase):
    def test_missing_project_blocks_before_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(fetch_aiven_ca, "ROOT", Path(directory)), \
             patch.object(fetch_aiven_ca, "load_env_file", return_value={"AIVEN_TOKEN": "SECRET-TEST"}), \
             patch.dict(os.environ, {"AIVEN_TOKEN": "SECRET-TEST"}, clear=True), \
             patch.object(fetch_aiven_ca.urllib.request, "urlopen") as urlopen:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(fetch_aiven_ca.main(), 1)
            self.assertIn("TF_VAR_aiven_project", output.getvalue())
            self.assertNotIn("SECRET-TEST", output.getvalue())
            urlopen.assert_not_called()

    def test_invalid_project_name_blocks_before_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(fetch_aiven_ca, "ROOT", Path(directory)), \
             patch.object(fetch_aiven_ca, "load_env_file", return_value={"AIVEN_TOKEN": "SECRET-TEST", "TF_VAR_aiven_project": "../wrong"}), \
             patch.dict(os.environ, {}, clear=True), \
             patch.object(fetch_aiven_ca.urllib.request, "urlopen") as urlopen:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(fetch_aiven_ca.main(), 1)
            self.assertIn("INVALID_PROJECT_NAME=True", output.getvalue())
            self.assertNotIn("SECRET-TEST", output.getvalue())
            urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
