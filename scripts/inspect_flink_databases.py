"""Etapa 8: verifica quais clusters Kafka o Flink consegue enxergar."""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from safety import load_env_file
from inspect_flink_accounts import request, state_resource

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra/terraform"

print("========== ETAPA 8 — SHOW DATABASES ==========")

def fail(code):
    print("ERROR_CODE=", code)
    print("STAGE8_DATABASE_DISCOVERY_GATE=BLOCKED")
    raise SystemExit(1)

def run(cmd, cwd=ROOT):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )

# Os preflights abaixo validam recursos e autorizacao sem
# condicionar a inspecao ao nome da branch Git.
result = run(["terraform", "state", "pull"], TF)
if result.returncode != 0:
    fail("STATE_UNAVAILABLE")

state = json.loads(result.stdout)

sa = state_resource(state, "confluent_service_account", "flink_processor")
key = state_resource(state, "confluent_api_key", "flink_processor")
pool = state_resource(state, "confluent_flink_compute_pool", "payment_fraud")
environment = state_resource(state, "confluent_environment", "challenge")
cluster = state_resource(state, "confluent_kafka_cluster", "basic")

if not all((sa, key, pool, environment, cluster)):
    fail("RESOURCE_MISSING")

env = dict(os.environ)
for name, value in load_env_file(ROOT / ".env").items():
    if value and not env.get(name):
        env[name] = value

cloud_key = (
    env.get("CONFLUENT_CLOUD_API_KEY")
    or env.get("TF_VAR_confluent_cloud_api_key")
    or env.get("TF_VAR_confluent_api_key")
)
cloud_secret = (
    env.get("CONFLUENT_CLOUD_API_SECRET")
    or env.get("TF_VAR_confluent_cloud_api_secret")
    or env.get("TF_VAR_confluent_api_secret")
)

if not cloud_key or not cloud_secret:
    fail("CLOUD_CREDENTIALS_MISSING")

status, body = request(
    "https://api.confluent.cloud/org/v2/organizations",
    cloud_key, cloud_secret
)

items = body.get("data", []) if isinstance(body, dict) else []
if status != 200 or len(items) != 1:
    fail("ORGANIZATION_UNAVAILABLE")

base = (
    "https://flink.us-east-1.aws.confluent.cloud"
    f"/sql/v1/organizations/{items[0]['id']}"
    f"/environments/{environment['id']}/statements"
)

name = "stage8-databases-" + uuid.uuid4().hex[:12]
url = base + "/" + name

payload = {
    "name": name,
    "organization_id": items[0]["id"],
    "environment_id": environment["id"],
    "spec": {
        "statement": "SHOW DATABASES;",
        "principal": sa["id"],
        "compute_pool_id": pool["id"],
        "properties": {
            "sql.current-catalog": environment["display_name"]
        },
        "stopped": False
    }
}

created = False
cleaned = False
success = False

try:
    code, _ = request(
        base, key["id"], key["secret"],
        method="POST", payload=payload
    )

    print("SUBMIT_HTTP_STATUS=", code)

    if code in (200, 201, 202):
        created = True
        phase = "UNKNOWN"
        detail = {}

        for _ in range(15):
            status, detail = request(url, key["id"], key["secret"])
            if status != 200:
                break

            phase = (detail.get("status") or {}).get("phase", "UNKNOWN")

            if phase in ("COMPLETED", "FAILED", "FAILING"):
                break

            time.sleep(2)

        print("STATEMENT_PHASE=", phase)

        if phase == "COMPLETED":
            result_status, result = request(
                url + "/results", key["id"], key["secret"]
            )
            print("RESULTS_HTTP_STATUS=", result_status)

            rows = (
                (result.get("results") or {}).get("data", [])
                if isinstance(result, dict) else []
            )

            if result_status == 200 and isinstance(rows, list):
                # Nunca exibe IDs ou nomes de outros recursos.
                expected_name = cluster["display_name"]
                expected_id = cluster["id"]

                matches = [
                    item for item in rows
                    if isinstance(item, dict)
                    and (
                        expected_name in str(item.get("row", []))
                        or expected_id in str(item.get("row", []))
                    )
                ]

                print("DATABASE_ROWS=", len(rows))
                print("EXPECTED_KAFKA_DATABASE_VISIBLE=", bool(matches))
                success = True

        elif phase in ("FAILED", "FAILING"):
            message = str(
                (detail.get("status") or {}).get("detail", "")
            ).lower()

            print("ERROR_PERMISSION=", any(
                term in message for term in
                ("permission", "not authorized", "access denied")
            ))
            print("ERROR_CATALOG=", "catalog" in message)
            print("ERROR_DATABASE=", "database" in message)
            print("ERROR_DETAIL_PRESENT=", bool(message))

finally:
    if created:
        delete_status, _ = request(
            url, key["id"], key["secret"], method="DELETE"
        )
        print("DELETE_HTTP_STATUS=", delete_status)

        if delete_status in (200, 202, 204, 404):
            for _ in range(10):
                check, _ = request(url, key["id"], key["secret"])
                if check == 404:
                    cleaned = True
                    break
                time.sleep(2)

    print("STATEMENT_CLEANUP_CONFIRMED=", cleaned)
    print("ALTER_TABLE_EXECUTED=False")
    print("CDC_CONNECTOR_ACTIVATED=False")
    print("SECRETS_PRINTED=False")
    print(
        "STAGE8_DATABASE_DISCOVERY_GATE=",
        "PASS" if success and cleaned else "BLOCKED"
    )

if not (success and cleaned):
    raise SystemExit(1)
