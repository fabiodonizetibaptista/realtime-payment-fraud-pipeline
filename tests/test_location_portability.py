"""Cloud, regiao e nomes Confluent vem de variaveis/State, nao de literais."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra" / "terraform"
LITERALS = re.compile(r'"(AWS|GCP|AZURE|us-east-1|desafio-final|desafio-basic)"')


class LocationPortabilityTests(unittest.TestCase):
    def test_terraform_resources_use_variables(self):
        for path in sorted(TF.glob("*.tf")):
            if path.name == "variables.tf":
                continue
            with self.subTest(file=path.name):
                self.assertIsNone(LITERALS.search(path.read_text(encoding="utf-8")))

    def test_pool_follows_cluster_location(self):
        pool = (TF / "flink-compute-pool.tf").read_text(encoding="utf-8")
        self.assertIn("cloud        = confluent_kafka_cluster.basic.cloud", pool)
        self.assertIn("region       = confluent_kafka_cluster.basic.region", pool)

    def test_runbook_flink_validator_reads_location_from_state(self):
        text = (ROOT / "scripts" / "validate_temporal_join.py").read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        self.assertIsNone(re.search(r'"(aws|us-east-1)"|`desafio-final`', code))


if __name__ == "__main__":
    unittest.main()
