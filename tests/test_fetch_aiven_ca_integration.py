"""Fluxo CA simulado: projeto no State, HTTP GET, PEM novo e PG_CA.

Nenhuma chamada remota. Nao utiliza .env, certificado ou State reais.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import fetch_aiven_ca as ca


class AivenCAIntegrationTests(unittest.TestCase):
    def test_api_response_creates_fresh_pem_and_updates_env(self):
        pem = "-----BEGIN CERTIFICATE-----\nZmFrZS1jZXJ0aWZpY2F0ZQ==\n-----END CERTIFICATE-----\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git" / "info").mkdir(parents=True)
            (root / ".git" / "info" / "exclude").write_text("", encoding="utf-8")
            local_env = root / ".env"
            local_env.write_text(
                "AIVEN_TOKEN=test-token\n"
                "TF_VAR_aiven_project=test-project\n"
                "KEEP_ME=untouched\n"
                "PG_CA=obsolete-path\n",
                encoding="utf-8",
            )
            target = root / ".local" / "aiven-ca.pem"
            self.assertFalse(target.exists(), "Teste deve iniciar sem CA")

            response = io.BytesIO(json.dumps({"certificate": pem}).encode("utf-8"))
            output = io.StringIO()
            with (
                patch.object(ca, "ROOT", root),
                patch.object(ca, "ENV_FILE", local_env),
                patch.object(ca, "TARGET", target),
                patch.object(ca, "load_env_file", return_value={
                    "AIVEN_TOKEN": "test-token",
                    "TF_VAR_aiven_project": "test-project",
                }),
                patch.object(ca, "_validate_aiven_project_state", return_value="PASS") as check_state,
                patch.object(ca.urllib.request, "urlopen", return_value=response) as get,
                patch.object(ca.ssl, "PEM_cert_to_DER_cert", return_value=b"test"),
                patch.dict(ca.os.environ, {
                    "AIVEN_TOKEN": "test-token",
                    "TF_VAR_aiven_project": "test-project",
                }, clear=True),
                redirect_stdout(output),
            ):
                result = ca.main()

            self.assertEqual(result, 0, output.getvalue())
            check_state.assert_called_once_with("test-project")
            get.assert_called_once()
            request = get.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "https://api.aiven.io/v1/project/test-project/kms/ca")
            self.assertEqual(target.read_text(encoding="utf-8"), pem)
            updated_env = local_env.read_text(encoding="utf-8")
            self.assertIn("KEEP_ME=untouched\n", updated_env)
            self.assertEqual(updated_env.count("PG_CA="), 1)
            self.assertIn(f"PG_CA={target.resolve()}\n", updated_env)
            self.assertNotIn("obsolete-path", updated_env)
            self.assertNotIn("test-token", output.getvalue())
            self.assertNotIn(pem, output.getvalue())
            self.assertIn("CA_GATE=PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
