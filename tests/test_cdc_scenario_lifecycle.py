"""Cenario CDC: baseline antes de qualquer mutacao e verificacao no final."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.cdc_test_scenario as scenario


class CdcScenarioLifecycleTests(unittest.TestCase):
    def test_baseline_failure_blocks_before_database_connection(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(scenario, "RESULT_FILE", Path(tmp) / "r.json"), \
             patch.object(scenario, "connector_in_state", return_value=True), \
             patch.object(scenario, "run_lifecycle", return_value=1) as lifecycle, \
             patch.object(scenario, "connect") as connect, \
             patch.object(sys, "argv", ["cdc_test_scenario.py", "--execute"]):
            with self.assertRaisesRegex(RuntimeError, "LIFECYCLE_BASELINE_FAILED"):
                scenario.main()
        lifecycle.assert_called_once_with("--baseline")
        connect.assert_not_called()

    def test_check_mode_does_not_touch_lifecycle(self):
        with patch.object(scenario, "run_lifecycle") as lifecycle, \
             patch.object(scenario, "connect", side_effect=RuntimeError("STOP")), \
             patch.object(sys, "argv", ["cdc_test_scenario.py", "--check"]):
            with self.assertRaises(RuntimeError):
                scenario.main()
        lifecycle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
