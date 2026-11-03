"""Comandos locais do laboratorio de pagamentos."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Sequence

from safety import (
    changed_resources,
    merge_env_file,
    run_command,
    secret_values,
    validate_apply_allowlist,
)

ROOT = Path(__file__).resolve().parent
TF_DIR = ROOT / "infra" / "terraform"
ENV_FILE = ROOT / ".env"
MIN_TERRAFORM_VERSION = (1, 16, 0)
MIN_CONFLUENT_VERSION = (4, 81, 0)

FOUNDATION_APPLY_RESOURCES = frozenset({
    "confluent_environment.challenge",
    "confluent_kafka_cluster.basic",
    "confluent_service_account.iac_admin",
    "confluent_service_account.producer",
    "confluent_service_account.consumer",
    "confluent_service_account.schema_registry",
    "confluent_service_account.cdc",
    "confluent_role_binding.iac_admin_cluster_admin",
    "confluent_role_binding.schema_registry_subject_read",
    "confluent_role_binding.schema_registry_subject_write",
    "confluent_api_key.iac_admin_kafka",
    "confluent_api_key.producer_kafka",
    "confluent_api_key.consumer_kafka",
    "confluent_api_key.schema_registry",
})

# --help e local, nao exige login nem consulta recursos remotos.
CLI_HELP_COMMANDS = (
    ("environment", "list"),
    ("kafka", "cluster", "list"),
    ("iam", "service-account", "list"),
    ("kafka", "acl", "list"),
    ("kafka", "topic", "list"),
    ("kafka", "topic", "consume"),
    ("connect", "cluster", "list"),
    ("flink", "compute-pool", "list"),
    ("flink", "statement", "list"),
    ("schema-registry", "schema", "compatibility", "validate"),
    ("billing", "cost", "list"),
)
# Estas flags aparecem nas variantes Platform e Cloud sem exigir login.
# Flags especificas de ACL no Cloud serao verificadas no primeiro marco com login.
CLI_REQUIRED_FLAGS = {
    ("schema-registry", "schema", "compatibility", "validate"): ("--subject", "--type"),
    ("billing", "cost", "list"): ("--start-date", "--end-date"),
}


def check_cli_help() -> None:
    for command in CLI_HELP_COMMANDS:
        help_text = run_command(["confluent", *command, "--help"], cwd=ROOT)
        missing = [flag for flag in CLI_REQUIRED_FLAGS.get(command, ()) if flag not in help_text]
        if missing:
            raise RuntimeError("Flags esperadas ausentes em confluent " + " ".join(command) + ": " + ", ".join(missing))


def _version_parts(value: object, tool: str) -> tuple[int, int, int]:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)", str(value))
    if not match:
        raise RuntimeError(f"Nao foi possivel identificar a versao do {tool}.")
    return tuple(int(part) for part in match.groups())


def _check_minimum_version(tool: str, found: object, minimum: tuple[int, int, int]) -> None:
    parsed = _version_parts(found, tool)
    minimum_text = ".".join(str(part) for part in minimum)
    if parsed < minimum:
        raise RuntimeError(f"{tool} >= {minimum_text} requerido; encontrado {found}.")
    if parsed != minimum:
        print(f"Aviso: {tool} encontrado {found}; minimo declarado {minimum_text}.")


def _check_versions() -> None:
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 ou superior e obrigatorio.")
    tf = run_command(["terraform", "version", "-json"], cwd=ROOT)
    found_tf = json.loads(tf).get("terraform_version")
    _check_minimum_version("Terraform", found_tf, MIN_TERRAFORM_VERSION)
    cli = run_command(["confluent", "version"], cwd=ROOT)
    _check_minimum_version("Confluent CLI", cli, MIN_CONFLUENT_VERSION)


def setup() -> None:
    """Marco 1: prepara somente o ambiente local; nao executa plan/apply."""
    # Codespaces Secrets ja chegam no ambiente. O .env e opcional e nunca
    # pode apagar ou substituir valores definidos pelo ambiente de execucao.
    merge_env_file(ENV_FILE, os.environ)
    secrets = secret_values(os.environ)
    _check_versions()
    execution_env = dict(os.environ)
    # Prevent inherited Terraform debug logging from exposing provider payloads.
    execution_env["TF_LOG"] = "OFF"
    run_command(["terraform", "init", "-lockfile=readonly"],
                cwd=TF_DIR, env=execution_env, secrets=secrets)
    result = run_command(["terraform", "validate", "-no-color"],
                         cwd=TF_DIR, env=execution_env, secrets=secrets)
    check_cli_help()
    if result.strip():
        print(result.strip())
    print("BOOTSTRAP_LOCAL_OK; nenhum recurso remoto foi consultado ou alterado.")


def plan() -> None:
    """Gera um plano local revisavel; nao cria nem altera recursos remotos."""
    merge_env_file(ENV_FILE, os.environ)
    execution_env = dict(os.environ)
    execution_env["TF_LOG"] = "OFF"
    secrets = secret_values(execution_env)
    result = run_command(
        ["terraform", "plan", "-no-color", "-out=foundation.tfplan"],
        cwd=TF_DIR, env=execution_env, secrets=secrets,
    )
    if result.strip():
        print(result.strip())
    print("FOUNDATION_PLAN_READY=True; nenhum recurso remoto foi criado ou alterado.")


def validate_foundation_plan(plan: dict) -> list[str]:
    """Aceita somente a criacao exata dos recursos da primeira Foundation."""
    if plan.get("errored") is True:
        raise RuntimeError("O plano Terraform esta marcado como erro.")

    changes = changed_resources(plan)
    addresses = [str(item.get("address", "")) for item in changes]

    if len(addresses) != len(set(addresses)):
        raise RuntimeError("O plano contem enderecos de recursos duplicados.")

    actual = set(addresses)
    missing = sorted(FOUNDATION_APPLY_RESOURCES - actual)
    unexpected = sorted(actual - FOUNDATION_APPLY_RESOURCES)

    if missing or unexpected:
        raise RuntimeError(
            "Plano Foundation divergente. "
            f"AUSENTES={missing}; NAO_AUTORIZADOS={unexpected}"
        )

    non_create = []
    for item in changes:
        actions = item.get("change", {}).get("actions", [])
        if actions != ["create"]:
            non_create.append(
                f"{item.get('address', '')}: {actions}"
            )

    if non_create:
        raise RuntimeError(
            "Apply bloqueado: somente criacoes sao permitidas. "
            + "; ".join(non_create)
        )

    # Mantem a allowlist central de safety.py como segunda barreira.
    validate_apply_allowlist(plan, FOUNDATION_APPLY_RESOURCES)

    return sorted(actual)


def apply_foundation(confirm: bool = False) -> None:
    """Aplica somente o plano revisado e autorizado da primeira Foundation."""
    if not confirm:
        raise RuntimeError(
            "Apply bloqueado. Utilize --confirm-foundation."
        )

    plan_path = TF_DIR / "foundation.tfplan"
    if not plan_path.is_file():
        raise RuntimeError(
            "Plano foundation.tfplan ausente. Execute python lab.py plan."
        )

    merge_env_file(ENV_FILE, os.environ)
    execution_env = dict(os.environ)
    execution_env["TF_LOG"] = "OFF"
    execution_env["TF_INPUT"] = "0"
    secrets = secret_values(execution_env)

    # O JSON do plano pode conter atributos sensiveis.
    # Ele e processado em memoria e nunca exibido no terminal.
    try:
        plan_json = run_command(
            ["terraform", "show", "-json", str(plan_path)],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secrets,
        )
        plan_data = json.loads(plan_json)
    except (RuntimeError, json.JSONDecodeError):
        raise RuntimeError(
            "Nao foi possivel inspecionar o plano salvo. "
            "Nenhuma aplicacao foi iniciada."
        ) from None

    addresses = validate_foundation_plan(plan_data)

    print("========== FOUNDATION APPLY REVIEW ==========")
    print(f"RESOURCES_TO_CREATE={len(addresses)}")
    for address in addresses:
        print(f"CREATE {address}")

    print("DESTRUCTIONS=0")
    print("UPDATES=0")
    approval = input(
        "Digite APPLY FOUNDATION para provisionar os recursos: "
    )

    if approval != "APPLY FOUNDATION":
        print("FOUNDATION_APPLY_CANCELLED=True")
        return

    try:
        # Aplicar um saved plan nao requer -auto-approve:
        # o proprio plano revisado e a aprovacao da operacao.
        # A saida nao e impressa para evitar exposicao de credenciais.
        run_command(
            ["terraform", "apply", "-no-color", str(plan_path)],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secrets,
        )
    except RuntimeError as error:
        # run_command ja redige os secrets conhecidos do ambiente.
        # Preservamos o diagnostico para permitir corrigir a causa real.
        diagnostic = str(error)
        raise RuntimeError(
            "Terraform apply falhou. Diagnostico com secrets redigidos:\\n"
            + diagnostic
        ) from None

    print(
        f"FOUNDATION_APPLY_OK=True; RESOURCES={len(addresses)}"
    )


def teardown() -> None:
    """Bloqueia teardown ate existir um fluxo remoto revisado e allow-listed."""
    has_resources = any(
        re.search(r'^\s*resource\s+"', path.read_text(encoding="utf-8"), re.MULTILINE)
        for path in TF_DIR.glob("*.tf")
    )
    if has_resources:
        raise RuntimeError("Teardown remoto sera habilitado com plano e allow-list no marco de provisionamento.")
    print("TEARDOWN_OK; nenhum recurso declarado neste marco.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Laboratorio de pagamentos em tempo real.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="prepara e valida o bootstrap local")
    commands.add_parser("plan", help="gera um plano Terraform revisavel, sem apply")
    apply_parser = commands.add_parser(
        "apply", help="aplica a Foundation com allowlist e confirmacao explicita"
    )
    apply_parser.add_argument(
        "--confirm-foundation",
        action="store_true",
        help="autoriza iniciar a revisao interativa da Foundation",
    )
    commands.add_parser("teardown", help="encerra recursos gerenciados pelo Terraform")
    commands.add_parser("check-cli", help="valida localmente os comandos Confluent CLI")
    commands.add_parser("test", help="executa os testes sem credenciais")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            setup()
        elif args.command == "plan":
            plan()
        elif args.command == "apply":
            apply_foundation(confirm=args.confirm_foundation)
        elif args.command == "teardown":
            teardown()
        elif args.command == "check-cli":
            check_cli_help()
            print(f"CONFLUENT_CLI_HELP_OK={len(CLI_HELP_COMMANDS)}")
        elif args.command == "test":
            import unittest
            result = unittest.TextTestRunner(verbosity=2).run(
                unittest.defaultTestLoader.discover(str(ROOT / "tests"))
            )
            return 0 if result.wasSuccessful() else 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
