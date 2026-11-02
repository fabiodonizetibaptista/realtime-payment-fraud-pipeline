"""Comandos locais do laboratorio de pagamentos."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Sequence

from safety import merge_env_file, run_command, secret_values

ROOT = Path(__file__).resolve().parent
TF_DIR = ROOT / "infra" / "terraform"
ENV_FILE = ROOT / ".env"
MIN_TERRAFORM_VERSION = (1, 16, 0)
MIN_CONFLUENT_VERSION = (4, 81, 0)

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
    run_command(["terraform", "init", "-backend=false", "-lockfile=readonly"],
                cwd=TF_DIR, env=os.environ, secrets=secrets)
    result = run_command(["terraform", "validate", "-no-color"],
                         cwd=TF_DIR, env=os.environ, secrets=secrets)
    check_cli_help()
    if result.strip():
        print(result.strip())
    print("BOOTSTRAP_LOCAL_OK; nenhum recurso remoto foi consultado ou alterado.")


def teardown() -> None:
    """No Marco 1 ainda nao existem recursos Terraform para destruir."""
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
    commands.add_parser("teardown", help="encerra recursos gerenciados pelo Terraform")
    commands.add_parser("check-cli", help="valida localmente os comandos Confluent CLI")
    commands.add_parser("test", help="executa os testes sem credenciais")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            setup()
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
