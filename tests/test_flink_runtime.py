import json
import subprocess
import unittest
from unittest.mock import Mock

from scripts.flink_runtime import (
    FlinkConfig,
    FlinkRuntime,
    FlinkRuntimeError,
    ROOT,
    load_config,
)


def completed(args, stdout="{}", returncode=0):
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def sample_state():
    return {
        "resources": [
            {
                "mode": "managed",
                "type": "confluent_environment",
                "instances": [
                    {"attributes": {"id": "env-test"}}
                ],
            },
            {
                "mode": "managed",
                "type": "confluent_kafka_cluster",
                "instances": [
                    {"attributes": {"id": "lkc-test"}}
                ],
            },
            {
                "mode": "managed",
                "type": "confluent_flink_compute_pool",
                "instances": [
                    {
                        "attributes": {
                            "id": "lfcp-test",
                            "cloud": "AWS",
                            "region": "us-east-1",
                        }
                    }
                ],
            },
        ]
    }


class FlinkRuntimeTests(unittest.TestCase):

    def setUp(self):
        self.config = FlinkConfig(
            environment_id="env-test",
            kafka_cluster_id="lkc-test",
            compute_pool_id="lfcp-test",
            cloud="aws",
            region="us-east-1",
        )

    def test_root_is_independent_of_current_directory(self):
        self.assertTrue((ROOT / "infra" / "terraform").is_dir())

    def test_loads_configuration_from_terraform_state(self):
        runner = Mock(
            return_value=completed(
                ["terraform", "state", "pull"],
                json.dumps(sample_state()),
            )
        )

        config = load_config(command_runner=runner)

        self.assertEqual(config.environment_id, "env-test")
        self.assertEqual(config.kafka_cluster_id, "lkc-test")
        self.assertEqual(config.compute_pool_id, "lfcp-test")
        self.assertEqual(config.cloud, "aws")
        self.assertEqual(config.region, "us-east-1")

        args = runner.call_args.args[0]
        self.assertEqual(args, ["terraform", "state", "pull"])

    def test_rejects_missing_terraform_resource(self):
        state = sample_state()
        state["resources"].pop()

        runner = Mock(
            return_value=completed(
                ["terraform", "state", "pull"],
                json.dumps(state),
            )
        )

        with self.assertRaises(FlinkRuntimeError):
            load_config(command_runner=runner)

    def test_rejects_duplicate_terraform_resources(self):
        state = sample_state()
        state["resources"].append(state["resources"][0])

        runner = Mock(
            return_value=completed(
                ["terraform", "state", "pull"],
                json.dumps(state),
            )
        )

        with self.assertRaises(FlinkRuntimeError):
            load_config(command_runner=runner)

    def test_rejects_failed_terraform_state_pull(self):
        runner = Mock(
            return_value=completed(
                ["terraform", "state", "pull"],
                returncode=1,
            )
        )

        with self.assertRaises(FlinkRuntimeError):
            load_config(command_runner=runner)

    def test_create_statement_uses_shared_configuration(self):
        runner = Mock(
            return_value=completed(
                ["confluent", "flink", "statement", "create"]
            )
        )

        runtime = FlinkRuntime(self.config, runner)

        result = runtime.create_statement(
            "test_accounts_ddl",
            "ALTER TABLE accounts ADD CONSTRAINT pk_accounts "
            "PRIMARY KEY (account_id) NOT ENFORCED",
        )

        self.assertTrue(result)

        args = runner.call_args.args[0]

        self.assertEqual(args[:5], [
            "confluent",
            "flink",
            "statement",
            "create",
            "test_accounts_ddl",
        ])

        self.assertIn("--wait", args)
        self.assertIn("--compute-pool", args)
        self.assertIn("lfcp-test", args)
        self.assertIn("--environment", args)
        self.assertIn("env-test", args)
        self.assertIn("--region", args)
        self.assertIn("us-east-1", args)

        self.assertNotIn("--unsafe-trace", args)

    def test_create_statement_without_wait(self):
        runner = Mock(
            return_value=completed(
                ["confluent", "flink", "statement", "create"]
            )
        )

        runtime = FlinkRuntime(self.config, runner)

        runtime.create_statement(
            "test_statement",
            "SELECT 1",
            wait=False,
        )

        args = runner.call_args.args[0]
        self.assertNotIn("--wait", args)

    def test_rejects_invalid_statement_name(self):
        runtime = FlinkRuntime(self.config, Mock())

        with self.assertRaises(FlinkRuntimeError):
            runtime.create_statement(
                "invalid statement name",
                "SELECT 1",
            )

    def test_rejects_empty_sql(self):
        runtime = FlinkRuntime(self.config, Mock())

        with self.assertRaises(FlinkRuntimeError):
            runtime.create_statement("test_statement", " ")

    def test_describe_statement_parses_json(self):
        runner = Mock(
            return_value=completed(
                ["confluent", "flink", "statement", "describe"],
                json.dumps({"name": "test_statement", "status": "RUNNING"}),
            )
        )

        runtime = FlinkRuntime(self.config, runner)
        result = runtime.describe_statement("test_statement")

        self.assertEqual(result["name"], "test_statement")
        self.assertEqual(result["status"], "RUNNING")

    def test_bounded_query_parses_json_rows(self):
        rows = [{"account_id": 1}, {"account_id": 2}]

        runner = Mock(
            return_value=completed(
                ["confluent", "flink", "query"],
                json.dumps(rows),
            )
        )

        runtime = FlinkRuntime(self.config, runner)
        result = runtime.query("SELECT account_id FROM accounts")

        self.assertEqual(result, rows)

        args = runner.call_args.args[0]
        self.assertIn("query", args)
        self.assertIn("--output", args)
        self.assertIn("json", args)

    def test_rejects_invalid_query_response(self):
        runner = Mock(
            return_value=completed(
                ["confluent", "flink", "query"],
                '{"unexpected": true}',
            )
        )

        runtime = FlinkRuntime(self.config, runner)

        with self.assertRaises(FlinkRuntimeError):
            runtime.query("SELECT 1")

    def test_failed_cli_command_does_not_expose_stderr(self):
        runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["confluent"],
                returncode=1,
                stdout="",
                stderr="sensitive diagnostic content",
            )
        )

        runtime = FlinkRuntime(self.config, runner)

        with self.assertRaises(FlinkRuntimeError) as context:
            runtime.query("SELECT 1")

        self.assertNotIn(
            "sensitive diagnostic content",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
