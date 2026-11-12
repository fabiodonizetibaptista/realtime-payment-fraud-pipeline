"""lab.py termina com RESULTADO inequivoco e codigo de saida encadeavel."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab


def run(argv, **patches):
    output = io.StringIO()
    with contextlib.ExitStack() as stack:
        for name, value in patches.items():
            stack.enter_context(patch.object(lab, name, value))
        stack.enter_context(contextlib.redirect_stdout(output))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        code = lab.main(argv)
    return code, output.getvalue().strip().splitlines()[-1]


class VerdictTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(run(["plan"], plan=lambda: None), (0, "RESULTADO: OK"))

    def test_failure(self):
        def boom():
            raise RuntimeError("X")
        code, last = run(["plan"], plan=boom)
        self.assertEqual(code, 1)
        self.assertTrue(last.startswith("RESULTADO: FALHOU"))

    def test_cancel(self):
        code, last = run(["teardown", "--confirm-destroy"], teardown=lambda confirm: lab.CANCELLED)
        self.assertEqual(code, 2)
        self.assertTrue(last.startswith("RESULTADO: CANCELADO"))

    def test_failed_pipeline_plan_removes_partial_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            def failing(command, **kwargs):
                (directory / "pipeline.tfplan").write_text("partial")
                raise RuntimeError("PROVIDER")

            with patch.object(lab, "TF_DIR", directory), patch.object(lab, "merge_env_file"), \
                 patch.object(lab, "secret_values", return_value=[]), \
                 patch.object(lab, "run_command", side_effect=failing):
                with self.assertRaisesRegex(RuntimeError, "PIPELINE_PLAN_FAILED"):
                    lab.plan_pipeline()
            self.assertFalse((directory / "pipeline.tfplan").exists())


if __name__ == "__main__":
    unittest.main()
