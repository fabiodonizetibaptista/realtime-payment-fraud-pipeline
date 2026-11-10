import tempfile
import unittest
from pathlib import Path

from scripts.flink_setup import (
    DDLStep,
    assess_definition,
    apply_step,
    load_sql,
)
from scripts.flink_runtime import FlinkRuntimeError


class FakeRuntime:

    def __init__(self, definition, existing=None):
        self.definition = definition
        self.existing = existing
        self.created = []
        self.waited = []

    def query(self, sql):
        return [{"create_table": self.definition}]

    def find_statement(self, name):
        return self.existing

    @staticmethod
    def statement_phase(statement):
        return FlinkRuntimeStatementPhase(statement)

    def create_statement(self, name, sql, wait=True):
        self.created.append((name, sql, wait))

        if "accounts-pk" in name:
            self.definition = (
                "CREATE TABLE accounts (account_id BIGINT, "
                "PRIMARY KEY (account_id) NOT ENFORCED)"
            )
        elif "transactions-pk" in name:
            self.definition = (
                "CREATE TABLE transactions (transaction_id BIGINT, "
                "PRIMARY KEY (transaction_id) NOT ENFORCED)"
            )
        elif "transactions-append" in name:
            self.definition = (
                "CREATE TABLE transactions (transaction_id BIGINT, "
                "PRIMARY KEY (transaction_id) NOT ENFORCED) "
                "WITH ('changelog.mode' = 'append')"
            )

    def wait_for_statement(self, name):
        self.waited.append(name)
        return {"status": "COMPLETED"}


def FlinkRuntimeStatementPhase(statement):
    if isinstance(statement, dict):
        status = statement.get("status")
        if isinstance(status, dict):
            return status.get("phase")
        if isinstance(status, str):
            return status.upper()
    return None


def step(kind="primary_key", expected="account_id"):
    return DDLStep(
        name="payment-fraud-setup-accounts-pk",
        table="accounts",
        inspect_file="sql/enrichment/07_show_create_accounts.sql",
        ddl_file="sql/enrichment/accounts_primary_key.sql",
        kind=kind,
        expected=expected,
    )


class FlinkSetupTests(unittest.TestCase):

    def test_accepts_existing_primary_key(self):
        definition = (
            "CREATE TABLE accounts (account_id BIGINT, "
            "PRIMARY KEY (account_id) NOT ENFORCED)"
        )

        self.assertEqual(
            assess_definition(definition, step()),
            "PRESENT",
        )

    def test_detects_missing_primary_key(self):
        self.assertEqual(
            assess_definition(
                "CREATE TABLE accounts (account_id BIGINT)",
                step(),
            ),
            "MISSING",
        )

    def test_detects_conflicting_primary_key(self):
        definition = (
            "CREATE TABLE accounts (account_id BIGINT, "
            "PRIMARY KEY (customer_id) NOT ENFORCED)"
        )

        self.assertEqual(
            assess_definition(definition, step()),
            "CONFLICT",
        )

    def test_accepts_append_changelog(self):
        definition = (
            "CREATE TABLE transactions "
            "WITH ('changelog.mode' = 'append')"
        )

        self.assertEqual(
            assess_definition(
                definition,
                step("changelog", "append"),
            ),
            "PRESENT",
        )

    def test_detects_missing_changelog_mode(self):
        self.assertEqual(
            assess_definition(
                "CREATE TABLE transactions (transaction_id BIGINT)",
                step("changelog", "append"),
            ),
            "MISSING",
        )

    def test_detects_conflicting_changelog_mode(self):
        definition = (
            "CREATE TABLE transactions "
            "WITH ('changelog.mode' = 'retract')"
        )

        self.assertEqual(
            assess_definition(
                definition,
                step("changelog", "append"),
            ),
            "CONFLICT",
        )

    def test_skips_existing_primary_key_without_creating_statement(self):
        definition = (
            "CREATE TABLE accounts (account_id BIGINT, "
            "PRIMARY KEY (account_id) NOT ENFORCED)"
        )

        runtime = FakeRuntime(definition)

        result = apply_step(runtime, step())

        self.assertEqual(result, "ALREADY_CONFIGURED")
        self.assertEqual(runtime.created, [])

    def test_applies_missing_primary_key_and_verifies_result(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)"
        )

        result = apply_step(runtime, step())

        self.assertEqual(result, "APPLIED")
        self.assertEqual(len(runtime.created), 1)
        self.assertEqual(len(runtime.waited), 1)

    def test_rejects_conflicting_primary_key_without_mutation(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts "
            "(PRIMARY KEY (customer_id) NOT ENFORCED)"
        )

        with self.assertRaises(FlinkRuntimeError):
            apply_step(runtime, step())

        self.assertEqual(runtime.created, [])

    def test_rejects_previous_completed_statement_without_schema_change(self):
        runtime = FakeRuntime(
            "CREATE TABLE accounts (account_id BIGINT)",
            existing={"status": "COMPLETED"},
        )

        with self.assertRaises(FlinkRuntimeError):
            apply_step(runtime, step())

        self.assertEqual(runtime.created, [])

    def test_load_sql_extracts_ddl_and_ignores_read_only_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.sql"
            path.write_text(
                "-- comment\n"
                "ALTER TABLE accounts ADD CONSTRAINT pk_accounts "
                "PRIMARY KEY (account_id) NOT ENFORCED;\n"
                "DESCRIBE accounts;\n",
                encoding="utf-8",
            )

            # Test the SQL parsing contract using a temporary repository root.
            import scripts.flink_setup as setup
            original_root = setup.ROOT

            try:
                setup.ROOT = Path(directory)
                path.write_text(
                    "-- comment\n"
                    "ALTER TABLE accounts ADD CONSTRAINT pk_accounts "
                    "PRIMARY KEY (account_id) NOT ENFORCED;\n"
                    "DESCRIBE accounts;\n",
                    encoding="utf-8",
                )
                result = load_sql("sample.sql")
            finally:
                setup.ROOT = original_root

            self.assertTrue(result.startswith("ALTER TABLE"))
            self.assertNotIn("DESCRIBE", result)

    def test_rejects_multiple_mutating_sql_statements(self):
        with tempfile.TemporaryDirectory() as directory:
            import scripts.flink_setup as setup
            original_root = setup.ROOT

            try:
                setup.ROOT = Path(directory)
                (Path(directory) / "invalid.sql").write_text(
                    "ALTER TABLE a SET ('x' = 'y'); "
                    "DROP TABLE b;",
                    encoding="utf-8",
                )

                with self.assertRaises(FlinkRuntimeError):
                    load_sql("invalid.sql")
            finally:
                setup.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
