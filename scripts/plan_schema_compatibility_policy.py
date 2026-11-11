"""Planeja SOMENTE compatibilidade BACKWARD apos registro do subject pelo CDC.

Nao cria schemas e nao liga/desliga o conector por conta propria.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file
from scripts.cdc_stage_flags import configure_flags, changes_in_plan, SUBJECT

TF_DIR = ROOT / 'infra' / 'terraform'
PLAN = TF_DIR / 'stage6-subject-config.tfplan'
SUBJECT_NAME = 'payments.public.transactions-value'


def terraform(env, *args):
    return subprocess.run(['terraform', *args], cwd=TF_DIR, env=env,
                          capture_output=True, text=True, check=False, timeout=180)


def main():
    if PLAN.exists():
        print('POLICY_PLAN_GATE=BLOCKED; REASON=EXISTING_PLAN')
        return 1
    config = load_env_file(ROOT / '.env')
    env = dict(os.environ)
    for key, val in config.items():
        if val and not env.get(key): env[key] = val
    try:
        addresses = configure_flags(env, connector='auto', subject='on')
    except (RuntimeError, subprocess.TimeoutExpired):
        print('POLICY_PLAN_GATE=BLOCKED; REASON=STATE_UNAVAILABLE')
        return 1
    if SUBJECT in addresses:
        print('POLICY_PLAN_GATE=ALREADY_MANAGED')
        return 0
    if config.get('CDC_PGPASSWORD'):
        env['TF_VAR_cdc_connector_password'] = config['CDC_PGPASSWORD']
    old = os.umask(0o077)
    try:
        planned = terraform(env, 'plan', '-input=false', '-no-color', '-out=stage6-subject-config.tfplan')
    finally: os.umask(old)
    if planned.returncode:
        PLAN.unlink(missing_ok=True)
        print('POLICY_PLAN_GATE=BLOCKED; REASON=PLAN_FAILED')
        return 1
    shown = terraform(env, 'show', '-json', PLAN.name)
    if shown.returncode:
        PLAN.unlink(missing_ok=True)
        print('POLICY_PLAN_GATE=BLOCKED; REASON=INSPECTION_FAILED')
        return 1
    try:
        changes = json.loads(shown.stdout).get('resource_changes', [])
        mutated = [item for item in changes if item.get('change', {}).get('actions') not in (["read"], ["no-op"])]
        allowed = len(mutated) == 1 and mutated[0].get('address') == SUBJECT and mutated[0]['change']['actions'] == ['create'] and mutated[0]['change'].get('after', {}).get('subject_name') == SUBJECT_NAME and mutated[0]['change'].get('after', {}).get('compatibility_level') == 'BACKWARD'
    except (ValueError, KeyError, TypeError): allowed = False
    print('ONLY_SUBJECT_POLICY_CREATE=', allowed)
    print('SECRETS_PRINTED=False')
    if not allowed:
        PLAN.unlink(missing_ok=True)
        print('POLICY_PLAN_GATE=BLOCKED')
        return 1
    print('POLICY_PLAN_GATE=PASS')
    return 0


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Planeja politica BACKWARD; nao aplica.')
    parser.parse_args(argv)
    return main()

if __name__ == '__main__':
    try: raise SystemExit(cli())
    except Exception as error:
        print('ERROR_TYPE=', type(error).__name__)
        print('POLICY_PLAN_GATE=BLOCKED')
        raise SystemExit(1)
