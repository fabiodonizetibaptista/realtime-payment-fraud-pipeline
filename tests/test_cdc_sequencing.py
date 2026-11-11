"""Conserva o contrato das etapas sem usar nuvem ou Terraform real."""
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.cdc_stage_flags import configure_flags, CONNECTOR, SUBJECT
from scripts.plan_cdc_acls import EXPECTED, approved_acl_plan

ROOT = Path(__file__).resolve().parents[1]


def plan_for(items):
    return {'resource_changes': [
        {'address': addr, 'change': {'actions': actions}}
        for addr, actions in items
    ]}


class SequencingTests(unittest.TestCase):
    def test_acl_count_and_names(self):
        self.assertEqual(len(EXPECTED), 11)

    def test_all_expected_acls_pass(self):
        self.assertTrue(approved_acl_plan(
            plan_for([(x, ['create']) for x in EXPECTED]), set()
        ))

    def test_partial_retry_allows_only_missing_acls(self):
        existing = {next(iter(EXPECTED))}
        self.assertTrue(approved_acl_plan(
            plan_for([(x, ['create']) for x in EXPECTED - existing]), existing
        ))

    def test_acl_plan_rejects_subject_or_connector(self):
        for extra in (SUBJECT, CONNECTOR):
            with self.subTest(extra=extra):
                self.assertFalse(approved_acl_plan(
                    plan_for([(x, ['create']) for x in EXPECTED] + [(extra, ['create'])]), set()
                ))

    def test_acl_plan_rejects_update_destroy_replace(self):
        addr = next(iter(EXPECTED))
        for action in (['update'], ['delete'], ['delete','create']):
            with self.subTest(action=action):
                self.assertFalse(approved_acl_plan(
                    plan_for([(x, action if x == addr else ['create']) for x in EXPECTED]), set()
                ))

    def test_no_missing_acl_is_not_a_new_plan(self):
        self.assertFalse(approved_acl_plan(plan_for([]), set(EXPECTED)))

    def test_policy_defaults_to_off_if_not_managed(self):
        env = {}
        configure_flags(env, connector='off', subject='auto', addresses=set())
        self.assertEqual(env['TF_VAR_enable_subject_compatibility'], 'false')
        self.assertEqual(env['TF_VAR_enable_cdc_connector'], 'false')

    def test_policy_and_connector_remain_on_when_in_state(self):
        env = {}
        configure_flags(env, addresses={SUBJECT,CONNECTOR})
        self.assertEqual(env['TF_VAR_enable_subject_compatibility'], 'true')
        self.assertEqual(env['TF_VAR_enable_cdc_connector'], 'true')

    def test_stage_overrides_untrusted_boolean_flags(self):
        env = {'TF_VAR_enable_subject_compatibility':'true',
               'TF_VAR_enable_cdc_connector':'true'}
        configure_flags(env, connector='off', subject='off', addresses=set())
        self.assertEqual(env['TF_VAR_enable_subject_compatibility'],'false')
        self.assertEqual(env['TF_VAR_enable_cdc_connector'],'false')

    def test_state_failure_blocks_instead_of_assuming_empty(self):
        with patch('scripts.cdc_stage_flags.managed_addresses', side_effect=RuntimeError('UNAVAILABLE')):
            with self.assertRaises(RuntimeError): configure_flags({})

    def test_subject_config_is_conditional_and_protected(self):
        hcl = (ROOT / 'infra/terraform/cdc-subject-compatibility.tf').read_text(encoding='utf-8')
        self.assertIn('count = var.enable_subject_compatibility ? 1 : 0', hcl)
        self.assertIn('prevent_destroy = true', hcl)
        self.assertIn('default     = false', (ROOT/'infra/terraform/variables.tf').read_text(encoding='utf-8'))


if __name__ == '__main__': unittest.main()
