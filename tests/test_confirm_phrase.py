"""Confirmacao com ate 3 tentativas, comparacao exata."""
import contextlib
import io
import unittest
from unittest.mock import patch

import lab


def ask(answers):
    output = io.StringIO()
    with patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(output):
        result = lab.confirm_phrase("DESTROY PIPELINE", "confirmar")
    return result, output.getvalue()


class ConfirmPhraseTests(unittest.TestCase):
    def test_first_try(self):
        self.assertEqual(ask(["DESTROY PIPELINE"])[0], True)

    def test_typo_then_correct(self):
        result, text = ask(["DESTROY PIPELIEN", "DESTROY PIPELINE"])
        self.assertTrue(result)
        self.assertIn("tentativa 2 de 3", text)

    def test_surrounding_spaces_ignored_but_not_case_or_partial(self):
        self.assertTrue(ask(["  DESTROY PIPELINE \n"])[0])
        self.assertFalse(ask(["destroy pipeline", "DESTROY", "DESTROY  PIPELINE"])[0])

    def test_three_failures_cancel(self):
        result, text = ask(["x", "y", "z"])
        self.assertFalse(result)
        self.assertIn("tentativa 3 de 3", text)

    def test_end_of_input_cancels(self):
        self.assertFalse(ask(EOFError())[0])


if __name__ == "__main__":
    unittest.main()
