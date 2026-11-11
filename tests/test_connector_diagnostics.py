"""O diagnostico do conector nunca persiste texto do provider."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.connector_diagnostics import CATEGORIES, classify, write_diagnostic

SECRETS = {
    "confluent_key": "ABCD1234EFGH5678",
    "confluent_secret": "s3cr3tV4lueWithLotsOfEntropy+/xyzABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "pg_uri_password": "Hunter2-Very-Secret",
    "pem_body": "MIIDdzCCAl+gAwIBAgIEAgAAuTANBgkqhkiG9w0BAQUFADBaMQswCQYDVQQGEwJJ",
    "base64": "cGFzc3dvcmQ6c3VwZXJzZWNyZXR2YWx1ZQ==",
    "json_password": "jsonP@ssw0rdValue",
    "aiven_token": "avn_tok_9f8e7d6c5b4a3210fedcba9876543210",
    "bearer": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl",
}

SAMPLES = {
    "PG_AUTH": (
        'Error: error creating connector: 400 Bad Request: FATAL: password '
        'authentication failed for user "cdc_user" '
        f'postgres://cdc_user:{SECRETS["pg_uri_password"]}@pg.example:5432/defaultdb'
    ),
    "TLS_CA": (
        "Error: unable to validate: SSL handshake failed: x509: certificate "
        "signed by unknown authority\n-----BEGIN CERTIFICATE-----\n"
        f'{SECRETS["pem_body"]}\n-----END CERTIFICATE-----'
    ),
    "REPLICATION_SLOT": (
        'Error: 400: replication slot "payments_cdc_slot" is active; '
        f'"password":"{SECRETS["json_password"]}"'
    ),
    "NETWORK": (
        f"Error: could not connect to server: Connection refused; token={SECRETS['aiven_token']}"
    ),
    "KAFKA_ACL": (
        "Error: TopicAuthorizationException: not authorized to access topics "
        f"api_key={SECRETS['confluent_key']} api_secret={SECRETS['confluent_secret']}"
    ),
    "CONFLUENT_AUTH": (
        f"Error: 401 Unauthorized\nAuthorization: Bearer {SECRETS['bearer']}\n"
        f"Basic {SECRETS['base64']}"
    ),
    "INVALID_CONFIG": (
        "Error: error creating connector: 400 Bad Request: "
        "Missing required configuration \"database.dbname\" which has no default value; it is required"
    ),
}


class ConnectorDiagnosticsTests(unittest.TestCase):
    def test_categories_are_classified(self):
        for expected, text in SAMPLES.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify(text)["category"], expected)

    def test_unknown_text_falls_back(self):
        self.assertEqual(classify("algo inesperado")["category"], "UNKNOWN")
        self.assertEqual(classify("")["category"], "UNKNOWN")

    def test_http_status_is_numeric_or_none(self):
        self.assertEqual(classify(SAMPLES["CONFLUENT_AUTH"])["http_status"], 401)
        self.assertEqual(classify(SAMPLES["INVALID_CONFIG"])["http_status"], 400)
        self.assertIsNone(classify(SAMPLES["NETWORK"])["http_status"])

    def test_output_never_contains_provider_text_or_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in SAMPLES.items():
                diagnostic = classify(text)
                self.assertEqual(set(diagnostic), {"category", "rule_id", "http_status"})
                self.assertIn(diagnostic["category"], CATEGORIES)
                path = write_diagnostic(Path(tmp), f"run-{name}", diagnostic)
                saved = path.read_text(encoding="utf-8")
                for secret in SECRETS.values():
                    self.assertNotIn(secret, saved)
                self.assertNotIn("cdc_user", saved)
                self.assertFalse(json.loads(saved)["provider_text_persisted"])

    def test_write_rejects_fields_outside_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            leaking = {**classify("x"), "detail": "texto do provider"}
            with self.assertRaises(ValueError):
                write_diagnostic(Path(tmp), "run", leaking)
            with self.assertRaises(ValueError):
                write_diagnostic(Path(tmp), "run", {
                    "category": "texto livre", "rule_id": "no_rule_matched", "http_status": None,
                })
            with self.assertRaises(ValueError):
                write_diagnostic(Path(tmp), "run", {
                    "category": "UNKNOWN", "rule_id": "no_rule_matched", "http_status": "401",
                })


if __name__ == "__main__":
    unittest.main()
