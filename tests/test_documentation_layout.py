"""Contratos locais para a documentação publicada e seus caminhos funcionais."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DocumentationLayoutTests(unittest.TestCase):
    def test_public_documentation_uses_functional_paths(self):
        docs = ROOT / "docs"
        self.assertTrue((docs / "README.md").is_file())
        self.assertTrue((docs / "decisions/postgres-cdc.md").is_file())
        self.assertTrue((docs / "alert-contract.md").is_file())
        self.assertTrue((docs / "validation/fraud-scenarios.md").is_file())
        self.assertFalse(any(path.is_file() for folder in docs.glob("etapa-*") for path in folder.rglob("*")))
        self.assertFalse((docs / "stage8-evidence.md").exists())

    def test_cdc_decision_keeps_evidence_gate(self):
        source = (ROOT / "scripts/collect_cdc_access_evidence.py").read_text(encoding="utf-8")
        decision = (ROOT / "docs/decisions/postgres-cdc.md").read_text(encoding="utf-8")
        self.assertIn('docs/decisions/postgres-cdc.md', source)
        self.assertIn('DECISAO_MERCHANTS=60', decision)


if __name__ == "__main__":
    unittest.main()
