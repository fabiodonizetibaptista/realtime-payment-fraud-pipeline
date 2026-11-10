"""Testes locais da Etapa 12, sem acessar o PostgreSQL."""

import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fraud_scenarios as scenarios


class Etapa12ScenarioTests(unittest.TestCase):

    def test_four_transactions_planned(self):
        self.assertEqual(len(scenarios.AMOUNTS), 4)

    def test_all_amounts_are_positive(self):
        self.assertTrue(
            all(float(value) > 0 for value in scenarios.AMOUNTS)
        )

    def test_plan_does_not_connect_to_database(self):
        output = io.StringIO()

        with (
            patch.object(
                scenarios, "connect",
                side_effect=AssertionError("DATABASE_ACCESSED"),
            ),
            patch.object(
                scenarios, "connector_in_state",
                side_effect=AssertionError("TERRAFORM_ACCESSED"),
            ),
            contextlib.redirect_stdout(output),
        ):
            scenarios.plan()

        result = output.getvalue()

        self.assertIn("TRANSACTION_COUNT=4", result)
        self.assertIn("FRAUD_SEQUENCE_TRANSACTIONS=3", result)
        self.assertIn("CLOUD_EXECUTION=False", result)

    def test_execute_requires_explicit_confirmation(self):
        with (
            patch("sys.argv", [
                "fraud_scenarios",
                "execute",
            ]),
            patch.object(
                scenarios,
                "execute",
                side_effect=AssertionError("EXECUTED_WITHOUT_CONFIRMATION"),
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as error:
                scenarios.main()

        self.assertNotEqual(error.exception.code, 0)

    def test_existing_manifest_prevents_reexecution(self):
        # Mesmo com execucao autorizada, um manifesto existente
        # impede repetir a ingestao acidentalmente.
        with (
            patch.object(scenarios.MANIFEST.__class__, "exists",
                         return_value=True),
            patch.object(
                scenarios, "connect",
                side_effect=AssertionError("DATABASE_ACCESSED"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "SCENARIO_ALREADY_RECORDED",
            ):
                scenarios.execute()

    def test_missing_connector_prevents_connection(self):
        with (
            patch.object(scenarios.MANIFEST.__class__, "exists",
                         return_value=False),
            patch.object(scenarios, "connector_in_state",
                         return_value=False),
            patch.object(
                scenarios, "connect",
                side_effect=AssertionError("DATABASE_ACCESSED"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CDC_CONNECTOR_NOT_IN_STATE",
            ):
                scenarios.execute()

    def test_script_contains_sequential_inserts(self):
        source = Path(scenarios.__file__).read_text(encoding="utf-8")

        self.assertIn("INSERT INTO public.transactions", source)
        self.assertIn("connection.commit()", source)
        self.assertIn("FRAUD_INTERVAL_UNDER_60S", source)
        self.assertIn("WATERMARK_CONFIRMATION=PENDING_FLINK", source)


if __name__ == "__main__":
    unittest.main()
