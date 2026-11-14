"""O apply do conector recebe as credenciais de provider do .env."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.apply_cdc_connector as apply


class ApplyEnvTests(unittest.TestCase):
    def test_env_file_fills_missing_provider_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("AIVEN_TOKEN=from-file\nPGHOST=file-host\n", encoding="utf-8")
            with patch.object(apply, "ROOT", root), \
                 patch.dict(apply.os.environ, {"PGHOST": "process-host"}, clear=True):
                env = apply.execution_env()
        self.assertEqual(env["AIVEN_TOKEN"], "from-file")
        self.assertEqual(env["PGHOST"], "process-host")  # processo tem precedencia
        self.assertEqual(env["TF_LOG"], "OFF")


if __name__ == "__main__":
    unittest.main()
