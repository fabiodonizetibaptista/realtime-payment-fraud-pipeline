"""Confere se a conta esta limpa antes de criar recursos (J0, somente leitura).

Restos de uma tentativa anterior que ficaram na nuvem mas fora do Terraform
State fazem o proximo apply falhar por nome duplicado (service accounts sao
unicas na organizacao Confluent; o nome do servico e unico no projeto Aiven).
Este script procura, pelos nomes que o Terraform vai criar:

- environment Confluent (TF_VAR_confluent_environment_name, padrao desafio-final);
- service accounts do projeto;
- servico PostgreSQL na Aiven (TF_VAR_aiven_pg_service_name, padrao payments-postgres).

Imprime apenas nomes e IDs (nao sao segredos) e como remover cada conflito.
Se o State local ja tiver recursos, a execucao esta sendo retomada: o script
apenas informa e nao bloqueia.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from safety import load_env_file  # noqa: E402
from scripts.check_cloud_credentials import aiven_request, confluent_request  # noqa: E402

TF_DIR = ROOT / "infra" / "terraform"
SERVICE_ACCOUNTS = (
    "desafio-iac-admin", "desafio-producer", "desafio-consumer", "desafio-cdc",
    "desafio-schema-registry", "payment-fraud-flink-v2", "desafio-metrics",
)
CONFLUENT_API = "https://api.confluent.cloud"
AIVEN_SERVICE_URL = "https://api.aiven.io/v1/project/{project}/service/{service}"


def get_json(request, opener=urllib.request.urlopen):
    """(status, corpo JSON ou None). Nunca propaga texto da resposta."""
    try:
        with opener(request, timeout=30) as reply:
            return reply.status, json.loads(reply.read().decode() or "null")
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, ValueError):
        return 0, None


def confluent_list(path, key, secret, opener=urllib.request.urlopen):
    request = confluent_request(key, secret)
    request.full_url = f"{CONFLUENT_API}{path}?page_size=100"
    status, body = get_json(request, opener)
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"CONFLUENT_LIST_FAILED HTTP={status}")
    return body.get("data") or []


def find_conflicts(environment, opener=urllib.request.urlopen) -> list[tuple[str, str, str]]:
    key = environment.get("CONFLUENT_CLOUD_API_KEY")
    secret = environment.get("CONFLUENT_CLOUD_API_SECRET")
    env_name = environment.get("TF_VAR_confluent_environment_name") or "desafio-final"
    conflicts = []
    for item in confluent_list("/org/v2/environments", key, secret, opener):
        if item.get("display_name") == env_name:
            conflicts.append(("environment", env_name, str(item.get("id"))))
    for item in confluent_list("/iam/v2/service-accounts", key, secret, opener):
        if item.get("display_name") in SERVICE_ACCOUNTS:
            conflicts.append(("service_account", item["display_name"], str(item.get("id"))))

    project = environment.get("TF_VAR_aiven_project")
    service = environment.get("TF_VAR_aiven_pg_service_name") or "payments-postgres"
    request = aiven_request(environment.get("AIVEN_TOKEN"), project)
    request.full_url = AIVEN_SERVICE_URL.format(
        project=urllib.parse.quote(project or "", safe=""),
        service=urllib.parse.quote(service, safe=""),
    )
    status, _ = get_json(request, opener)
    if status == 200:
        conflicts.append(("aiven_service", service, project or ""))
    elif status != 404:
        raise RuntimeError(f"AIVEN_SERVICE_CHECK_FAILED HTTP={status}")
    return conflicts


NEXT_ACTION = {
    "environment": "confluent environment delete {id} --force   (apaga cluster, conectores e pool dentro dele)",
    "service_account": "confluent iam service-account delete {id} --force",
    "aiven_service": "console da Aiven -> projeto {id} -> servico {name} -> Delete service",
}


def state_addresses():
    result = subprocess.run(["terraform", "state", "list"], cwd=TF_DIR,
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []  # sem State inicializado = execucao nova
    return [line for line in result.stdout.splitlines() if line and not line.startswith("data.")]


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    if state_addresses():
        print("STATE_NOT_EMPTY=True; execucao sendo retomada - conta limpa nao se aplica")
        print("CLEAN_SLATE_GATE=SKIPPED")
        return 0
    dotenv = load_env_file(ROOT / ".env") if (ROOT / ".env").is_file() else {}
    environment = {**dotenv, **{k: v for k, v in os.environ.items() if v}}
    conflicts = find_conflicts(environment)
    for kind, name, ident in conflicts:
        print(f"CONFLICT {kind} {name} {ident}")
        print("  NEXT_ACTION=" + NEXT_ACTION[kind].format(id=ident, name=name))
    print(f"CONFLICT_COUNT={len(conflicts)}")
    print("CLEAN_SLATE_GATE=" + ("PASS" if not conflicts else "BLOCKED"))
    return 0 if not conflicts else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"CLEAN_SLATE_ERROR={error}")
        print("CLEAN_SLATE_GATE=BLOCKED")
        raise SystemExit(1)
