"""Regressao offline: --help nao acessa credenciais nem a API Aiven."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import fetch_aiven_ca


class AivenCAHelpTests(unittest.TestCase):
    def test_help_does_not_read_env_or_call_network(self):
        output = io.StringIO()
        with (
            patch.object(fetch_aiven_ca, "load_env_file") as load_env,
            patch.object(fetch_aiven_ca.urllib.request, "urlopen") as request,
            redirect_stdout(output),
            self.assertRaises(SystemExit) as exit_result,
        ):
            fetch_aiven_ca.cli(["--help"])

        self.assertEqual(exit_result.exception.code, 0)
        self.assertIn("usage:", output.getvalue())
        self.assertNotIn("AIVEN_TOKEN_AVAILABLE", output.getvalue())
        load_env.assert_not_called()
        request.assert_not_called()

    def test_no_arguments_runs_existing_main(self):
        with patch.object(fetch_aiven_ca, "main", return_value=0) as main:
            self.assertEqual(fetch_aiven_ca.cli([]), 0)
        main.assert_called_once_with()

    def test_unknown_argument_does_not_run_main(self):
        with patch.object(fetch_aiven_ca, "main") as main:
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                fetch_aiven_ca.cli(["--unknown"])
        self.assertEqual(result.exception.code, 2)
        main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
