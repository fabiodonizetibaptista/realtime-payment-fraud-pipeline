"""Checagem de conta limpa: acha restos fora do State, sem rede real."""
import io
import json
import re
import unittest
import urllib.error
from pathlib import Path

import scripts.check_clean_slate as slate

ENV = {
    "CONFLUENT_CLOUD_API_KEY": "KEYSYNTHETIC0001",
    "CONFLUENT_CLOUD_API_SECRET": "Synthetic-Secret-Value",
    "AIVEN_TOKEN": "synthetic-token",
    "TF_VAR_aiven_project": "proj",
}


class Reply:
    def __init__(self, status, body):
        self.status, self._body = status, json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener(envs=(), sas=(), aiven_status=404):
    def open_(request, timeout=None):
        url = request.full_url
        if "environments" in url:
            return Reply(200, {"data": [{"display_name": n, "id": f"env-{i}"} for i, n in enumerate(envs)]})
        if "service-accounts" in url:
            return Reply(200, {"data": [{"display_name": n, "id": f"sa-{i}"} for i, n in enumerate(sas)]})
        if aiven_status >= 400:
            raise urllib.error.HTTPError(url, aiven_status, "x", {}, io.BytesIO())
        return Reply(aiven_status, {"service": {}})
    return open_


class CleanSlateTests(unittest.TestCase):
    def test_clean_account(self):
        self.assertEqual(slate.find_conflicts(ENV, opener(envs=["default"], sas=["SA_Teste"])), [])

    def test_leftovers_are_reported_with_ids(self):
        conflicts = slate.find_conflicts(ENV, opener(
            envs=["default", "desafio-final"], sas=["desafio-cdc", "SA_Teste"], aiven_status=200))
        self.assertEqual(conflicts, [
            ("environment", "desafio-final", "env-1"),
            ("service_account", "desafio-cdc", "sa-0"),
            ("aiven_service", "payments-postgres", "proj"),
        ])

    def test_custom_names_from_variables(self):
        env = {**ENV, "TF_VAR_confluent_environment_name": "meu-env", "TF_VAR_aiven_pg_service_name": "pg2"}
        conflicts = slate.find_conflicts(env, opener(envs=["desafio-final", "meu-env"]))
        self.assertEqual(conflicts, [("environment", "meu-env", "env-1")])

    def test_unexpected_aiven_status_blocks(self):
        with self.assertRaisesRegex(RuntimeError, "AIVEN_SERVICE_CHECK_FAILED HTTP=403"):
            slate.find_conflicts(ENV, opener(aiven_status=403))

    def test_service_account_names_match_terraform(self):
        tf = "\n".join(p.read_text(encoding="utf-8") for p in (Path(slate.TF_DIR)).glob("*.tf"))
        names = set(re.findall(
            r'resource "confluent_service_account" "\w+" \{.*?display_name = "([^"]+)"', tf, re.S))
        self.assertEqual(names, set(slate.SERVICE_ACCOUNTS))


if __name__ == "__main__":
    unittest.main()
