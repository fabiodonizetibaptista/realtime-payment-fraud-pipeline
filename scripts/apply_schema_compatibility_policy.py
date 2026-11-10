"""Aplica somente o plano aprovado da politica BACKWARD.

Seguranca:
- Nao executa terraform apply geral.
- Confere as alteracoes do plano antes de executar.
- Nao imprime stdout/stderr do Terraform.
- Nao imprime credenciais, schemas ou Terraform State.
"""

import json
import os
import subprocess
from pathlib import Path

from safety import load_env_file

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "stage6-subject-config.tfplan"

ADDRESS = "confluent_subject_config.transactions_value"
SUBJECT = "payments.public.transactions-value"


def terraform(env, *args):
    return subprocess.run(
        ["terraform", *args],
        cwd=TF_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main():
    print("========== ETAPA 6 — APPLY SUBJECT POLICY ==========")

    # A seguranca do apply depende do plano Terraform aprovado,
    # nao do nome da branch Git utilizada pelo operador.
    if not PLAN.is_file():
        raise RuntimeError("APPROVED_PLAN_NOT_FOUND")

    config = load_env_file(ROOT / ".env")
    env = dict(os.environ)

    for key, value in config.items():
        if value and not env.get(key):
            env[key] = value

    env.update({
        "TF_LOG": "OFF",
        "TF_INPUT": "0",
        "TF_VAR_enable_cdc_connector": "false",
        "TF_VAR_enable_cdc_acls": "true",
        "TF_VAR_enable_kafka_acls": "true",
    })

    if config.get("CDC_PGPASSWORD"):
        env["TF_VAR_cdc_connector_password"] = config["CDC_PGPASSWORD"]

    # Reconfirma que o plano salvo contem somente a mudanca autorizada.
    inspection = terraform(env, "show", "-json", PLAN.name)

    if inspection.returncode != 0:
        raise RuntimeError("PLAN_INSPECTION_FAILED")

    data = json.loads(inspection.stdout)

    changes = [
        item
        for item in data.get("resource_changes", [])
        if item.get("change", {}).get("actions")
        not in (["no-op"], ["read"])
    ]

    approved = (
        len(changes) == 1
        and changes[0].get("address") == ADDRESS
        and changes[0].get("change", {}).get("actions") == ["create"]
        and (
            changes[0].get("change", {}).get("after") or {}
        ).get("subject_name") == SUBJECT
        and (
            changes[0].get("change", {}).get("after") or {}
        ).get("compatibility_level") == "BACKWARD"
    )

    print("APPROVED_PLAN_VALID=", approved)
    print("PLANNED_CHANGES=", len(changes))

    if not approved:
        raise RuntimeError("UNEXPECTED_PLAN_CONTENT")

    print("APPLY_SCOPE=SUBJECT_CONFIG_ONLY")

    # Executa exatamente o plano autorizado, nunca um apply sem plano.
    result = terraform(
        env,
        "apply",
        "-input=false",
        "-no-color",
        "-auto-approve",
        PLAN.name,
    )

    print("TERRAFORM_APPLY_EXIT_CODE=", result.returncode)

    if result.returncode != 0:
        # Analisa os erros apenas em memoria. Nunca imprime logs brutos,
        # endpoints, payloads, tokens ou credenciais do Terraform.
        import re

        diagnostic = (result.stderr + "\n" + result.stdout).lower()

        if re.search(r"\\b403\\b|forbidden|permission denied|not authorized", diagnostic):
            category = "HTTP_403_AUTHORIZATION"
        elif re.search(r"\\b401\\b|unauthorized|authentication failed", diagnostic):
            category = "HTTP_401_AUTHENTICATION"
        elif re.search(r"\\b409\\b|conflict|already exists", diagnostic):
            category = "HTTP_409_CONFLICT"
        elif re.search(r"\\b400\\b|bad request|invalid compatibility", diagnostic):
            category = "HTTP_400_INVALID_REQUEST"
        elif re.search(r"\\b404\\b|not found", diagnostic):
            category = "HTTP_404_NOT_FOUND"
        elif re.search(r"timeout|connection refused|network|dial tcp|tls handshake", diagnostic):
            category = "NETWORK_ERROR"
        elif re.search(r"provider configuration|missing required argument|invalid provider", diagnostic):
            category = "PROVIDER_CONFIGURATION"
        elif re.search(r"stale plan|saved plan is stale", diagnostic):
            category = "STALE_PLAN"
        else:
            category = "UNCLASSIFIED_TERRAFORM_ERROR"

        print("APPLY_ERROR_CATEGORY=", category)
        print("ERROR_OUTPUT_REDACTED=True")
        print("SENSITIVE_DETAILS_PRINTED=False")
        raise RuntimeError("APPLY_FAILED_CHECK_REMOTE_STATE_BEFORE_RETRY")

    # Confirma a politica gravada no State sem exibir o conteudo dele.
    state_result = terraform(env, "state", "pull")

    if state_result.returncode != 0:
        raise RuntimeError("STATE_VERIFICATION_FAILED")

    state = json.loads(state_result.stdout)

    matches = [
        instance.get("attributes") or {}
        for resource in state.get("resources", [])
        if resource.get("type") == "confluent_subject_config"
        and resource.get("name") == "transactions_value"
        for instance in resource.get("instances", [])
    ]

    verified = (
        len(matches) == 1
        and matches[0].get("subject_name") == SUBJECT
        and matches[0].get("compatibility_level") == "BACKWARD"
    )

    print("SUBJECT_POLICY_IN_STATE=", verified)
    print("POLICY_BACKWARD=", verified)
    print("SCHEMA_VERSIONS_CHANGED=False")
    print("CDC_CONNECTOR_ACTIVATED=False")
    print("SECRETS_PRINTED=False")

    if not verified:
        raise RuntimeError("POLICY_STATE_MISMATCH")

    PLAN.unlink()

    print("TEMPORARY_PLAN_REMOVED=True")
    print("STAGE6_POLICY_APPLY_GATE=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("STAGE6_POLICY_APPLY_GATE=BLOCKED")
        raise SystemExit(1)
