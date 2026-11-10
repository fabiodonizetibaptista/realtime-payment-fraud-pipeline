"""Testes do executor da Etapa 11, sem acesso ao Confluent."""

import unittest
from unittest.mock import MagicMock, patch

from scripts import fraud_stream as executor


class Etapa11ExecutionTests(unittest.TestCase):

    def test_plan_loads_all_sql_files(self):
        for action in ("start", "inspect", "inspect-null"):
            with self.subTest(action=action):
                self.assertTrue(executor.load_sql(action).strip())

    def test_start_creates_nonblocking_statement(self):
        runtime = MagicMock()

        with (
            patch.object(
                executor, "statement_status",
                side_effect=["NOT_FOUND", "RUNNING"],
            ),
            patch.object(
                executor, "render_for_runtime",
                return_value="SQL_VALIDADA",
            ),
        ):
            executor.start(runtime)

        runtime.create_statement.assert_called_once_with(
            executor.STATEMENT_NAME,
            "SQL_VALIDADA",
            wait=False,
        )

    def test_start_accepts_initializing_state(self):
        runtime = MagicMock()

        with (
            patch.object(
                executor, "statement_status",
                side_effect=["NOT_FOUND", "PENDING"],
            ),
            patch.object(
                executor, "render_for_runtime",
                return_value="SQL_VALIDADA",
            ),
        ):
            executor.start(runtime)

        runtime.create_statement.assert_called_once()

    def test_running_statement_is_not_duplicated(self):
        runtime = MagicMock()

        with patch.object(
            executor, "statement_status",
            return_value="RUNNING",
        ):
            executor.start(runtime)

        runtime.create_statement.assert_not_called()

    def test_failed_statement_is_not_recreated(self):
        runtime = MagicMock()

        with patch.object(
            executor, "statement_status",
            return_value="FAILED",
        ):
            with self.assertRaises(executor.FlinkRuntimeError):
                executor.start(runtime)

        runtime.create_statement.assert_not_called()

    def test_inspection_uses_separate_query(self):
        runtime = MagicMock()
        runtime.query.return_value = [
            {
                "card_id": "TEST-CARD",
                "first_rowtime": "2026-11-09T12:00:00",
                "last_rowtime": "2026-11-09T12:00:30",
            }
        ]

        with patch.object(
            executor, "render_for_runtime",
            return_value="SELECT_LIMITADO",
        ):
            executor.inspect(runtime, "inspect")

        runtime.query.assert_called_once_with(
            "SELECT_LIMITADO",
            timeout=35,
        )


if __name__ == "__main__":
    unittest.main()
