"""Contratos locais para nomes publicos dos utilitarios do pipeline."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = {
    "database_stage2.py": "bootstrap_postgres.py",
    "evidence_postgres_stage2.py": "collect_postgres_evidence.py",
    "evidence_stage3.py": "collect_cdc_access_evidence.py",
    "plan_stage5_consumer_acl.py": "plan_cdc_consumer_acl.py",
    "run_stage5_cdc_window.py": "run_cdc_validation_window.py",
}


class OperationalModuleLayoutTests(unittest.TestCase):
    def test_operational_module_names_are_functional(self):
        for old, new in MODULES.items():
            with self.subTest(module=new):
                self.assertFalse((ROOT / "scripts" / old).exists())
                self.assertTrue((ROOT / "scripts" / new).is_file())

    def test_temporal_join_validation_is_at_scripts_root(self):
        self.assertTrue((ROOT / "scripts/validate_temporal_join.py").is_file())
        self.assertFalse((ROOT / "scripts/etapa-9/validar_materializacao.py").exists())


if __name__ == "__main__":
    unittest.main()
