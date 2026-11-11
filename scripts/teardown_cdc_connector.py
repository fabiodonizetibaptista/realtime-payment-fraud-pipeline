"""Destruicao controlada SOMENTE do conector CDC da Etapa 4.

Nunca executa destruicao sem --execute.
Nao remove PostgreSQL, Kafka, Service Accounts ou ACLs.
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
from scripts.cdc_stage_flags import configure_flags

TF_DIR = ROOT / "infra" / "terraform"
ADDRESS = "confluent_connector.payments_cdc[0]"
PLAN = TF_DIR / "cdc-teardown.tfplan"


def run(args, env):
    return subprocess.run(
        args,
        cwd=TF_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not args.execute:
        print("TEARDOWN_EXECUTED=False")
        print("USE=python scripts/teardown_cdc_connector.py --execute")
        return 0

    config = load_env_file(ROOT / ".env")
    password = config.get("CDC_PGPASSWORD")

    if not password:
        print("TEARDOWN_GATE=BLOCKED")
        print("REASON=CDC_PASSWORD_MISSING")
        return 1

    env = dict(os.environ)
    for key, value in config.items():
        if value and not env.get(key):
            env[key] = value

    configure_flags(env, connector="auto", subject="auto")
    env["TF_VAR_cdc_connector_password"] = password

    print("========== CDC TEARDOWN ==========")

    # Verifica o alvo no State antes de planejar a destruicao.
    state = run(["terraform", "state", "list"], env)

    if state.returncode != 0:
        print("STATE_GATE=BLOCKED")
        return 1

    addresses = set(state.stdout.splitlines())

    if ADDRESS not in addresses:
        print("CONNECTOR_IN_STATE=False")
        print("TEARDOWN_GATE=NO_RESOURCE_IN_STATE")
        return 0

    if PLAN.exists():
        print("TEARDOWN_GATE=BLOCKED")
        print("REASON=EXISTING_PLAN")
        return 1

    # Planos Terraform podem conter segredos.
    # Restringe as permissoes na criacao do arquivo.
    previous_umask = os.umask(0o077)

    try:
        planned = run([
            "terraform", "plan",
            "-destroy",
            f"-target={ADDRESS}",
            "-input=false",
            "-no-color",
            "-out=cdc-teardown.tfplan",
        ], env)
    finally:
        os.umask(previous_umask)

    if planned.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("DESTROY_PLAN_GATE=BLOCKED")
        return 1

    shown = run([
        "terraform", "show", "-json",
        "cdc-teardown.tfplan",
    ], env)

    if shown.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("DESTROY_PLAN_INSPECTION=BLOCKED")
        return 1

    try:
        data = json.loads(shown.stdout)
        changes = [
            (
                item.get("address"),
                item.get("change", {}).get("actions"),
            )
            for item in data.get("resource_changes", [])
            if item.get("change", {}).get("actions")
            not in (["no-op"], ["read"])
        ]

        allowed = changes == [(ADDRESS, ["delete"])]

        print("PLANNED_CHANGES=", len(changes))
        print("ONLY_CONNECTOR_DELETE=", allowed)

        if not allowed:
            print("TEARDOWN_GATE=BLOCKED")
            return 1

        applied = run([
            "terraform", "apply",
            "-input=false",
            "-no-color",
            "cdc-teardown.tfplan",
        ], env)

        print("TERRAFORM_APPLY_SUCCESS=", applied.returncode == 0)

        if applied.returncode != 0:
            print("TEARDOWN_GATE=BLOCKED")
            return 1

        final_state = run(["terraform", "state", "list"], env)

        absent = (
            final_state.returncode == 0
            and ADDRESS not in final_state.stdout.splitlines()
        )

        print("CONNECTOR_ABSENT_FROM_STATE=", absent)
        print("SECRETS_PRINTED=False")
        print("TEARDOWN_GATE=", "PASS" if absent else "BLOCKED")

        return 0 if absent else 1

    finally:
        PLAN.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("TEARDOWN_GATE=BLOCKED")
        raise SystemExit(1)
