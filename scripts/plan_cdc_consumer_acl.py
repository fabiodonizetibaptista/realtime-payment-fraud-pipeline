"""Planeja somente a nova ACL CDC, sem imprimir segredos."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "stage5-consumer-acl.tfplan"
ADDRESS = "confluent_kafka_acl.consumer_payments_topic_read[0]"


def run(*args, env):
    return subprocess.run(
        ["terraform", *args],
        cwd=TF_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main():
    print("========== PLAN CDC CONSUMER ACL ==========")

    config = load_env_file(ROOT / ".env")
    env = dict(os.environ)

    for key, value in config.items():
        if value and not env.get(key):
            env[key] = value

    env.update({
        "TF_LOG": "OFF",
        "TF_VAR_enable_cdc_connector": "false",
        "TF_VAR_enable_cdc_acls": "true",
        "TF_VAR_enable_kafka_acls": "true",
    })

    # O conector da Etapa 4 deve continuar ausente do State.
    state = run("state", "list", env=env)

    if state.returncode != 0:
        print("STATE_GATE=BLOCKED")
        return 1

    addresses = set(state.stdout.splitlines())

    if "confluent_connector.payments_cdc[0]" in addresses:
        print("CONNECTOR_GATE=BLOCKED")
        return 1

    if ADDRESS in addresses:
        print("ACL_ALREADY_MANAGED=True")
        print("PLAN_GATE=BLOCKED")
        return 1

    if PLAN.exists():
        print("PLAN_GATE=BLOCKED")
        print("REASON=EXISTING_PLAN")
        return 1

    old_umask = os.umask(0o077)

    try:
        planned = run(
            "plan",
            "-input=false",
            "-no-color",
            "-out=stage5-consumer-acl.tfplan",
            env=env,
        )
    finally:
        os.umask(old_umask)

    if planned.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("TERRAFORM_PLAN_OK=False")
        print("PLAN_EXIT_CODE=", planned.returncode)
        print("PLAN_GATE=BLOCKED")
        return 1

    inspected = run(
        "show", "-json", PLAN.name, env=env
    )

    if inspected.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("PLAN_INSPECTION=BLOCKED")
        return 1

    data = json.loads(inspected.stdout)

    changes = [
        (
            item.get("address"),
            item.get("change", {}).get("actions"),
        )
        for item in data.get("resource_changes", [])
        if item.get("change", {}).get("actions")
        not in (["no-op"], ["read"])
    ]

    # Diagnostico restrito a nomes de recursos e atributos de ACL.
    # Nunca exibir o plano completo, IDs, principal ou credenciais.
    print("========== DIAGNOSTICO DO PLANO ==========")

    for item in data.get("resource_changes", []):
        actions = item.get("change", {}).get("actions", [])

        if actions in (["no-op"], ["read"]):
            continue

        print("RESOURCE_ADDRESS=", item.get("address"))
        print("RESOURCE_ACTIONS=", actions)

        if item.get("type") == "confluent_kafka_acl":
            after = item.get("change", {}).get("after") or {}

            for field in (
                "resource_type",
                "resource_name",
                "pattern_type",
                "operation",
                "permission",
            ):
                value = after.get(field)
                print(
                    f"ACL_{field.upper()}=",
                    value if isinstance(value, str) else "UNRESOLVED",
                )

    print("DIAGNOSTIC_SECRETS_PRINTED=False")

    only_create = changes == [(ADDRESS, ["create"])]

    # Verifica o destino e as permissoes no plano,
    # sem imprimir principal, credenciais ou outros atributos.
    acl = next(
        (
            item.get("change", {}).get("after", {})
            for item in data.get("resource_changes", [])
            if item.get("address") == ADDRESS
        ),
        {},
    )

    config_valid = all([
        acl.get("resource_type") == "TOPIC",
        acl.get("resource_name") == "payments.",
        acl.get("pattern_type") == "PREFIXED",
        acl.get("operation") == "READ",
        acl.get("permission") == "ALLOW",
    ])

    # Confirma que a ACL utiliza exatamente o principal
    # da Service Account existente.
    current = run("state", "pull", env=env)
    identity_valid = False

    if current.returncode == 0:
        state_data = json.loads(current.stdout)
        consumer_ids = {
            instance.get("attributes", {}).get("id")
            for resource in state_data.get("resources", [])
            if (
                resource.get("type") == "confluent_service_account"
                and "consumer" in resource.get("name", "").lower()
            )
            for instance in resource.get("instances", [])
        }
        consumer_ids.discard(None)

        identity_valid = (
            len(consumer_ids) == 1
            and acl.get("principal") == (
                "User:" + next(iter(consumer_ids))
            )
        )

    print("PLANNED_CHANGES=", len(changes))
    print("ONLY_NEW_CONSUMER_ACL=", only_create)
    print("ACL_CONFIGURATION_VALID=", config_valid)
    print("CONSUMER_IDENTITY_VALID=", identity_valid)
    print("FOUNDATION_MUTATIONS=", sum(
        address != ADDRESS for address, _ in changes
    ))
    print("CONNECTOR_REMAINS_OFF=True")
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")

    passed = only_create and config_valid and identity_valid

    if not passed:
        PLAN.unlink(missing_ok=True)

    print("PLAN_GATE=", "PASS" if passed else "BLOCKED")
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("PLAN_GATE=BLOCKED")
        raise SystemExit(1)
