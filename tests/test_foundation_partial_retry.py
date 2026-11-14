"""Apply parcial da fundacao: a nova tentativa cria so o que falta."""
import unittest

from lab import FOUNDATION_APPLY_RESOURCES, prior_state_addresses, validate_foundation_plan

ALL = sorted(FOUNDATION_APPLY_RESOURCES)


def plan(creates, existing=()):
    return {
        "errored": False,
        "prior_state": {"values": {"root_module": {"resources": [
            {"address": address, "mode": "managed"} for address in existing
        ]}}},
        "resource_changes": [
            {"address": address, "change": {"actions": ["create"]}} for address in creates
        ],
    }


class FoundationPartialRetryTests(unittest.TestCase):
    def test_completes_only_missing_resources(self):
        existing, missing = ALL[:6], ALL[6:]
        self.assertEqual(validate_foundation_plan(plan(missing, existing)), missing)

    def test_still_requires_every_missing_resource(self):
        existing = ALL[:6]
        with self.assertRaisesRegex(RuntimeError, "AUSENTES"):
            validate_foundation_plan(plan(ALL[7:], existing))

    def test_recreating_existing_resource_is_rejected(self):
        existing = ALL[:6]
        with self.assertRaisesRegex(RuntimeError, "NAO_AUTORIZADOS"):
            validate_foundation_plan(plan(ALL, existing))

    def test_everything_present_means_nothing_to_create(self):
        self.assertEqual(validate_foundation_plan(plan([], ALL)), [])

    def test_prior_state_ignores_data_sources_and_reads_child_modules(self):
        state = {"prior_state": {"values": {"root_module": {
            "resources": [{"address": "a.b", "mode": "managed"}, {"address": "data.x", "mode": "data"}],
            "child_modules": [{"resources": [{"address": "module.m.c.d", "mode": "managed"}]}],
        }}}}
        self.assertEqual(prior_state_addresses(state), {"a.b", "module.m.c.d"})


if __name__ == "__main__":
    unittest.main()
