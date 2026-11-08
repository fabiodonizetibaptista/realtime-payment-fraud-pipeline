"""Resolve nomes Flink sem expor o conteúdo sensível do Terraform State."""

import json
import re
from pathlib import Path

from scripts.flink_runtime import (
    FlinkRuntimeError,
    run_command,
)

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"

# Identificadores históricos encontrados nos SQLs das etapas 8 e 9.
OLD_CATALOG = "desafio-final"
OLD_DATABASE = "desafio-basic"


def terraform_resource_name(state, resource_type, expected_id):
    """Obtém o nome do recurso identificado pelo ID, sem imprimir o State."""
    matches = []

    for resource in state.get("resources", []):
        if resource.get("type") != resource_type:
            continue

        for instance in resource.get("instances", []):
            attrs = instance.get("attributes") or {}

            if attrs.get("id") != expected_id:
                continue

            name = attrs.get("display_name") or attrs.get("name")

            if isinstance(name, str) and name.strip():
                matches.append(name.strip())

    if len(matches) != 1:
        raise FlinkRuntimeError(
            f"FLINK_RESOURCE_NAME_UNRESOLVED_{resource_type.upper()}"
        )

    return matches[0]


def resolve_names(config, command_runner=run_command):
    """Lê apenas os nomes necessários do State.

    A resposta completa do Terraform nunca é registrada em stdout,
    stderr ou mensagens de erro.
    """
    result = command_runner(
        ["terraform", "state", "pull"],
        timeout=30,
        cwd=TF_DIR,
    )

    if result is None or result.returncode != 0:
        raise FlinkRuntimeError("FLINK_NAMES_STATE_UNAVAILABLE")

    try:
        state = json.loads(result.stdout)
    except (TypeError, ValueError):
        raise FlinkRuntimeError("FLINK_NAMES_STATE_INVALID") from None

    if not isinstance(state, dict):
        raise FlinkRuntimeError("FLINK_NAMES_STATE_INVALID")

    catalog = terraform_resource_name(
        state,
        "confluent_environment",
        config.environment_id,
    )

    database = terraform_resource_name(
        state,
        "confluent_kafka_cluster",
        config.kafka_cluster_id,
    )

    return catalog, database


def render_sql(sql, catalog_name, database_name):
    """Substitui somente o prefixo qualificado conhecido dos SQLs.

    Não usa interpolação genérica: dados recebidos do Terraform só
    podem ocupar posições de identificadores SQL previamente definidas.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise FlinkRuntimeError("FLINK_SQL_EMPTY")

    identifiers = (catalog_name, database_name)

    if any(
        not isinstance(value, str)
        or not value.strip()
        or "`" in value
        or any(ord(char) < 32 for char in value)
        for value in identifiers
    ):
        raise FlinkRuntimeError("FLINK_SQL_IDENTIFIER_INVALID")

    original = f"`{OLD_CATALOG}`.`{OLD_DATABASE}`"
    replacement = f"`{catalog_name}`.`{database_name}`"

    if original not in sql:
        raise FlinkRuntimeError(
            "FLINK_SQL_EXPECTED_QUALIFIED_PREFIX_MISSING"
        )

    rendered = sql.replace(original, replacement)

    # Não permitir SQL misturando referências do ambiente antigo com
    # referências ao ambiente atual.
    if original != replacement and original in rendered:
        raise FlinkRuntimeError("FLINK_SQL_MIXED_ENVIRONMENTS")

    return rendered


def render_for_runtime(sql, runtime):
    """Mantém os dublês de testes sem config; exige nomes no runtime real."""
    if not hasattr(runtime, "config"):
        return sql

    catalog = getattr(runtime.config, "catalog_name", None)
    database = getattr(runtime.config, "database_name", None)

    if not catalog or not database:
        raise FlinkRuntimeError("FLINK_SQL_NAMES_NOT_INITIALIZED")

    return render_sql(sql, catalog, database)
