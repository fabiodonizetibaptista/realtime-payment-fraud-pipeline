"""Testes locais da resolução de nomes e da renderização SQL."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.flink_runtime import FlinkConfig, FlinkRuntimeError
from scripts.flink_portability import (
    render_sql,
    render_for_runtime,
    resolve_names,
)


class FlinkPortabilityTests(unittest.TestCase):

    def test_renders_sql_using_new_environment_names(self):
        sql = (
            "SHOW CREATE TABLE `desafio-final`.`desafio-basic`."
            "`payments.public.accounts`;"
        )

        result = render_sql(sql, "meu-ambiente", "meu-cluster")

        self.assertIn(
            "`meu-ambiente`.`meu-cluster`",
            result,
        )
        self.assertNotIn("`desafio-final`", result)

    def test_preserves_topic_name(self):
        sql = (
            "ALTER TABLE `desafio-final`.`desafio-basic`."
            "`payments.public.transactions` "
            "SET ('changelog.mode' = 'append');"
        )

        result = render_sql(sql, "novo-env", "novo-cluster")

        self.assertIn("`payments.public.transactions`", result)

    def test_rejects_unexpected_sql_prefix(self):
        with self.assertRaises(FlinkRuntimeError):
            render_sql(
                "DROP TABLE random_table;",
                "meu-env",
                "meu-cluster",
            )

    def test_rejects_invalid_sql_identifier(self):
        sql = (
            "SHOW CREATE TABLE `desafio-final`.`desafio-basic`."
            "`payments.public.accounts`;"
        )

        with self.assertRaises(FlinkRuntimeError):
            render_sql(sql, "ambiente`invalido", "cluster")

    def test_resolves_names_using_resource_ids(self):
        config = FlinkConfig(
            "env-123",
            "lkc-456",
            "lfcp-789",
            "aws",
            "us-east-1",
        )

        state = {
            "resources": [
                {
                    "type": "confluent_environment",
                    "instances": [{
                        "attributes": {
                            "id": "env-123",
                            "display_name": "ambiente-novo",
                        }
                    }],
                },
                {
                    "type": "confluent_kafka_cluster",
                    "instances": [{
                        "attributes": {
                            "id": "lkc-456",
                            "display_name": "cluster-novo",
                        }
                    }],
                },
            ],
        }

        runner = Mock(return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps(state),
            stderr="",
        ))

        catalog, database = resolve_names(config, runner)

        self.assertEqual(catalog, "ambiente-novo")
        self.assertEqual(database, "cluster-novo")
        self.assertEqual(runner.call_count, 1)

    def test_fails_closed_when_name_is_missing(self):
        config = FlinkConfig(
            "env-123",
            "lkc-456",
            "lfcp-789",
            "aws",
            "us-east-1",
        )

        runner = Mock(return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"resources": []}),
            stderr="",
        ))

        with self.assertRaises(FlinkRuntimeError):
            resolve_names(config, runner)

    def test_query_flags_prefer_database_name(self):
        config = FlinkConfig(
            "env-123",
            "lkc-456",
            "lfcp-789",
            "aws",
            "us-east-1",
            catalog_name="ambiente-novo",
            database_name="cluster-novo",
        )

        flags = config.query_flags()
        database_index = flags.index("--database")

        self.assertEqual(flags[database_index + 1], "cluster-novo")

    def test_runtime_without_names_fails_closed(self):
        sql = (
            "SHOW CREATE TABLE `desafio-final`.`desafio-basic`."
            "`payments.public.accounts`;"
        )

        runtime = SimpleNamespace(config=FlinkConfig(
            "env-123",
            "lkc-456",
            "lfcp-789",
            "aws",
            "us-east-1",
        ))

        with self.assertRaises(FlinkRuntimeError):
            render_for_runtime(sql, runtime)


if __name__ == "__main__":
    unittest.main()
