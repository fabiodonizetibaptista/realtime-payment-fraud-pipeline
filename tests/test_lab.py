import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lab
import safety


class ProcessSafetyTests(unittest.TestCase):
    def test_redaction_replaces_only_exact_secret_value(self):
        message = "Error: password authentication failed for password=abc123; token field missing"
        safe = safety.redact_exact_secrets(message, ["abc123"])
        self.assertEqual(
            safe,
            "Error: password authentication failed for password=<redigido>; token field missing",
        )
    def test_stderr_does_not_fail_successful_native_process(self):
        output = safety.run_command(
            [sys.executable, "-c", "import sys; print('out'); print('warning', file=sys.stderr)"],
            cwd=ROOT,
        )
        self.assertIn("out", output)
        self.assertIn("warning", output)
    def test_failure_redacts_exact_secret_but_preserves_error_context(self):
        with self.assertRaises(RuntimeError) as raised:
            safety.run_command(
                [sys.executable, "-c", "import sys; print('Error: password=secret-value', file=sys.stderr); sys.exit(7)"],
                cwd=ROOT,
                secrets=["secret-value"],
            )
        self.assertIn("Error:", str(raised.exception))
        self.assertIn("password=<redigido>", str(raised.exception))
        self.assertNotIn("secret-value", str(raised.exception))


class TerraformSafetyTests(unittest.TestCase):
    def test_empty_resource_changes_are_zero(self):
        self.assertEqual(safety.changed_resources({"resource_changes": []}), [])
    def test_apply_allowlist_accepts_only_authorized_prefix(self):
        plan = {
            "resource_changes": [
                {"address": "example_resource.allowed[\"transactions\"]", "change": {"actions": ["create"]}},
                {"address": "data.example_data.current", "change": {"actions": ["read"]}},
            ]
        }
        accepted = safety.validate_apply_allowlist(plan, ["example_resource.allowed"])
        self.assertEqual(accepted, ['example_resource.allowed["transactions"]'])
    def test_apply_allowlist_rejects_unauthorized_resource(self):
        plan = {
            "resource_changes": [
                {"address": "example_resource.forbidden", "change": {"actions": ["create"]}}
            ]
        }
        with self.assertRaisesRegex(ValueError, "APPLY bloqueado"):
            safety.validate_apply_allowlist(plan, ["example_resource.allowed"])
    def test_destroy_requires_separate_allowlist(self):
        plan = {
            "resource_changes": [
                {"address": "example_resource.delete_me", "change": {"actions": ["delete"]}}
            ]
        }
        with self.assertRaises(ValueError):
            safety.validate_apply_allowlist(plan, ["example_resource.delete_me"])
        self.assertEqual(
            safety.validate_apply_allowlist(plan, [], ["example_resource.delete_me"]),
            ["example_resource.delete_me"],
        )
    def test_utf8_writer_does_not_add_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.txt"
            safety.write_utf8(path, "linha 1\nlinha 2\n")
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))


class LifecycleTests(unittest.TestCase):
    def test_teardown_runs_after_success(self):
        calls = []
        result = safety.run_with_teardown(lambda: calls.append("work") or "ok", lambda: calls.append("down"))
        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["work", "down"])
    def test_teardown_runs_after_failure_and_preserves_primary_error(self):
        calls = []

        def work():
            calls.append("work")
            raise ValueError("scenario failed")

        def down():
            calls.append("down")
            raise RuntimeError("cleanup failed")

        with self.assertRaisesRegex(ValueError, "scenario failed") as raised:
            safety.run_with_teardown(work, down)
        self.assertEqual(calls, ["work", "down"])
        self.assertTrue(any("RuntimeError" in note for note in getattr(raised.exception, "__notes__", [])))


class RepositoryContractTests(unittest.TestCase):
    def test_no_known_v1_ids_or_hosts_in_runtime_code(self):
        markers = (
            "env-" + "y5p78j",
            "lkc-" + "v75g02j",
            "lsrc-" + "xq59381",
            "lfcp-" + "9k36nv0",
            "sa-" + "mk5z1xw",
            "pg-payment-fraud-lab",
            "payments-cdc-aiven",
            "__debezium-heartbeat-lcc-" + "j50qpk8",
        )
        files = [ROOT / "lab.py", *((ROOT / "infra" / "terraform").glob("*.tf"))]
        content = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for marker in markers:
            self.assertNotIn(marker, content)
        self.assertNotRegex(content, r"[A-Za-z0-9-]+\.aivencloud\.com")
        self.assertNotRegex(content, r"[A-Za-z0-9-]+\.confluent\.cloud")
    def test_acl_command_uses_cloud_path_but_defers_cloud_flags_until_login(self):
        acl_command = ("kafka", "acl", "list")
        self.assertIn(acl_command, lab.CLI_HELP_COMMANDS)
        self.assertNotIn(("iam", "acl", "list"), lab.CLI_HELP_COMMANDS)
        self.assertNotIn(acl_command, lab.CLI_REQUIRED_FLAGS)
    def test_schema_compatibility_and_billing_commands_are_in_help_checks(self):
        self.assertIn(
            ("schema-registry", "schema", "compatibility", "validate"),
            lab.CLI_HELP_COMMANDS,
        )
        self.assertIn(("billing", "cost", "list"), lab.CLI_HELP_COMMANDS)
        self.assertEqual(
            lab.CLI_REQUIRED_FLAGS[("schema-registry", "schema", "compatibility", "validate")],
            ("--subject", "--type"),
        )
        self.assertEqual(lab.CLI_REQUIRED_FLAGS[("billing", "cost", "list")], ("--start-date", "--end-date"))


if __name__ == "__main__":
    unittest.main()
