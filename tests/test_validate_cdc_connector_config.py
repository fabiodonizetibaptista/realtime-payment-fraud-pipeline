"""A validacao do conector nunca expoe valores de configuracao."""
import unittest

from scripts.validate_cdc_connector_config import (
    OMITTED, connector_from_plan, field_errors, sensitive_fragments,
)

PASSWORD = "Synthetic-Password-0123456789abcdef"
PEM = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIEQTCCAqmgAwIBAgIUSyntheticCertificateBodyLine01\n"
    "-----END CERTIFICATE-----\n"
)


class ValidateConfigTests(unittest.TestCase):
    def test_plan_extraction(self):
        plan = {"resource_changes": [{
            "address": "confluent_connector.payments_cdc[0]",
            "change": {"after": {
                "environment": [{"id": "env-x"}], "kafka_cluster": [{"id": "lkc-x"}],
                "config_nonsensitive": {"name": "n"},
                "config_sensitive": {"database.password": PASSWORD},
            }},
        }]}
        self.assertEqual(connector_from_plan(plan)[:2], ("env-x", "lkc-x"))
        with self.assertRaises(RuntimeError):
            connector_from_plan({"resource_changes": []})

    def test_echoed_values_are_never_returned(self):
        fragments = sensitive_fragments([PASSWORD, PEM])
        response = {"configs": [
            {"value": {"name": "database.password", "value": PASSWORD,
                       "errors": [f"Invalid value {PASSWORD}"]}},
            {"value": {"name": "database.sslrootcert", "value": PEM,
                       "errors": ["Bad cert MIIEQTCCAqmgAwIBAgIUSyntheticCertificateBodyLine01"]}},
            {"value": {"name": "snapshot.mode", "value": "initial",
                       "errors": ["Unknown option"]}},
            {"value": {"name": "tasks.max", "value": "1", "errors": []}},
        ]}
        errors = field_errors(response, fragments)
        self.assertEqual(errors, [
            ("database.password", OMITTED),
            ("database.sslrootcert", OMITTED),
            ("snapshot.mode", "Unknown option"),
        ])
        rendered = repr(errors)
        self.assertNotIn(PASSWORD, rendered)
        self.assertNotIn("SyntheticCertificateBodyLine01", rendered)


if __name__ == "__main__":
    unittest.main()
