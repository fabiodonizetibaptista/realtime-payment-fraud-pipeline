"""Testes locais sem acesso ao PostgreSQL nem exposicao de segredos."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Isola o teste local: nenhuma conexao e aberta e o driver nao precisa estar instalado
# no ambiente de construcao do patch. No projeto real o driver vem do requirements.txt.
import sys
from types import ModuleType

if "pg8000" not in sys.modules:
    try:
        import pg8000.dbapi
    except ImportError:
        driver = ModuleType("pg8000")
        driver.dbapi = ModuleType("pg8000.dbapi")
        sys.modules["pg8000"] = driver
        sys.modules["pg8000.dbapi"] = driver.dbapi

from scripts import preflight_postgres_cdc as preflight


class PostgresConfigTests(unittest.TestCase):
    def test_missing_config_fails_before_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(preflight, "ROOT", Path(temp)):
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "POSTGRES_ENV_INCOMPLETE"):
                        preflight.read_config()

    def test_missing_ca_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(PGHOST="example.invalid", PGPORT="5432", PGDATABASE="db",
                       PGUSER="admin", PGPASSWORD="secret", CDC_PGUSER="cdc_user",
                       CDC_PGPASSWORD="secret", PG_CA=str(Path(temp) / "missing.pem"))
            with patch.object(preflight, "ROOT", Path(temp)):
                with patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "POSTGRES_CA_MISSING"):
                        preflight.read_config()

    def test_invalid_port_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(PGHOST="example.invalid", PGPORT="0", PGDATABASE="db",
                       PGUSER="admin", PGPASSWORD="secret", CDC_PGUSER="cdc_user",
                       CDC_PGPASSWORD="secret", PG_CA=str(Path(temp) / "missing.pem"))
            with patch.object(preflight, "ROOT", Path(temp)):
                with patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "POSTGRES_PORT_INVALID"):
                        preflight.read_config()


if __name__ == "__main__":
    unittest.main()
