"""Aplica SOMENTE o plano ACL previamente aprovado, nunca um apply geral."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file
from scripts.cdc_stage_flags import configure_flags, changes_in_plan, CONNECTOR
from scripts.plan_cdc_acls import PLAN, EXPECTED, approved_acl_plan

TF_DIR = ROOT / 'infra' / 'terraform'


def terraform(env, *args):
    return subprocess.run(['terraform', *args], cwd=TF_DIR, env=env,
                          capture_output=True, text=True, check=False, timeout=180)


def main():
    if not PLAN.is_file():
        print('ACL_APPLY_GATE=BLOCKED; REASON=APPROVED_PLAN_MISSING')
        return 1
    config = load_env_file(ROOT / '.env')
    env = dict(os.environ)
    for key, val in config.items():
        if val and not env.get(key): env[key] = val
    try:
        before = configure_flags(env, connector='off', subject='auto')
    except (RuntimeError, subprocess.TimeoutExpired):
        print('ACL_APPLY_GATE=BLOCKED; REASON=STATE_UNAVAILABLE')
        return 1
    if CONNECTOR in before:
        print('ACL_APPLY_GATE=BLOCKED; REASON=CONNECTOR_ACTIVE')
        return 1
    shown = terraform(env, 'show', '-json', PLAN.name)
    if shown.returncode:
        print('ACL_APPLY_GATE=BLOCKED; REASON=PLAN_INSPECTION_FAILED')
        return 1
    try:
        data = json.loads(shown.stdout)
        allowed = approved_acl_plan(data, before)
    except (ValueError, TypeError):
        allowed = False
    print('ONLY_EXPECTED_ACL_CREATES=', allowed)
    if not allowed:
        print('ACL_APPLY_GATE=BLOCKED')
        return 1
    applied = terraform(env, 'apply', '-input=false', '-no-color', PLAN.name)
    if applied.returncode:
        print('ACL_APPLY_GATE=BLOCKED; REASON=APPLY_FAILED_CHECK_STATE')
        return 1
    state = terraform(env, 'state', 'list')
    verified = state.returncode == 0 and EXPECTED <= set(state.stdout.splitlines())
    print('ACL_RESOURCES_IN_STATE=', verified)
    print('SECRETS_PRINTED=False')
    if not verified:
        print('ACL_APPLY_GATE=BLOCKED')
        return 1
    PLAN.unlink(missing_ok=True)
    print('ACL_APPLY_GATE=PASS')
    return 0


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Aplica somente ACLs aprovadas por plan_cdc_acls.py.')
    parser.add_argument('--confirm-acls', action='store_true', required=True)
    parser.parse_args(argv)
    return main()

if __name__ == '__main__':
    try: raise SystemExit(cli())
    except Exception as error:
        print('ERROR_TYPE=', type(error).__name__)
        print('ACL_APPLY_GATE=BLOCKED')
        raise SystemExit(1)
