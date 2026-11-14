"""Remocao de statements Flink com escopo explicito e remocao assincrona, sem nuvem."""
import json
import unittest
from types import SimpleNamespace

from scripts.flink_runtime import FlinkConfig, FlinkRuntime, FlinkRuntimeError

CONFIG = FlinkConfig("env-x", "lkc-x", "lfcp-x", "aws", "us-east-1")


class FakeCli:
    """Simula a Confluent: o delete so some da lista apos `lag` consultas."""

    def __init__(self, names, lag=0, sticky=(), failing_delete=()):
        self.names = list(names)
        self.lag, self.sticky, self.failing_delete = lag, set(sticky), set(failing_delete)
        self.pending, self.calls = {}, []

    def __call__(self, args, timeout=None, cwd=None):
        self.calls.append(args)
        if args[3] == "list":
            for name in list(self.pending):
                self.pending[name] -= 1
                if self.pending[name] < 0:
                    self.names.remove(name)
                    del self.pending[name]
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"name": n} for n in self.names]))
        if args[3] == "delete":
            name = args[4]
            if name not in self.sticky:
                self.pending.setdefault(name, self.lag)
            return SimpleNamespace(returncode=1 if name in self.failing_delete else 0, stdout="")
        raise AssertionError(args)


def runtime(cli):
    flink = FlinkRuntime(CONFIG, cli)
    flink.sleep = lambda seconds: None
    return flink


class StatementCleanupTests(unittest.TestCase):
    def test_deletes_all_with_explicit_scope(self):
        cli = FakeCli(["etapa11-fraud-pattern-matches", "cli-query-1"])
        self.assertEqual(runtime(cli).delete_all_statements(), 2)
        deletes = [c for c in cli.calls if c[3] == "delete"]
        self.assertEqual(len(deletes), 2)
        for call in deletes:
            for flag, value in (("--environment", "env-x"), ("--cloud", "aws"), ("--region", "us-east-1")):
                self.assertEqual(call[call.index(flag) + 1], value)
            self.assertIn("--force", call)

    def test_waits_for_asynchronous_removal(self):
        # Caso real: logo apos o delete os statements ainda aparecem na lista.
        cli = FakeCli([f"s{i}" for i in range(35)], lag=3)
        self.assertEqual(runtime(cli).delete_all_statements(), 35)

    def test_delete_error_for_statement_already_going_away_is_tolerated(self):
        cli = FakeCli(["a", "b"], failing_delete={"b"})
        self.assertEqual(runtime(cli).delete_all_statements(), 2)

    def test_statement_that_never_goes_away_is_an_error_with_count(self):
        cli = FakeCli(["a", "b"], sticky={"b"})
        with self.assertRaisesRegex(FlinkRuntimeError, "REMAIN_AFTER_DELETE_1"):
            runtime(cli).delete_all_statements()

    def test_empty_pool_is_zero(self):
        self.assertEqual(runtime(FakeCli([])).delete_all_statements(), 0)


if __name__ == "__main__":
    unittest.main()
