"""Garante que operacoes nao dependam de branches historicas do Git."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "scripts/apply_schema_compatibility_policy.py",
    "scripts/collect_schema_evidence.py",
    "scripts/collect_flink_pool_evidence.py",
    "scripts/inspect_flink_accounts.py",
    "scripts/inspect_flink_databases.py",
    "scripts/etapa-9/validar_materializacao.py",
)


class BranchIndependenceTests(unittest.TestCase):
    def test_operational_scripts_do_not_require_historical_git_branches(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertNotIn('"WRONG_BRANCH"', source)
                self.assertNotIn('"BLOCKED_WRONG_BRANCH"', source)
                self.assertNotIn('"branch", "--show-current"', source)

    def test_subject_policy_preserves_saved_plan_gate(self):
        source = (ROOT / SCRIPTS[0]).read_text(encoding="utf-8")
        self.assertIn("APPROVED_PLAN_NOT_FOUND", source)
        self.assertIn("UNEXPECTED_PLAN_CONTENT", source)
        self.assertIn('"apply",', source)


if __name__ == "__main__":
    unittest.main()
