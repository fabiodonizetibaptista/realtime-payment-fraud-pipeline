"""Checagem de credenciais: so status, nunca valores; sem rede real."""
import contextlib
import io
import unittest
import urllib.error
from unittest.mock import patch

import scripts.check_cloud_credentials as creds

ENV = {
    "CONFLUENT_CLOUD_API_KEY": "KEYSYNTHETIC0001",
    "CONFLUENT_CLOUD_API_SECRET": "Synthetic-Secret-Value-0123456789",
    "AIVEN_TOKEN": "synthetic-aiven-token-value",
    "TF_VAR_aiven_project": "my-project",
}


class FakeReply:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def opener_for(confluent_status, aiven_status):
    def opener(request, timeout=None):
        status = confluent_status if "confluent" in request.full_url else aiven_status
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, None)
        return FakeReply(status)
    return opener


class CloudCredentialTests(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(creds.check(ENV, opener_for(200, 200)), {"CONFLUENT": 200, "AIVEN": 200})
        self.assertEqual(creds.check(ENV, opener_for(401, 403)), {"CONFLUENT": 401, "AIVEN": 403})
        self.assertEqual(creds.check({}, opener_for(200, 200)), {"CONFLUENT": None, "AIVEN": None})

    def test_aiven_request_uses_project_and_token_header(self):
        request = creds.aiven_request("tok", "my project")
        self.assertTrue(request.full_url.endswith("/v1/project/my%20project"))
        self.assertEqual(request.get_header("Authorization"), "aivenv1 tok")

    def test_output_never_contains_values_and_blocks_on_401(self):
        output = io.StringIO()
        with patch.object(creds, "load_env_file", return_value=ENV), \
             patch.object(creds, "check", return_value={"CONFLUENT": 401, "AIVEN": 200}), \
             patch("sys.argv", ["check_cloud_credentials.py"]), \
             contextlib.redirect_stdout(output):
            code = creds.main()
        text = output.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("CONFLUENT_CREDENTIALS=FAILED HTTP=401", text)
        self.assertIn("api-key create --resource cloud", text)
        self.assertIn("CREDENTIALS_GATE=BLOCKED", text)
        for value in ENV.values():
            self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
