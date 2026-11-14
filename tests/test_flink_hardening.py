import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.flink_runtime import (
    FlinkConfig,
    FlinkRuntime,
    FlinkRuntimeError,
)
from scripts.flink_setup import (
    STEPS,
    load_sql,
    validate_ddl,
)


class FlinkHardeningTests(unittest.TestCase):

    def test_all_versioned_ddls_match_their_contracts(self):
        for step in STEPS:
            with self.subTest(step=step.name):
                ddl = load_sql(step.ddl_file)
                self.assertTrue(validate_ddl(step, ddl))

    def test_rejects_wrong_target_table(self):
        step = STEPS[0]

        with self.assertRaises(FlinkRuntimeError):
            validate_ddl(
                step,
                "ALTER TABLE another_table ADD CONSTRAINT "
                "pk_accounts PRIMARY KEY (account_id) NOT ENFORCED;",
            )

    def test_rejects_wrong_primary_key(self):
        step = STEPS[0]

        with self.assertRaises(FlinkRuntimeError):
            validate_ddl(
                step,
                "ALTER TABLE `desafio-final`.`desafio-basic`."
                "`payments.public.accounts` "
                "ADD CONSTRAINT pk_accounts PRIMARY KEY "
                "(customer_id) NOT ENFORCED;",
            )

    def test_rejects_destructive_ddl(self):
        step = STEPS[0]

        with self.assertRaises(FlinkRuntimeError):
            validate_ddl(step, "DROP TABLE accounts;")

    def test_rejects_wrong_changelog_mode(self):
        step = STEPS[2]

        with self.assertRaises(FlinkRuntimeError):
            validate_ddl(
                step,
                "ALTER TABLE `desafio-final`.`desafio-basic`."
                "`payments.public.transactions` "
                "SET ('changelog.mode' = 'retract');",
            )

    def test_rejects_wrong_changelog_target(self):
        step = STEPS[2]

        with self.assertRaises(FlinkRuntimeError):
            validate_ddl(
                step,
                "ALTER TABLE `desafio-final`.`desafio-basic`."
                "`payments.public.accounts` "
                "SET ('changelog.mode' = 'append');",
            )

    def test_statement_phase_reads_nested_running_status(self):
        result = FlinkRuntime.statement_phase({
            "status": {"phase": "RUNNING"}
        })

        self.assertEqual(result, "RUNNING")

    def test_statement_phase_reads_completed_status(self):
        result = FlinkRuntime.statement_phase({
            "status": {"phase": "COMPLETED"}
        })

        self.assertEqual(result, "COMPLETED")

    def test_statement_wait_accepts_running_then_completed(self):
        config = FlinkConfig(
            "env-test", "lkc-test", "lfcp-test", "aws", "us-east-1"
        )

        runtime = FlinkRuntime(config, Mock())

        runtime.describe_statement = Mock(side_effect=[
            {"status": {"phase": "RUNNING"}},
            {"status": {"phase": "COMPLETED"}},
        ])

        result = runtime.wait_for_statement(
            "test_statement",
            timeout=30,
            poll_interval=0,
            clock=lambda: 0,
            sleep=lambda _: None,
        )

        self.assertEqual(
            FlinkRuntime.statement_phase(result),
            "COMPLETED",
        )

    def test_statement_wait_rejects_failed_statement(self):
        config = FlinkConfig(
            "env-test", "lkc-test", "lfcp-test", "aws", "us-east-1"
        )

        runtime = FlinkRuntime(config, Mock())

        runtime.describe_statement = Mock(return_value={
            "status": {"phase": "FAILED"}
        })

        with self.assertRaises(FlinkRuntimeError):
            runtime.wait_for_statement("test_statement")

    def test_statement_wait_rejects_unknown_phase(self):
        config = FlinkConfig(
            "env-test", "lkc-test", "lfcp-test", "aws", "us-east-1"
        )

        runtime = FlinkRuntime(config, Mock())

        runtime.describe_statement = Mock(return_value={
            "status": {"phase": "UNKNOWN"}
        })

        with self.assertRaises(FlinkRuntimeError):
            runtime.wait_for_statement("test_statement")

    def test_statement_wait_enforces_timeout(self):
        config = FlinkConfig(
            "env-test", "lkc-test", "lfcp-test", "aws", "us-east-1"
        )

        runtime = FlinkRuntime(config, Mock())

        runtime.describe_statement = Mock(return_value={
            "status": {"phase": "RUNNING"}
        })

        clock_values = iter([0, 11])

        with self.assertRaises(FlinkRuntimeError):
            runtime.wait_for_statement(
                "test_statement",
                timeout=10,
                clock=lambda: next(clock_values),
                sleep=lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
