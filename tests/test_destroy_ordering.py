"""Ordem de destruicao dos recursos de data plane.

As ACLs Kafka e a politica do Schema Registry autenticam com credenciais do
provider passadas por variaveis (TF_VAR_foundation_*). Sem uma aresta
explicita no grafo, `terraform destroy` pode remover a API key, o role
binding ou o cluster antes desses recursos: o teardown de 2026-11-12
(run-20261111) falhou assim, com 401 em 6 ACLs e 4 service accounts presas.
"""
import re
import unittest
from pathlib import Path

TF = Path(__file__).resolve().parents[1] / "infra" / "terraform"
BLOCK = re.compile(r'^resource "(?P<type>[a-z_]+)" "(?P<name>[^"]+)" \{\n(?P<body>.*?)^\}', re.M | re.S)


def resources(resource_type):
    found = []
    for path in sorted(TF.glob("*.tf")):
        for match in BLOCK.finditer(path.read_text(encoding="utf-8")):
            if match.group("type") == resource_type:
                found.append((f"{path.name}:{match.group('name')}", match.group("body")))
    return found


class DestroyOrderingTests(unittest.TestCase):
    def test_every_kafka_acl_depends_on_admin_kafka_key(self):
        acls = resources("confluent_kafka_acl")
        self.assertEqual(len(acls), 12)
        for name, body in acls:
            with self.subTest(acl=name):
                self.assertRegex(body, r"depends_on\s*=\s*\[[^\]]*confluent_api_key\.iac_admin_kafka")

    def test_admin_key_chain_reaches_cluster(self):
        # key -> role binding -> cluster: destroy remove ACL antes da chave,
        # a chave antes do role binding e o role binding antes do cluster.
        foundation = (TF / "foundation.tf").read_text(encoding="utf-8")
        key = dict(resources("confluent_api_key"))["foundation.tf:iac_admin_kafka"]
        self.assertIn("confluent_role_binding.iac_admin_cluster_admin", key)
        binding = dict(resources("confluent_role_binding"))["foundation.tf:iac_admin_cluster_admin"]
        self.assertIn("confluent_kafka_cluster.basic", binding)
        self.assertIn("iac_admin_kafka", foundation)

    def test_subject_policy_depends_on_schema_registry_credentials(self):
        (name, body), = resources("confluent_subject_config")
        self.assertIn("confluent_api_key.schema_registry", body)
        self.assertIn("confluent_role_binding.schema_registry_transactions_manage", body)


if __name__ == "__main__":
    unittest.main()
