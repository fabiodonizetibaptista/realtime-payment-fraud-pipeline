"""Gate de prontidao da Foundation V2.

Validacoes incrementais e somente leitura.
Nunca exibe API Keys, API Secrets ou o JSON bruto do Terraform.
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"

sys.path.insert(0, str(ROOT))
from safety import load_env_file


def fail(message):
    print(f"GATE_STATUS=BLOCKED; REASON={message}")
    return 1


def get_json(url, key, secret):
    token = base64.b64encode(
        f"{key}:{secret}".encode("utf-8")
    ).decode("ascii")

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)



def check_identities_and_acls(env, outputs, kafka_id):
    """Confere as identidades e as ACLs no State e no Kafka real."""
    expected_accounts = {
        "desafio-iac-admin",
        "desafio-producer",
        "desafio-consumer",
        "desafio-schema-registry",
        "desafio-cdc",
    }

    expected_acls = {
        ("TOPIC", "payments", "PREFIXED", "WRITE"),
        ("TOPIC", "payments", "PREFIXED", "CREATE"),
        ("CLUSTER", "kafka-cluster", "LITERAL", "DESCRIBE"),
        ("CLUSTER", "kafka-cluster", "LITERAL", "DESCRIBE_CONFIGS"),
        ("TOPIC", "__debezium-heartbeat-", "PREFIXED", "CREATE"),
        ("TOPIC", "__debezium-heartbeat-", "PREFIXED", "DESCRIBE"),
        ("TOPIC", "__debezium-heartbeat-", "PREFIXED", "WRITE"),
        ("TOPIC", "desafio-", "PREFIXED", "WRITE"),
        ("TOPIC", "desafio-", "PREFIXED", "READ"),
        ("GROUP", "desafio-", "PREFIXED", "READ"),
    }

    # State consultado em memoria, sem imprimir dados sensiveis.
    state = subprocess.run(
        ["terraform", "show", "-json"],
        cwd=TF_DIR,
        env={**env, "TF_LOG": "OFF"},
        capture_output=True,
        text=True,
        check=False,
    )
    if state.returncode:
        return fail("TERRAFORM_STATE_UNAVAILABLE")

    try:
        resources = json.loads(state.stdout)["values"]["root_module"]["resources"]
        state_addresses = {
            r["address"] for r in resources
        }
        state_acls = [
            r for r in resources
            if r.get("type") == "confluent_kafka_acl"
            and r.get("mode") == "managed"
        ]
    except (KeyError, TypeError, ValueError):
        return fail("TERRAFORM_STATE_INVALID")

    account_resources = {
        "confluent_service_account.iac_admin",
        "confluent_service_account.producer",
        "confluent_service_account.consumer",
        "confluent_service_account.schema_registry",
        "confluent_service_account.cdc",
    }

    if not account_resources.issubset(state_addresses):
        return fail("SERVICE_ACCOUNTS_MISSING_IN_STATE")

    if len(state_acls) != 10:
        return fail("ACL_COUNT_MISMATCH_IN_STATE")

    state_acl_tuples = {
        (
            r["values"]["resource_type"],
            r["values"]["resource_name"],
            r["values"]["pattern_type"],
            r["values"]["operation"],
        )
        for r in state_acls
    }

    if state_acl_tuples != expected_acls:
        return fail("ACL_CONFIGURATION_MISMATCH_IN_STATE")

    cloud_key = env["CONFLUENT_CLOUD_API_KEY"]
    cloud_secret = env["CONFLUENT_CLOUD_API_SECRET"]

    accounts = get_json(
        "https://api.confluent.cloud/iam/v2/service-accounts?page_size=100",
        cloud_key,
        cloud_secret,
    )

    found_accounts = {
        item.get("display_name")
        for item in accounts.get("data", [])
    }

    if not expected_accounts.issubset(found_accounts):
        return fail("SERVICE_ACCOUNTS_MISSING_REMOTELY")

    # Kafka REST API: leitura das ACLs do cluster provisionado.
    endpoint = env["TF_VAR_foundation_kafka_rest_endpoint"].rstrip("/")
    api_key = env["TF_VAR_foundation_kafka_api_key"]
    api_secret = env["TF_VAR_foundation_kafka_api_secret"]

    remote_acls = get_json(
        f"{endpoint}/kafka/v3/clusters/{kafka_id}/acls",
        api_key,
        api_secret,
    )

    remote_tuples = {
        (
            item.get("resource_type"),
            item.get("resource_name"),
            item.get("pattern_type"),
            item.get("operation"),
        )
        for item in remote_acls.get("data", [])
        if item.get("permission") == "ALLOW"
    }

    if not expected_acls.issubset(remote_tuples):
        return fail("ACL_CONFIGURATION_MISSING_REMOTELY")

    print("========== BLOCO 3 — GATE ITEM 2 ==========")
    print("SERVICE_ACCOUNTS_IN_STATE=5")
    print("SERVICE_ACCOUNTS_REMOTE_MATCH=True")
    print("ACLs_IN_STATE=10")
    print("ACLs_REMOTE_MATCH=True")
    print("GATE_ITEM_2=PASS")
    return 0



def check_credentials(env, kafka_id):
    """Testa Kafka e Schema Registry sem exibir tokens ou respostas."""
    kafka_endpoint = env.get(
        "TF_VAR_foundation_kafka_rest_endpoint", ""
    ).rstrip("/")
    kafka_key = env.get("TF_VAR_foundation_kafka_api_key", "")
    kafka_secret = env.get("TF_VAR_foundation_kafka_api_secret", "")

    schema_endpoint = env.get(
        "TF_VAR_foundation_schema_registry_rest_endpoint", ""
    ).rstrip("/")
    schema_key = env.get("TF_VAR_foundation_schema_registry_api_key", "")
    schema_secret = env.get(
        "TF_VAR_foundation_schema_registry_api_secret", ""
    )

    if not all((
        kafka_endpoint, kafka_key, kafka_secret,
        schema_endpoint, schema_key, schema_secret,
    )):
        return fail("DATA_PLANE_CREDENTIALS_MISSING")

    # Ambas as consultas sao GET, sem criar topicos ou schemas.
    kafka_response = get_json(
        f"{kafka_endpoint}/kafka/v3/clusters/{kafka_id}/topics",
        kafka_key,
        kafka_secret,
    )
    if not isinstance(kafka_response.get("data"), list):
        return fail("KAFKA_SMOKE_INVALID_RESPONSE")

    subjects = get_json(
        f"{schema_endpoint}/subjects",
        schema_key,
        schema_secret,
    )
    if not isinstance(subjects, list):
        return fail("SCHEMA_REGISTRY_SMOKE_INVALID_RESPONSE")

    print("========== BLOCO 3 — GATE ITEM 3 ==========")
    print("KAFKA_AUTH_OK=True")
    print("SCHEMA_REGISTRY_AUTH_OK=True")
    print("CREDENTIAL_VALUES_PRINTED=False")
    print("GATE_ITEM_3=PASS")
    return 0



def check_readiness(env):
    """Verifica a sessao e detecta drift sem aplicar alteracoes."""
    required = (
        "CONFLUENT_CLOUD_API_KEY",
        "CONFLUENT_CLOUD_API_SECRET",
        "TF_VAR_foundation_environment_id",
        "TF_VAR_foundation_kafka_id",
        "TF_VAR_foundation_kafka_rest_endpoint",
        "TF_VAR_foundation_kafka_api_key",
        "TF_VAR_foundation_kafka_api_secret",
        "TF_VAR_foundation_schema_registry_id",
        "TF_VAR_foundation_schema_registry_rest_endpoint",
        "TF_VAR_foundation_schema_registry_api_key",
        "TF_VAR_foundation_schema_registry_api_secret",
        "KAFKA_BOOTSTRAP_ENDPOINT",
        "CDC_SERVICE_ACCOUNT_ID",
    )

    missing = [key for key in required if not env.get(key)]

    if missing:
        return fail("SESSION_VARIABLES_MISSING")

    execution_env = dict(env)
    execution_env["TF_LOG"] = "OFF"
    execution_env["TF_INPUT"] = "0"

    # As 10 ACLs ja foram aplicadas nos blocos anteriores.
    # Precisamos manter as duas flags ativas durante o plan
    # para nao interpretar essas ACLs como recursos a destruir.
    execution_env["TF_VAR_enable_cdc_acls"] = "true"
    execution_env["TF_VAR_enable_kafka_acls"] = "true"

    # -detailed-exitcode:
    # 0 = nenhuma mudanca pendente
    # 1 = erro
    # 2 = mudancas detectadas
    #
    # Capturamos a saida em memoria para nao exibir secrets.
    # Nao usamos -out e nao executamos apply.
    result = subprocess.run(
        [
            "terraform", "plan",
            "-detailed-exitcode",
            "-no-color",
            "-input=false",
            "-lock-timeout=30s",
        ],
        cwd=TF_DIR,
        env=execution_env,
        capture_output=True,
        text=True,
        check=False,
    )

    print("========== BLOCO 3 — GATE ITEM 4 ==========")
    print("SESSION_VARIABLES_READY=True")
    print("REQUIRED_VARIABLES=", len(required))

    if result.returncode == 2:
        print("TERRAFORM_NO_PENDING_CHANGES=False")
        return fail("TERRAFORM_DRIFT_OR_CHANGES_DETECTED")

    if result.returncode != 0:
        print("TERRAFORM_PLAN_OK=False")
        return fail("TERRAFORM_PLAN_FAILED")

    print("TERRAFORM_PLAN_OK=True")
    print("TERRAFORM_NO_PENDING_CHANGES=True")
    print("GATE_ITEM_4=PASS")
    print("FOUNDATION_PREFLIGHT=PASS")

    # Evidencia sanitizada, sem credenciais, endpoints ou
    # identificadores de recursos.
    evidence = ROOT / "evidencias" / "window"
    evidence.mkdir(parents=True, exist_ok=True)
    report = evidence / "foundation-preflight.txt"

    report.write_text(
        "BLOCO_3_FOUNDATION_PREFLIGHT=PASS\\n"
        "GATE_ITEM_1=PASS\\n"
        "GATE_ITEM_2=PASS\\n"
        "GATE_ITEM_3=PASS\\n"
        "GATE_ITEM_4=PASS\\n"
        "TERRAFORM_NO_PENDING_CHANGES=True\\n",
        encoding="utf-8",
    )

    print("EVIDENCE_RECORDED=True")
    return 0


def main():
    env = dict(os.environ)

    # Nao substitui valores existentes na sessao.
    for key, value in load_env_file(ROOT / ".env").items():
        if value and not env.get(key):
            env[key] = value

    cloud_key = env.get("CONFLUENT_CLOUD_API_KEY", "")
    cloud_secret = env.get("CONFLUENT_CLOUD_API_SECRET", "")

    if not cloud_key or not cloud_secret:
        return fail("CLOUD_CREDENTIALS_MISSING")

    execution_env = dict(env)
    execution_env["TF_LOG"] = "OFF"

    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TF_DIR,
        env=execution_env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode:
        return fail("TERRAFORM_OUTPUT_UNAVAILABLE")

    try:
        outputs = json.loads(result.stdout)

        environment_id = outputs["environment_id"]["value"]
        kafka_id = outputs["kafka_cluster_id"]["value"]
        bootstrap = outputs["kafka_bootstrap_endpoint"]["value"]

        if not all(
            isinstance(v, str) and v
            for v in (environment_id, kafka_id, bootstrap)
        ):
            return fail("TERRAFORM_OUTPUT_INVALID")

        # Confirma que as variaveis exportadas pertencem
        # aos recursos registrados no Terraform State.
        expected = {
            "TF_VAR_foundation_environment_id": environment_id,
            "TF_VAR_foundation_kafka_id": kafka_id,
            "KAFKA_BOOTSTRAP_ENDPOINT": bootstrap,
        }

        if any(env.get(k) != v for k, v in expected.items()):
            return fail("ENV_OUTPUT_MISMATCH")

        environments = get_json(
            "https://api.confluent.cloud/org/v2/environments?page_size=100",
            cloud_key,
            cloud_secret,
        )

        match = [
            item for item in environments.get("data", [])
            if item.get("id") == environment_id
            and item.get("display_name") == "desafio-final"
        ]

        if len(match) != 1:
            return fail("ENVIRONMENT_MISMATCH")

        clusters = get_json(
            "https://api.confluent.cloud/cmk/v2/clusters"
            f"?environment={environment_id}&page_size=100",
            cloud_key,
            cloud_secret,
        )

        match = [
            item for item in clusters.get("data", [])
            if item.get("id") == kafka_id
            and item.get("spec", {}).get("display_name")
            == "desafio-basic"
            and item.get("spec", {}).get("kafka_bootstrap_endpoint")
            in (None, bootstrap)
        ]

        if len(match) != 1:
            return fail("KAFKA_CLUSTER_MISMATCH")

    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return fail("INVALID_RESPONSE_OR_OUTPUT")
    except urllib.error.HTTPError as error:
        return fail(f"CONFLUENT_HTTP_{error.code}")
    except (urllib.error.URLError, TimeoutError, OSError):
        return fail("CONFLUENT_CONNECTION_FAILED")

    print("========== BLOCO 3 — GATE ITEM 1 ==========")
    print("TERRAFORM_OUTPUTS_VALID=True")
    print("ENVIRONMENT_MATCH=True")
    print("KAFKA_CLUSTER_MATCH=True")
    print("BOOTSTRAP_EXPORTED=True")
    print("GATE_ITEM_1=PASS")

    try:
        identity_result = check_identities_and_acls(
            env, outputs, kafka_id
        )
        if identity_result != 0:
            return identity_result
        credential_result = check_credentials(env, kafka_id)
        if credential_result != 0:
            return credential_result

        return check_readiness(env)
    except urllib.error.HTTPError as error:
        return fail(f"ACL_OR_IDENTITY_HTTP_{error.code}")
    except (urllib.error.URLError, TimeoutError, OSError):
        return fail("ACL_OR_IDENTITY_CONNECTION_FAILED")
    except (KeyError, TypeError, ValueError):
        return fail("ACL_OR_IDENTITY_INVALID_RESPONSE")


if __name__ == "__main__":
    raise SystemExit(main())
