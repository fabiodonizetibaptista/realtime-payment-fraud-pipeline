import unittest

from lab import FOUNDATION_APPLY_RESOURCES, validate_foundation_plan


def make_plan(addresses=None, actions_by_address=None):
    addresses = (
        sorted(FOUNDATION_APPLY_RESOURCES)
        if addresses is None else addresses
    )
    actions_by_address = actions_by_address or {}

    return {
        "errored": False,
        "resource_changes": [
            {
                "address": address,
                "change": {
                    "actions": actions_by_address.get(address, ["create"])
                },
            }
            for address in addresses
        ],
    }


class FoundationApplyTests(unittest.TestCase):
    def test_accepts_exact_foundation_create_plan(self):
        result = validate_foundation_plan(make_plan())
        self.assertEqual(set(result), FOUNDATION_APPLY_RESOURCES)
        self.assertEqual(len(result), 14)

    def test_rejects_missing_resource(self):
        addresses = sorted(FOUNDATION_APPLY_RESOURCES)
        addresses.pop()
        with self.assertRaisesRegex(RuntimeError, "AUSENTES"):
            validate_foundation_plan(make_plan(addresses))

    def test_rejects_unexpected_resource(self):
        addresses = sorted(FOUNDATION_APPLY_RESOURCES)
        addresses.append("confluent_kafka_acl.unauthorized")
        with self.assertRaisesRegex(RuntimeError, "NAO_AUTORIZADOS"):
            validate_foundation_plan(make_plan(addresses))

    def test_rejects_update(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["update"]})
            )

    def test_rejects_replacement(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["delete", "create"]})
            )

    def test_rejects_destroy(self):
        address = sorted(FOUNDATION_APPLY_RESOURCES)[0]
        with self.assertRaisesRegex(RuntimeError, "somente criacoes"):
            validate_foundation_plan(
                make_plan(actions_by_address={address: ["delete"]})
            )


if __name__ == "__main__":
    unittest.main()
