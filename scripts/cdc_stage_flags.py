"""Isola etapas Terraform sem destruir recursos permanentes por flags divergentes.

Consulta somente enderecos do State. Nao imprime o State nem credenciais.
"""
import subprocess
from pathlib import Path

TF_DIR = Path(__file__).resolve().parents[1] / "infra" / "terraform"
CONNECTOR = "confluent_connector.payments_cdc[0]"
SUBJECT = "confluent_subject_config.transactions_value[0]"


def managed_addresses(env):
    result = subprocess.run(
        ["terraform", "state", "list"], cwd=TF_DIR, env=env,
        capture_output=True, text=True, check=False, timeout=45,
    )
    if result.returncode:
        raise RuntimeError("TERRAFORM_STATE_UNAVAILABLE")
    return set(result.stdout.splitlines())


def configure_flags(env, *, connector="auto", subject="auto", addresses=None):
    """Produz flags explicitas. Nunca presume ausencia quando State falha.

    connector/subject: auto = conforme State, on = true, off = false.
    ACLs ficam ativas ao longo das etapas de CDC.
    """
    if addresses is None:
        addresses = managed_addresses(env)
    for value in (connector, subject):
        if value not in ("auto", "on", "off"):
            raise ValueError("INVALID_STAGE_FLAG")
    def enabled(mode, address):
        return address in addresses if mode == "auto" else mode == "on"
    env.update({
        "TF_LOG": "OFF",
        "TF_INPUT": "0",
        "TF_VAR_enable_cdc_connector": str(enabled(connector, CONNECTOR)).lower(),
        "TF_VAR_enable_cdc_acls": "true",
        "TF_VAR_enable_kafka_acls": "true",
        "TF_VAR_enable_subject_compatibility": str(enabled(subject, SUBJECT)).lower(),
    })
    return addresses


def changes_in_plan(plan):
    return [
        (item.get("address"), item.get("change", {}).get("actions"))
        for item in plan.get("resource_changes", [])
        if item.get("change", {}).get("actions") not in (["no-op"], ["read"])
    ]
