"""A politica BACKWARD so pode ser removida pelo teardown completo.

Substitui o prevent_destroy estatico: qualquer fluxo de etapa que propuser
excluir a politica deve ser bloqueado, sem nuvem ou Terraform real.
"""
import unittest

from plan_review import review_plan
from scripts.cdc_stage_flags import SUBJECT, configure_flags
from scripts.plan_cdc_acls import EXPECTED, approved_acl_plan


def plan_with(*items):
    return {"resource_changes": [
        {
            "address": address,
            "type": address.split(".")[0],
            "mode": "managed",
            "change": {"actions": actions},
        }
        for address, actions in items
    ]}


class SubjectPolicyProtectionTests(unittest.TestCase):
    def test_pipeline_review_rejects_subject_policy_delete(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION"):
            review_plan(plan_with((SUBJECT, ["delete"])))

    def test_pipeline_review_rejects_subject_policy_replacement(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION"):
            review_plan(plan_with((SUBJECT, ["delete", "create"])))

    def test_acl_stage_rejects_plan_that_also_deletes_policy(self):
        acl_creates = [(address, ["create"]) for address in sorted(EXPECTED)]
        plan = plan_with(*acl_creates, (SUBJECT, ["delete"]))
        self.assertFalse(approved_acl_plan(plan, set()))

    def test_stage_flags_keep_policy_enabled_while_in_state(self):
        env = {"TF_VAR_enable_subject_compatibility": "false"}
        configure_flags(env, addresses={SUBJECT})
        self.assertEqual(env["TF_VAR_enable_subject_compatibility"], "true")


if __name__ == "__main__":
    unittest.main()
