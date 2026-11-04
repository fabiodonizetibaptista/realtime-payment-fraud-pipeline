"""Prepara o plano Terraform do CDC sem criar recursos remotos."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "cdc-stage4.tfplan"
EXPECTED = "confluent_connector.payments_cdc[0]"


def main():
    print("========== ETAPA 4 — ATIVIDADE 3 ==========")

    if PLAN.exists():
        print("PLAN_ALREADY_EXISTS=True")
        print("PLAN_GATE=BLOCKED")
        return 1

    env_file = load_env_file(ROOT / ".env")
    password = env_file.get("CDC_PGPASSWORD", "")

    if not password:
        print("CDC_CREDENTIAL_PRESENT=False")
        print("PLAN_GATE=BLOCKED")
        return 1

    execution_env = dict(os.environ)

    for key, value in env_file.items():
        if value and not execution_env.get(key):
            execution_env[key] = value

    execution_env.update({
        "TF_LOG": "OFF",
        "TF_VAR_enable_cdc_connector": "true",
        "TF_VAR_enable_cdc_acls": "true",
        "TF_VAR_enable_kafka_acls": "true",
        "TF_VAR_cdc_connector_password": password,
    })

    print("CDC_CREDENTIAL_PRESENT=True")
    print("FOUNDATION_ACLS_PRESERVED=True")

    command = [
        "terraform", "plan",
        "-input=false",
        "-no-color",
        "-out=cdc-stage4.tfplan",
    ]

    result = subprocess.run(
        command,
        cwd=TF_DIR,
        env=execution_env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("TERRAFORM_PLAN_OK=False")
        print("PLAN_EXIT_CODE=", result.returncode)

        # Classifica os erros sem imprimir mensagens brutas do provider.
        # Mensagens podem conter valores de configuracao e credenciais.
        import re

        diagnostic = result.stdout + "\n" + result.stderr
        headings = re.findall(
            r"Error:\\s*([^\\r\\n]+)", diagnostic
        )

        patterns = {
            "INVALID_REFERENCE": r"reference to undeclared",
            "UNSUPPORTED_ARGUMENT": r"unsupported argument",
            "INVALID_VALUE": r"invalid value|invalid function",
            "MISSING_ARGUMENT": r"missing required argument",
            "INVALID_BLOCK": r"unsupported block",
            "PROVIDER_AUTH": r"authentication|unauthorized|forbidden|401|403",
            "PROVIDER_CONFIGURATION": r"provider configuration",
            "PROVIDER_CONNECTION": r"connection refused|timeout|connection error",
            "VARIABLE_ERROR": r"input variable|variable",
            "RESOURCE_PRECONDITION": r"precondition",
        }

        for index, heading in enumerate(headings[:5], 1):
            category = next(
                (
                    name for name, pattern in patterns.items()
                    if re.search(pattern, heading, re.IGNORECASE)
                ),
                "OTHER_TERRAFORM_ERROR",
            )
            print(f"ERROR_{index}_CATEGORY={category}")

        print("ERROR_COUNT=", len(headings))
        print("AIVEN_TOKEN_PRESENT=", bool(execution_env.get("AIVEN_TOKEN")))
        print("CONFLUENT_CLOUD_AUTH_PRESENT=", all(
            execution_env.get(key)
            for key in (
                "CONFLUENT_CLOUD_API_KEY",
                "CONFLUENT_CLOUD_API_SECRET",
            )
        ))
        print("ERROR_DETAILS_REDACTED=True")
        print("PLAN_GATE=BLOCKED")
        return 1

    show = subprocess.run(
        ["terraform", "show", "-json", str(PLAN)],
        cwd=TF_DIR,
        env=execution_env,
        capture_output=True,
        text=True,
        check=False,
    )

    if show.returncode != 0:
        PLAN.unlink(missing_ok=True)
        print("PLAN_INSPECTION_OK=False")
        print("PLAN_GATE=BLOCKED")
        return 1

    changes = json.loads(show.stdout).get(
        "resource_changes", []
    )

    mutations = [
        (item.get("address"), item.get("change", {}).get("actions"))
        for item in changes
        if item.get("change", {}).get("actions")
        not in (["no-op"], ["read"])
    ]

    allowed = mutations == [(EXPECTED, ["create"])]

    print("PLANNED_CHANGES=", len(mutations))
    print("ONLY_CDC_CONNECTOR_CREATE=", allowed)
    print("FOUNDATION_MUTATIONS=", sum(
        address != EXPECTED
        for address, _ in mutations
    ))
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")

    if not allowed:
        for address, actions in mutations:
            print("CHANGE_ADDRESS=", address)
            print("CHANGE_ACTION=", ",".join(actions))
        PLAN.unlink(missing_ok=True)
        print("PLAN_GATE=BLOCKED")
        return 1

    print("PLAN_GATE=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("PLAN_GATE=BLOCKED")
        raise SystemExit(1)
