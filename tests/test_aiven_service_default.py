"""Regressao: o nome do PostgreSQL Aiven nao e entrada obrigatoria para Foundation."""
import unittest
from scripts.check_configuration import PHASE_KEYS, missing_keys


class AivenServiceNameOptionalTests(unittest.TestCase):
    def test_service_name_not_required_in_foundation(self):
        self.assertNotIn("TF_VAR_aiven_pg_service_name", PHASE_KEYS["foundation"])

    def test_aiven_project_is_required(self):
        required = set(missing_keys("foundation", {}))
        self.assertIn("TF_VAR_aiven_project", required)

    def test_foundation_complete_without_service_name(self):
        values = {key: "present" for key in PHASE_KEYS["foundation"]}
        self.assertEqual(missing_keys("foundation", values), [])


if __name__ == "__main__":
    unittest.main()
