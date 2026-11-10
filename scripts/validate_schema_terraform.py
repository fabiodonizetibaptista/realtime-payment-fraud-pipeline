"""Valida drift do Terraform apos importar os 12 contratos CDC.

Nao executa apply. Nao imprime schemas, credenciais nem State.
Exibe somente enderecos e tipos de alteracoes, caso existam.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
PLAN = TF_DIR / "stage6-schema-validation.tfplan"

sys.path.insert(0, str(ROOT))
from safety import load_env_file


def terraform(*args, env):
    return subprocess.run(
        ["terraform", *args],
        cwd=TF_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main():
    print("========== ETAPA 6 — VALIDACAO SCHEMA IAC ==========")

    if PLAN.exists():
        print("VALIDATION_GATE=BLOCKED")
        print("REASON=PLAN_ALREADY_EXISTS")
        return 1

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

    # Terraform pode precisar dessa variavel mesmo com o
    # conector desligado. Nunca exibir seu valor.
    if config.get("CDC_PGPASSWORD"):
        env["TF_VAR_cdc_connector_password"] = config["CDC_PGPASSWORD"]

    old_umask = os.umask(0o077)

    try:
        result = terraform(
            "plan",
            "-input=false",
            "-no-color",
            "-out=stage6-schema-validation.tfplan",
            env=env,
        )
    finally:
        os.umask(old_umask)

    if result.returncode != 0:
        import re

        # Diagnostico por classificacao: nunca imprimir a
        # mensagem bruta do Terraform ou do provider.
        diagnostic = result.stdout + "\n" + result.stderr

        categories = {
            "PREVENT_DESTROY": r"prevent_destroy|prevented by lifecycle",
            "SCHEMA_VALIDATION": r"schema.*validat|invalid schema|avro",
            "SCHEMA_COMPATIBILITY": r"incompatible|compatibility",
            "RESOURCE_CONFIGURATION": r"unsupported argument|missing required argument|unsupported block",
            "RESOURCE_REFERENCE": r"undeclared resource|reference to undeclared",
            "PROVIDER_INCONSISTENCY": r"inconsistent result|provider produced",
            "PROVIDER_AUTHORIZATION": r"unauthorized|forbidden|permission denied|403|401",
            "PROVIDER_CONNECTION": r"timeout|connection refused|connection reset",
            "VARIABLE_ERROR": r"no value for required variable|invalid value for input variable",
            "STATE_ERROR": r"error acquiring the state lock|state snapshot|state lock",
            "RESOURCE_REFRESH": r"error reading|failed to read|unable to read",
        }

        found = [
            name for name, pattern in categories.items()
            if re.search(pattern, diagnostic, re.IGNORECASE)
        ]

        # Nomes de arquivos conhecidos apenas, sem caminhos
        # arbitrarios ou linhas que possam conter segredos.
        locations = [
            name
            for name in (
                "cdc-schemas.tf",
                "cdc-connector.tf",
                "consumer-cdc-acl.tf",
            )
            if name in diagnostic
        ]

        print("TERRAFORM_PLAN_OK=False")
        print("PLAN_EXIT_CODE=", result.returncode)
        print("ERROR_CATEGORIES=", ",".join(found) if found else "UNCLASSIFIED")
        print("CONFIG_FILES_REFERENCED=", ",".join(locations) if locations else "NONE")
        print("DIAGNOSTIC_AVAILABLE=", bool(diagnostic.strip()))
        print("ERROR_DETAILS_REDACTED=True")
        print("VALIDATION_GATE=BLOCKED")
        PLAN.unlink(missing_ok=True)
        return 1

    result = terraform(
        "show", "-json", PLAN.name, env=env
    )

    if result.returncode != 0:
        print("PLAN_INSPECTION=BLOCKED")
        PLAN.unlink(missing_ok=True)
        return 1

    data = json.loads(result.stdout)

    changes = [
        (
            item.get("address"),
            item.get("change", {}).get("actions"),
        )
        for item in data.get("resource_changes", [])
        if item.get("change", {}).get("actions")
        not in (["no-op"], ["read"])
    ]

    schema_changes = [
        (address, actions)
        for address, actions in changes
        if address and address.startswith("confluent_schema.cdc[")
    ]

    state = terraform("state", "list", env=env)

    managed_schemas = (
        [
            address
            for address in state.stdout.splitlines()
            if address.startswith("confluent_schema.cdc[")
        ]
        if state.returncode == 0
        else []
    )

    for address, actions in changes:
        # Endereco Terraform e operacao apenas; sem valores
        # de schema, IDs, principals ou segredos.
        print("PLANNED_RESOURCE=", address)
        print("PLANNED_ACTION=", actions)

    print("SCHEMAS_IN_STATE=", len(managed_schemas))
    print("SCHEMA_MUTATIONS=", len(schema_changes))
    print("TOTAL_PLANNED_MUTATIONS=", len(changes))
    print("FOUNDATION_MUTATIONS=", len(changes) - len(schema_changes))
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")

    # Nao manter plano contendo credenciais.
    PLAN.unlink(missing_ok=True)
    print("TEMPORARY_PLAN_REMOVED=True")

    passed = (
        len(managed_schemas) == 12
        and len(changes) == 0
    )

    print("SCHEMA_IAC_GATE=", "PASS" if passed else "BLOCKED")
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        PLAN.unlink(missing_ok=True)
        print("SCHEMA_IAC_GATE=BLOCKED")
        raise SystemExit(1)
