"""Verifica o Compute Pool registrado no Terraform State.

Nao altera a infraestrutura e nao imprime credenciais.
Antes do apply, informa que o recurso ainda nao foi criado.
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"


def main():
    print("========== ETAPA 7 — VERIFY COMPUTE POOL ==========")

    result = subprocess.run(
        ["terraform", "state", "pull"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError("STATE_UNAVAILABLE")

    state = json.loads(result.stdout)

    def attributes(resource_type, name):
        return [
            instance.get("attributes") or {}
            for resource in state.get("resources", [])
            if resource.get("mode") == "managed"
            and resource.get("type") == resource_type
            and resource.get("name") == name
            for instance in resource.get("instances", [])
        ]

    environments = attributes(
        "confluent_environment", "challenge"
    )
    pools = attributes(
        "confluent_flink_compute_pool", "payment_fraud"
    )

    if len(environments) != 1:
        raise RuntimeError("FOUNDATION_ENVIRONMENT_NOT_FOUND")

    if not pools:
        print("COMPUTE_POOL_IN_STATE=False")
        print("REMOTE_CHANGES=False")
        print("SECRETS_PRINTED=False")
        print("VERIFY_GATE=NOT_PROVISIONED")
        return

    if len(pools) != 1:
        raise RuntimeError("UNEXPECTED_POOL_COUNT")

    pool = pools[0]
    environment = pool.get("environment") or []

    environment_id = (
        environment[0].get("id")
        if isinstance(environment, list)
        and environment
        and isinstance(environment[0], dict)
        else None
    )

    checks = {
        "POOL_ID_PRESENT": bool(pool.get("id")),
        "DISPLAY_NAME": pool.get("display_name") == "payment-fraud-v2",
        "CLOUD_AWS": pool.get("cloud") == "AWS",
        "REGION_US_EAST_1": pool.get("region") == "us-east-1",
        "MAX_CFU_10": pool.get("max_cfu") == 10,
        "DEFAULT_POOL_FALSE": pool.get("default_pool") is False,
        "ENVIRONMENT_MATCH": environment_id == environments[0].get("id"),
    }

    for name, valid in checks.items():
        print(f"{name}={valid}")

    status = pool.get("status") or []
    if isinstance(status, list):
        status = status[0] if status else {}
    if not isinstance(status, dict):
        status = {}

    print("STATUS_AVAILABLE=", bool(status.get("phase")))
    print("POOL_STATUS=", status.get("phase") or "UNKNOWN")
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print(
        "VERIFY_GATE=",
        "PASS" if all(checks.values()) else "BLOCKED",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("VERIFY_GATE=BLOCKED")
        raise SystemExit(1)
