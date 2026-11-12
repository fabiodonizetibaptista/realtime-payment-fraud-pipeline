"""Remocao de statements Flink com escopo explicito, sem nuvem."""
import json
import unittest
from types import SimpleNamespace

from scripts.flink_runtime import FlinkConfig, FlinkRuntime, FlinkRuntimeError

CONFIG = FlinkConfig("env-x", "lkc-x", "lfcp-x", "aws", "us-east-1")


class FakeCli:
    def __init__(self, names, sticky=()):
        self.names, self.sticky, self.calls = list(names), set(sticky), []

    def __call__(self, args, timeout=None, cwd=None):
        self.calls.append(args)
        if args[3] == "list":
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"name": n} for n in self.names]))
        if args[3] == "delete":
            if args[4] not in self.sticky:
                self.names.remove(args[4])
            return SimpleNamespace(returncode=0, stdout="")
        raise AssertionError(args)


class StatementCleanupTests(unittest.TestCase):
    def test_deletes_all_with_explicit_scope(self):
        cli = FakeCli(["etapa11-fraud-pattern-matches", "cli-query-1"])
        self.assertEqual(FlinkRuntime(CONFIG, cli).delete_all_statements(), 2)
        deletes = [c for c in cli.calls if c[3] == "delete"]
        self.assertEqual(len(deletes), 2)
        for call in deletes:
            for flag, value in (("--environment", "env-x"), ("--cloud", "aws"), ("--region", "us-east-1")):
                self.assertEqual(call[call.index(flag) + 1], value)
            self.assertIn("--force", call)

    def test_remaining_statement_is_an_error(self):
        cli = FakeCli(["a", "b"], sticky={"b"})
        with self.assertRaisesRegex(FlinkRuntimeError, "REMAIN"):
            FlinkRuntime(CONFIG, cli).delete_all_statements()

    def test_empty_pool_is_zero(self):
        self.assertEqual(FlinkRuntime(CONFIG, FakeCli([])).delete_all_statements(), 0)


if __name__ == "__main__":
    unittest.main()
