"""Registra evidencias do Flink Compute Pool sem modificar a nuvem.

Dados de configuracao: Terraform State.
Dados operacionais: inspecao visual realizada na Confluent Cloud.
Nao registra credenciais, endpoints privados ou conteudo do State.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
OUTPUT = ROOT / "evidencias" / "flink" / "stage7-compute-pool.json"

EXPECTED_NAME = "payment-fraud-v2"
EXPECTED_ID = "lfcp-gq50o2n"


def fail(code):
    print("ERROR_CODE=", code)
    print("STAGE7_EVIDENCE_GATE=BLOCKED")
    raise SystemExit(1)


def get_resource(state, resource_type, name):
    instances = [
        instance.get("attributes") or {}
        for resource in state.get("resources", [])
        if resource.get("mode") == "managed"
        and resource.get("type") == resource_type
        and resource.get("name") == name
        for instance in resource.get("instances", [])
    ]
    return instances[0] if len(instances) == 1 else None


def main():
    print("========== ETAPA 7 — REGISTRO DE EVIDENCIAS ==========")

    # O acesso ao Terraform State e os checks de unicidade
    # continuam protegendo a coleta em qualquer branch.
    if OUTPUT.exists():
        fail("EVIDENCE_ALREADY_EXISTS")

    result = subprocess.run(
        ["terraform", "state", "pull"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        fail("STATE_UNAVAILABLE")

    state = json.loads(result.stdout)

    pool = get_resource(
        state, "confluent_flink_compute_pool", "payment_fraud"
    )
    environment = get_resource(
        state, "confluent_environment", "challenge"
    )

    if not pool or not environment:
        fail("RESOURCE_NOT_FOUND")

    pool_environment = pool.get("environment") or []

    environment_id = (
        pool_environment[0].get("id")
        if isinstance(pool_environment, list)
        and len(pool_environment) == 1
        and isinstance(pool_environment[0], dict)
        else None
    )

    checks = {
        "id": pool.get("id") == EXPECTED_ID,
        "name": pool.get("display_name") == EXPECTED_NAME,
        "cloud": pool.get("cloud") == "AWS",
        "region": pool.get("region") == "us-east-1",
        "environment": environment_id == environment.get("id"),
        "max_cfu": pool.get("max_cfu") == 10,
        "default_pool": pool.get("default_pool") is False,
    }

    if not all(checks.values()):
        fail("RESOURCE_CONFIGURATION_MISMATCH")

    # Running e 0 CFUs foram observados diretamente na interface.
    # Nao sao apresentados como uma nova medicao automatizada.
    evidence = {
        "stage": 7,
        "resource": "confluent_flink_compute_pool.payment_fraud",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "compute_pool": {
            "id": pool["id"],
            "name": pool["display_name"],
            "cloud": pool["cloud"],
            "region": pool["region"],
            "environment_id": environment_id,
            "max_cfu": pool["max_cfu"],
            "default_pool": pool["default_pool"],
            "configuration_source": "Terraform State",
        },
        "provisioning": {
            "status": "Running",
            "source": "Confluent Cloud UI",
            "verification": "Manual browser inspection",
            "terraform_apply": "PASS",
        },
        "capacity_and_cost": {
            "max_cfu_configured": pool["max_cfu"],
            "observed_current_cfu": 0,
            "observed_running_statements": 0,
            "observation_source": "Confluent Cloud UI",
            "measurement_type": "Point-in-time observation",
            "financial_cost_verified": False,
            "financial_cost_estimate_usd": None,
            "note": (
                "Max CFU is a configured capacity ceiling. "
                "Observed 0 CFUs does not establish total billing cost."
            ),
        },
        "sql_workspace": {
            "editor_accessible": True,
            "source": "Confluent Cloud UI inspection",
            "sql_execution_tested": False,
        },
        "gate": "PASS",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Criacao exclusiva: preserva evidencias de execucoes anteriores.
    with OUTPUT.open("x", encoding="utf-8") as file:
        json.dump(evidence, file, indent=2, ensure_ascii=False)
        file.write("\n")

    # Releitura garante integridade do arquivo criado.
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))

    if saved != evidence:
        fail("EVIDENCE_VERIFICATION_FAILED")

    print("COMPUTE_POOL_ID_RECORDED=True")
    print("COMPUTE_POOL_NAME_RECORDED=True")
    print("REGION_RECORDED=True")
    print("PROVISIONING_STATUS=Running")
    print("MAX_CFU_RECORDED=10")
    print("OBSERVED_CURRENT_CFU=0")
    print("FINANCIAL_COST_VERIFIED=False")
    print("SQL_WORKSPACE_ACCESS_RECORDED=True")
    print("EVIDENCE_FILE=evidencias/flink/stage7-compute-pool.json")
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print("STAGE7_EVIDENCE_GATE=PASS")


if __name__ == "__main__":
    main()
