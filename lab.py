"""Comandos locais do laboratorio de pagamentos."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Sequence

from plan_review import review_plan

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
    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
    secrets = secret_values(execution_env)
    _check_versions()
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
    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
    execution_env["TF_LOG"] = "OFF"
    secrets = secret_values(execution_env)
    # Bootstrap em duas fases: o primeiro plano deve conter apenas os 14
    # recursos da Foundation. Um plan geral incluiria PostgreSQL/Flink/ACLs
    # que exigem credenciais exportadas somente depois da Foundation.
    # -target e usado deliberadamente apenas neste bootstrap; a segunda
    # fase usa plan-pipeline sem -target para reconciliar o modulo completo.
    targets = [f"-target={address}" for address in sorted(FOUNDATION_APPLY_RESOURCES)]
    command = ["terraform", "plan", "-no-color", "-input=false", *targets,
               "-out=foundation.tfplan"]
    run_command(command, cwd=TF_DIR, env=execution_env, secrets=secrets)
    # Nao imprimir o output bruto do provider (pode conter atributos sensiveis).
    print(f"FOUNDATION_TARGETS={len(targets)}")
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
            "Plano Foundation divergente. Nenhum apply iniciado. "
            f"AUSENTES={missing}; NAO_AUTORIZADOS={unexpected}. "
            "Revise as divergencias e o Terraform State; depois descarte o "
            "foundation.tfplan antigo de modo controlado e execute "
            "python lab.py plan novamente. Nao execute terraform apply "
            "diretamente nem amplie a allowlist."
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

    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
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
    finally:
        # Plano submetido ao apply nunca e reutilizavel (consumido ou stale),
        # contem dados sensiveis e bloquearia a proxima execucao.
        plan_path.unlink(missing_ok=True)

    print(
        f"FOUNDATION_APPLY_OK=True; RESOURCES={len(addresses)}"
    )



def plan_pipeline() -> None:
    """Gera plano do pipeline completo sem autorizar provisionamento.

    Mantem um arquivo independente do plano historico da Foundation.
    O plano binario pode conter segredos, portanto nunca deve ser
    versionado, exibido ou copiado para logs.
    """
    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
    execution_env["TF_LOG"] = "OFF"
    execution_env["TF_INPUT"] = "0"

    plan_path = TF_DIR / "pipeline.tfplan"

    # Um plano antigo nao pode ser reutilizado silenciosamente.
    # A geracao de um novo plano exige revisao posterior.
    if plan_path.exists():
        raise RuntimeError(
            "PIPELINE_PLAN_BLOCKED=EXISTING_PLAN; "
            "revise e remova o plano antigo antes de gerar outro."
        )

    try:
        run_command(
            [
                "terraform",
                "plan",
                "-no-color",
                "-input=false",
                "-out=pipeline.tfplan",
            ],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secret_values(execution_env),
        )
    except (RuntimeError, OSError):
        # O erro original do provider pode incluir valores sensiveis.
        # O diagnostico detalhado deve ocorrer por canal seguro.
        raise RuntimeError(
            "PIPELINE_PLAN_FAILED; nenhuma aplicacao foi iniciada."
        ) from None

    print("PIPELINE_PLAN_CREATED=True")
    print("PIPELINE_PLAN_FILE=infra/terraform/pipeline.tfplan")
    print("APPLY_AUTHORIZED=False")


def review_saved_plan(pipeline: bool = False) -> dict:
    """Inspeciona um plano salvo sem executar apply ou consultar a nuvem."""

    plan_path = TF_DIR / "pipeline.tfplan" if pipeline else TF_DIR / "foundation.tfplan"

    if not plan_path.is_file():
        raise RuntimeError("PLAN_REVIEW_BLOCKED=PLAN_FILE_NOT_FOUND")

    # O plano pode conter credenciais e atributos sensiveis.
    # Toda a leitura ocorre em memoria; nunca imprimir o JSON.
    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
    execution_env["TF_LOG"] = "OFF"
    execution_env["TF_INPUT"] = "0"

    try:
        raw = run_command(
            ["terraform", "show", "-json", str(plan_path)],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secret_values(execution_env),
        )
        data = json.loads(raw)
    except (RuntimeError, ValueError, OSError):
        # Nao propagar stderr ou payload do Terraform:
        # podem conter informacoes sensiveis.
        raise RuntimeError("PLAN_REVIEW_BLOCKED=PLAN_READ_FAILED") from None

    result = review_plan(data)

    print("=== TERRAFORM PLAN REVIEW ===")
    print(f"CREATE_COUNT={result['create']}")
    print(f"UPDATE_COUNT={result['update']}")
    print("DESTROY_COUNT=0")
    print("REPLACEMENT_COUNT=0")
    print("PLAN_REVIEW=PASSED")
    print("APPLY_AUTHORIZED=False")

    return result



def apply_pipeline(confirm: bool = False, allow_cdc: bool = False) -> None:
    """Aplica somente um plano salvo, revisado e aprovado pelo operador.

    O conector CDC exige autorizacao adicional devido ao custo por hora.
    Nenhum atributo sensivel do plano deve ser exibido.
    """
    if not confirm:
        raise RuntimeError("PIPELINE_APPLY_BLOCKED=CONFIRMATION_REQUIRED")

    plan_path = TF_DIR / "pipeline.tfplan"
    if not plan_path.is_file():
        raise RuntimeError("PIPELINE_APPLY_BLOCKED=PLAN_NOT_FOUND")

    execution_env = dict(os.environ)
    merge_env_file(ENV_FILE, execution_env)
    execution_env["TF_LOG"] = "OFF"
    execution_env["TF_INPUT"] = "0"

    try:
        raw = run_command(
            ["terraform", "show", "-json", str(plan_path)],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secret_values(execution_env),
        )
        data = json.loads(raw)
    except (RuntimeError, ValueError, OSError):
        raise RuntimeError(
            "PIPELINE_APPLY_BLOCKED=PLAN_READ_FAILED"
        ) from None

    # Reutiliza a politica extensivel. Destruicoes e substituicoes
    # sao rejeitadas independentemente da confirmacao do operador.
    try:
        review = review_plan(data)
    except ValueError:
        raise RuntimeError(
            "PIPELINE_APPLY_BLOCKED=UNSAFE_PLAN"
        ) from None

    resources = review["resources"]

    cdc_changes = [
        item for item in resources
        if item["address"] == "confluent_connector.payments_cdc"
        or item["address"].startswith(
            "confluent_connector.payments_cdc["
        )
    ]

    if cdc_changes and not allow_cdc:
        raise RuntimeError(
            "PIPELINE_APPLY_BLOCKED=CDC_REQUIRES_EXPLICIT_AUTHORIZATION"
        )

    if not resources:
        print("PIPELINE_APPLY_SKIPPED=NO_CHANGES")
        return

    print("=== PIPELINE APPLY REVIEW ===")
    print(f"CREATE_COUNT={review['create']}")
    print(f"UPDATE_COUNT={review['update']}")
    print("DESTROY_COUNT=0")
    print("REPLACEMENT_COUNT=0")
    print(f"CDC_CHANGES={len(cdc_changes)}")
    print("WARNING=CLOUD_RESOURCES_MAY_GENERATE_COSTS")

    # Exibir somente endereco e acao, nunca valores before/after.
    for item in resources:
        print(f"{item['action'].upper()} {item['address']}")

    approval = input("Digite APPLY PIPELINE para autorizar: ")

    if approval != "APPLY PIPELINE":
        print("PIPELINE_APPLY_CANCELLED=True")
        return

    # O Terraform verifica se o plano salvo permanece aplicavel
    # ao state. Nao regeneramos o plano apos a aprovacao.
    try:
        run_command(
            ["terraform", "apply", "-no-color", str(plan_path)],
            cwd=TF_DIR,
            env=execution_env,
            secrets=secret_values(execution_env),
        )
    except (RuntimeError, OSError):
        raise RuntimeError(
            "PIPELINE_APPLY_FAILED; verificar o estado Terraform "
            "por procedimento seguro antes de tentar novamente."
        ) from None
    finally:
        plan_path.unlink(missing_ok=True)

    print("PIPELINE_APPLY_OK=True")


FLINK_POOL_ADDRESS = "confluent_flink_compute_pool.payment_fraud"


def teardown_flink_runtime(actions):
    """Runtime Flink quando o destroy inclui o compute pool; senao None."""
    if not any(item.get("address") == FLINK_POOL_ADDRESS for item in actions):
        return None
    from scripts.flink_runtime import FlinkRuntime

    return FlinkRuntime.from_terraform_state()


def teardown(confirm: bool = False) -> None:
    """Destroi somente os recursos do Terraform State atual.

    Nunca reutiliza um plano antigo. A aprovacao humana ocorre
    depois da revisao das acoes, sem imprimir atributos sensiveis.
    """
    if not confirm:
        raise RuntimeError("TEARDOWN_BLOCKED=CONFIRMATION_REQUIRED")

    env = dict(os.environ)
    merge_env_file(ENV_FILE, env)
    env["TF_LOG"] = "OFF"
    env["TF_INPUT"] = "0"

    plan_path = TF_DIR / "teardown.tfplan"

    if plan_path.exists():
        raise RuntimeError("TEARDOWN_BLOCKED=EXISTING_PLAN")

    try:
        # Plano de destruicao, sem realizar nenhuma alteracao remota.
        run_command(
            [
                "terraform", "plan", "-destroy",
                "-no-color", "-input=false",
                "-out=teardown.tfplan",
            ],
            cwd=TF_DIR,
            env=env,
            secrets=secret_values(env),
        )

        raw = run_command(
            ["terraform", "show", "-json", str(plan_path)],
            cwd=TF_DIR,
            env=env,
            secrets=secret_values(env),
        )

        data = json.loads(raw)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("TEARDOWN_PLAN_FAILED") from None

    actions = []

    for resource in data.get("resource_changes", []):
        change = resource.get("change") or {}
        action = change.get("actions") or []

        if action == ["no-op"]:
            continue

        if action != ["delete"]:
            raise RuntimeError("TEARDOWN_BLOCKED=UNSAFE_PLAN")

        # Nao exibimos endereco nem atributos para evitar
        # exposicao acidental de identificadores sensiveis.
        actions.append(resource)

    if not actions:
        print("TEARDOWN_SKIPPED=NO_RESOURCES")
        return

    # Statements Flink nao sao recursos Terraform: sao listados antes da
    # aprovacao e apagados depois dela, antes do destroy do pool/environment.
    try:
        flink = teardown_flink_runtime(actions)
        statements = len(flink.list_statements()) if flink else 0
    except Exception:
        plan_path.unlink(missing_ok=True)
        raise RuntimeError("TEARDOWN_BLOCKED=FLINK_STATEMENTS_UNVERIFIED") from None

    print("=== TERRAFORM TEARDOWN REVIEW ===")
    print(f"DESTROY_COUNT={len(actions)}")
    print(f"FLINK_STATEMENTS_TO_DELETE={statements}")
    print("WARNING=ALL_RESOURCES_IN_CURRENT_TERRAFORM_STATE")
    print("WARNING=DESTRUCTION_MAY_BE_IRREVERSIBLE")

    approval = input("Digite DESTROY PIPELINE para confirmar: ")

    if approval != "DESTROY PIPELINE":
        plan_path.unlink(missing_ok=True)
        print("TEARDOWN_CANCELLED=True")
        return

    if flink is not None:
        try:
            deleted = flink.delete_all_statements()
        except Exception:
            plan_path.unlink(missing_ok=True)
            raise RuntimeError(
                "TEARDOWN_BLOCKED=FLINK_STATEMENT_DELETE_FAILED; "
                "nenhum recurso Terraform foi destruido"
            ) from None
        print(f"FLINK_STATEMENTS_DELETED={deleted}")

    try:
        # Aplicar exclusivamente o plano previamente revisado.
        run_command(
            ["terraform", "apply", "-no-color", str(plan_path)],
            cwd=TF_DIR,
            env=env,
            secrets=secret_values(env),
        )
    except (RuntimeError, OSError):
        raise RuntimeError(
            "TEARDOWN_FAILED=CHECK_TERRAFORM_STATE; nao repita: "
            "python scripts/reconcile_state.py plan"
        ) from None
    finally:
        plan_path.unlink(missing_ok=True)

    print("TEARDOWN_COMPLETED=True")




def setup_flink(apply: bool = False) -> None:
    """Prepara as tabelas Flink após o provisionamento Terraform.

    A consulta padrão é somente leitura. A aplicação de DDL exige
    autorização interativa e permanece separada do Terraform Apply.
    """
    from dataclasses import replace
    from scripts.flink_runtime import FlinkRuntime
    from scripts.flink_portability import resolve_names
    from scripts.flink_setup import preflight_tables, prepare_tables

    merge_env_file(ENV_FILE, os.environ)

    # Os IDs vêm do Terraform State; os nomes SQL também são
    # resolvidos pelo State, evitando referências ao laboratório antigo.
    runtime = FlinkRuntime.from_terraform_state()
    catalog, database = resolve_names(runtime.config)
    runtime.config = replace(
        runtime.config,
        catalog_name=catalog,
        database_name=database,
    )

    plan = preflight_tables(runtime)
    print("=== FLINK PREFLIGHT ===")
    for item in plan:
        print(f"{item['step'].name}: {item['state']}")

    print("FLINK_PREFLIGHT=PASSED")

    if not apply:
        print("REMOTE_DDL_EXECUTED=False")
        return

    approval = input("Digite APPLY FLINK para autorizar os DDLs: ")
    if approval != "APPLY FLINK":
        print("FLINK_APPLY_CANCELLED=True")
        return

    results = prepare_tables(runtime)

    for item in results:
        print(f"{item['step']}: {item['result']}")

    print("FLINK_SETUP_COMPLETED=True")


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
    review_parser = commands.add_parser(
        "review-plan",
        help="revisa um plano Terraform salvo sem executar apply"
    )
    review_parser.add_argument(
        "--pipeline",
        action="store_true",
        help="revisa pipeline.tfplan em vez de foundation.tfplan",
    )
    commands.add_parser(
        "plan-pipeline",
        help="gera plano completo do pipeline sem executar apply"
    )
    pipeline_apply_parser = commands.add_parser(
        "apply-pipeline",
        help="aplica um plano completo salvo, com revisao e aprovacao",
    )
    pipeline_apply_parser.add_argument(
        "--confirm-pipeline",
        action="store_true",
        help="habilita a revisao interativa do apply",
    )
    pipeline_apply_parser.add_argument(
        "--allow-cdc",
        action="store_true",
        help="autoriza incluir o conector CDC, sujeito a custos",
    )
    flink_parser = commands.add_parser(
        "flink-setup",
        help="verifica ou aplica os DDLs Flink após o Terraform",
    )
    flink_parser.add_argument(
        "--apply",
        action="store_true",
        help="habilita a confirmação interativa dos DDLs",
    )
    teardown_parser = commands.add_parser(
        "teardown",
        help="revisa e executa destruicao controlada do pipeline",
    )
    teardown_parser.add_argument(
        "--confirm-destroy",
        action="store_true",
        help="habilita o plano de destruicao e a confirmacao interativa",
    )
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
        elif args.command == "plan-pipeline":
            plan_pipeline()
        elif args.command == "review-plan":
            review_saved_plan(pipeline=args.pipeline)
        elif args.command == "apply-pipeline":
            apply_pipeline(
                confirm=args.confirm_pipeline,
                allow_cdc=args.allow_cdc,
            )
        elif args.command == "flink-setup":
            setup_flink(apply=args.apply)
        elif args.command == "teardown":
            teardown(confirm=args.confirm_destroy)
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
