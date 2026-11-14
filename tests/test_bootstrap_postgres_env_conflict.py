"""Regressao: ambiente herdado nao pode trocar conexao do clone silenciosamente."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch, sentinel

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_postgres_under_test", ROOT / "scripts" / "bootstrap_postgres.py"
)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)

VALUES = {
    "PGHOST": "service-from-current-clone.invalid",
    "PGPORT": "5432",
    "PGDATABASE": "defaultdb",
    "PGUSER": "current_user",
    "PGPASSWORD": "test-only-dummy",
    "PG_CA": "dummy-ca.pem",
}

class BootstrapEnvConflictTests(unittest.TestCase):
    def test_conflicting_process_host_is_blocked_before_connection(self):
        with patch.dict(os.environ, {"PGHOST": "old-host.invalid"}, clear=True), \
             patch.object(bootstrap, "read_local_env", return_value=VALUES.copy()), \
             patch.object(bootstrap.pg8000.dbapi, "connect") as db_connect:
            with self.assertRaisesRegex(RuntimeError, r"^POSTGRES_ENV_CONFLICT:PGHOST$"):
                bootstrap.connect()
            db_connect.assert_not_called()

    def test_conflicting_process_password_is_blocked_without_disclosing_it(self):
        with patch.dict(os.environ, {"PGPASSWORD": "old-password"}, clear=True), \
             patch.object(bootstrap, "read_local_env", return_value=VALUES.copy()), \
             patch.object(bootstrap.pg8000.dbapi, "connect") as db_connect:
            with self.assertRaisesRegex(RuntimeError, r"^POSTGRES_ENV_CONFLICT:PGPASSWORD$"):
                bootstrap.connect()
            db_connect.assert_not_called()

    def test_matching_host_can_connect_with_clone_values(self):
        with patch.dict(os.environ, {"PGHOST": VALUES["PGHOST"]}, clear=True), \
             patch.object(bootstrap, "read_local_env", return_value=VALUES.copy()), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(bootstrap.ssl, "create_default_context", return_value=sentinel.context), \
             patch.object(bootstrap.pg8000.dbapi, "connect", return_value=sentinel.connection) as db_connect:
            result = bootstrap.connect()
            self.assertIs(result, sentinel.connection)
            kwargs = db_connect.call_args.kwargs
            self.assertEqual(kwargs["host"], VALUES["PGHOST"])
            self.assertEqual(kwargs["ssl_context"], sentinel.context)

    def test_no_process_override_uses_clone_values(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(bootstrap, "read_local_env", return_value=VALUES.copy()), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(bootstrap.ssl, "create_default_context", return_value=sentinel.context), \
             patch.object(bootstrap.pg8000.dbapi, "connect", return_value=sentinel.connection) as db_connect:
            bootstrap.connect()
            self.assertEqual(db_connect.call_args.kwargs["host"], VALUES["PGHOST"])

if __name__ == "__main__":
    unittest.main()
