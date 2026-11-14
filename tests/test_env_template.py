"""J0.1: .env.example renomeado para .env deve falhar com instrucao clara."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


class EnvTemplateTests(unittest.TestCase):
    def test_missing_template_explains_how_to_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                lab.require_env_template(Path(tmp) / ".env.example")
        message = str(ctx.exception)
        self.assertIn("ENV_TEMPLATE_MISSING", message)
        self.assertIn("git restore .env.example", message)
        self.assertIn("init-env", message)

    def test_present_template_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / ".env.example"
            template.write_text("KEY=\n", encoding="utf-8")
            lab.require_env_template(template)

    def test_setup_fails_before_terraform_with_verdict(self):
        stderr, stdout = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(lab, "ENV_TEMPLATE", Path(tmp) / ".env.example"), \
                patch.object(lab, "run_command") as run, \
                contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            code = lab.main(["setup"])
        self.assertEqual(code, 1)
        run.assert_not_called()
        self.assertIn("ENV_TEMPLATE_MISSING", stderr.getvalue())
        self.assertIn("RESULTADO: FALHOU", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
