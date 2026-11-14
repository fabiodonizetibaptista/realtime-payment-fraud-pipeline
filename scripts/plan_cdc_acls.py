"""Planeja as 11 ACLs CDC/Kafka antes de ativar o conector (somente leitura)."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import discard_stale_plan, load_env_file
from scripts.cdc_stage_flags import configure_flags, changes_in_plan, CONNECTOR

TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "cdc-acls-preconnector.tfplan"

# Enderecos explicitamente previstos no HCL desta revisao. Nao permite drift,
# exclusoes, substituicoes nem outras criacoes em infraestrutura permanente.
EXPECTED = frozenset({
    'confluent_kafka_acl.cdc_cluster_describe[0]',
    'confluent_kafka_acl.cdc_cluster_describe_configs[0]',
    'confluent_kafka_acl.cdc_heartbeat["CREATE"]',
    'confluent_kafka_acl.cdc_heartbeat["DESCRIBE"]',
    'confluent_kafka_acl.cdc_heartbeat["WRITE"]',
    'confluent_kafka_acl.cdc_topic_create[0]',
    'confluent_kafka_acl.cdc_topic_write[0]',
    'confluent_kafka_acl.consumer_group_read[0]',
    'confluent_kafka_acl.consumer_payments_topic_read[0]',
    'confluent_kafka_acl.consumer_topic_read[0]',
    'confluent_kafka_acl.producer_topic_write[0]',
})


def terraform(env, *args):
    return subprocess.run(["terraform", *args], cwd=TF_DIR, env=env,
                          capture_output=True, text=True, check=False, timeout=120)


def approved_acl_plan(data, existing):
    changes = changes_in_plan(data)
    expected_missing = EXPECTED - existing
    # Atualizacoes, destruicoes, criacoes inesperadas e plano parcial sao bloqueados.
    return bool(expected_missing) and len(changes) == len(expected_missing) and all(
        address in expected_missing and actions == ["create"]
        for address, actions in changes
    ) and {address for address, _ in changes} == expected_missing


def main():
    discard_stale_plan(PLAN)
    cfg = load_env_file(ROOT / '.env')
    env = dict(os.environ)
    for key, val in cfg.items():
        if val and not env.get(key):
            env[key] = val
    try:
        addresses = configure_flags(env, connector='off', subject='auto')
    except (RuntimeError, subprocess.TimeoutExpired):
        print('ACL_PLAN_GATE=BLOCKED; REASON=STATE_UNAVAILABLE')
        return 1
    if CONNECTOR in addresses:
        print('ACL_PLAN_GATE=BLOCKED; REASON=CONNECTOR_ALREADY_ACTIVE')
        return 1
    if EXPECTED <= addresses:
        print('ACL_PLAN_GATE=ALREADY_READY; MISSING_ACLS=0')
        return 0
    # Nao habilita conector. O subject fica desligado enquanto ainda nao existe.
    old = os.umask(0o077)
    try:
        result = terraform(env, 'plan', '-input=false', '-no-color', '-out=cdc-acls-preconnector.tfplan')
    finally:
        os.umask(old)
    if result.returncode:
        PLAN.unlink(missing_ok=True)
        print('ACL_PLAN_GATE=BLOCKED; REASON=TERRAFORM_PLAN_FAILED')
        return 1
    shown = terraform(env, 'show', '-json', PLAN.name)
    if shown.returncode:
        PLAN.unlink(missing_ok=True)
        print('ACL_PLAN_GATE=BLOCKED; REASON=PLAN_INSPECTION_FAILED')
        return 1
    try:
        data = json.loads(shown.stdout)
        allowed = approved_acl_plan(data, addresses)
    except (ValueError, TypeError, KeyError):
        allowed = False
    print('EXPECTED_MISSING_ACLS=', len(EXPECTED - addresses))
    print('PLANNED_CHANGES=', len(changes_in_plan(data)) if 'data' in locals() else -1)
    print('ONLY_EXPECTED_ACL_CREATES=', allowed)
    print('CONNECTOR_REMAINS_OFF=True')
    print('SECRETS_PRINTED=False')
    if not allowed:
        PLAN.unlink(missing_ok=True)
        print('ACL_PLAN_GATE=BLOCKED')
        return 1
    print('ACL_PLAN_GATE=PASS')
    return 0


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Planeja ACLs previas ao conector CDC, sem executar apply.')
    parser.parse_args(argv)
    return main()


if __name__ == '__main__':
    try:
        raise SystemExit(cli())
    except Exception as error:
        print('ERROR_TYPE=', type(error).__name__)
        print('ACL_PLAN_GATE=BLOCKED')
        raise SystemExit(1)
