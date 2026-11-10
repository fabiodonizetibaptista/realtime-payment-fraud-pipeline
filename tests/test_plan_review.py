"""Testes locais da politica de revisao Terraform."""

import unittest

from plan_review import review_plan


def resource(address, action=("create",), kind="confluent_kafka_acl"):
    return {
        "address": address,
        "type": kind,
        "mode": "managed",
        "change": {
            "actions": list(action),
            "before": {"secret": "DO_NOT_PRINT"},
            "after": {"secret": "DO_NOT_PRINT"},
        },
    }


class PlanReviewTests(unittest.TestCase):

    def test_accepts_new_resource_without_address_allowlist(self):
        plan = {"resource_changes": [
            resource("confluent_kafka_acl.future_stage[0]")
        ]}
        result = review_plan(plan)
        self.assertEqual(result["create"], 1)
        self.assertFalse(result["approved_for_apply"])

    def test_accepts_updates_for_review(self):
        result = review_plan({"resource_changes": [
            resource("aiven_pg.payments", ("update",), "aiven_pg")
        ]})
        self.assertEqual(result["update"], 1)

    def test_ignores_terraform_data_source_read(self):
        data_source = resource("data.confluent_organization.current", ("read",), "confluent_organization")
        data_source["mode"] = "data"
        result = review_plan({"resource_changes": [data_source]})
        self.assertEqual(result["create"], 0)
        self.assertEqual(result["update"], 0)
        self.assertEqual(result["resources"], [])

    def test_rejects_data_source_write(self):
        data_source = resource("data.confluent_organization.current", ("update",), "confluent_organization")
        data_source["mode"] = "data"
        with self.assertRaisesRegex(ValueError, "UNSAFE_DATA_SOURCE_ACTION"):
            review_plan({"resource_changes": [data_source]})

    def test_rejects_destroy(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION"):
            review_plan({"resource_changes": [
                resource("aiven_pg.payments", ("delete",), "aiven_pg")
            ]})

    def test_rejects_replacement(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION"):
            review_plan({"resource_changes": [
                resource(
                    "aiven_pg.payments",
                    ("delete", "create"),
                    "aiven_pg",
                )
            ]})

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_RESOURCE_TYPE"):
            review_plan({"resource_changes": [
                resource("random_password.secret", kind="random_password")
            ]})

    def test_rejects_duplicate_addresses(self):
        item = resource("confluent_kafka_acl.duplicate")
        with self.assertRaisesRegex(ValueError, "INVALID_RESOURCE_METADATA"):
            review_plan({"resource_changes": [item, item]})

    def test_never_returns_sensitive_values(self):
        result = review_plan({"resource_changes": [
            resource("confluent_kafka_acl.example")
        ]})
        self.assertNotIn("DO_NOT_PRINT", str(result))
        self.assertNotIn("before", str(result))
        self.assertNotIn("after", str(result))

    def test_rejects_incomplete_plan(self):
        with self.assertRaisesRegex(ValueError, "MISSING_RESOURCE_CHANGES"):
            review_plan({})


if __name__ == "__main__":
    unittest.main()
