"""Regressão do preflight global de metadados Flink."""

import unittest
from unittest.mock import patch

from scripts.flink_runtime import FlinkRuntimeError
from scripts.flink_setup import STEPS, preflight_tables, prepare_tables


class FakeRuntime:
    def __init__(self, accounts, transactions):
        self.definitions = {
            "accounts": accounts,
            "transactions": transactions,
        }
        self.created = []

    def query(self, sql):
        table = (
            "accounts" if "payments.public.accounts" in sql
            else "transactions"
        )
        return [{"create_table": self.definitions[table]}]

    def find_statement(self, name):
        return None

    def create_statement(self, name, sql, wait=True):
        self.created.append(name)

        if "accounts-pk" in name:
            self.definitions["accounts"] = (
                "CREATE TABLE accounts (account_id BIGINT, "
                "PRIMARY KEY (account_id) NOT ENFORCED)"
            )

        elif "transactions-pk" in name:
            self.definitions["transactions"] = (
                "CREATE TABLE transactions (transaction_id BIGINT, "
                "PRIMARY KEY (transaction_id) NOT ENFORCED)"
            )

        elif "transactions-append" in name:
            self.definitions["transactions"] += (
                " WITH ('changelog.mode' = 'append')"
            )

    def wait_for_statement(self, name):
        return {"status": {"phase": "COMPLETED"}}


class FlinkPreflightTests(unittest.TestCase):

    def test_conflict_in_second_table_prevents_first_mutation(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)",
            "CREATE TABLE transactions ("
            "PRIMARY KEY (other_id) NOT ENFORCED)",
        )

        with self.assertRaisesRegex(
            FlinkRuntimeError, "FLINK_PREFLIGHT_CONFLICT"
        ):
            prepare_tables(runtime)

        self.assertEqual(runtime.created, [])

    def test_global_preflight_detects_three_missing_properties(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)",
            "CREATE TABLE transactions (transaction_id BIGINT)",
        )

        plan = preflight_tables(runtime)

        self.assertEqual(len(plan), 3)
        self.assertEqual(
            [item["state"] for item in plan],
            ["MISSING", "MISSING", "MISSING"],
        )
        self.assertEqual(runtime.created, [])

    def test_already_configured_does_not_create_statements(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts ("
            "PRIMARY KEY (account_id) NOT ENFORCED)",
            "CREATE TABLE transactions ("
            "PRIMARY KEY (transaction_id) NOT ENFORCED)"
            " WITH ('changelog.mode' = 'append')",
        )

        result = prepare_tables(runtime)

        self.assertEqual(runtime.created, [])
        self.assertTrue(
            all(item["result"] == "ALREADY_CONFIGURED" for item in result)
        )

    def test_applies_all_missing_properties_after_preflight(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)",
            "CREATE TABLE transactions (transaction_id BIGINT)",
        )

        result = prepare_tables(runtime)

        self.assertEqual(len(runtime.created), 3)
        self.assertEqual(len(result), 3)
        self.assertTrue(
            all(item["result"] == "APPLIED" for item in result)
        )

    def test_invalid_ddl_blocks_all_mutations(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)",
            "CREATE TABLE transactions (transaction_id BIGINT)",
        )

        with patch(
            "scripts.flink_setup.validate_ddl",
            side_effect=FlinkRuntimeError("INVALID_DDL"),
        ):
            with self.assertRaises(FlinkRuntimeError):
                prepare_tables(runtime)

        self.assertEqual(runtime.created, [])


if __name__ == "__main__":
    unittest.main()
