"""Inventario read-only do Schema Registry da V2.

Nao imprime schemas, credenciais ou mensagens Kafka.
Nao registra novas versoes nem modifica configuracoes.
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "consumer"))

from audit_cdc import resources, terraform_state
from validate_cdc_avro import schema_registry_credentials

TOPICS = [
    "payments.public.customers",
    "payments.public.accounts",
    "payments.public.cards",
    "payments.public.merchants",
    "payments.public.transactions",
    "payments.cdc_internal.heartbeat",
]

EXPECTED_CDC = [
    f"{topic}-{kind}"
    for topic in TOPICS
    for kind in ("key", "value")
]


def request_json(url, key, secret):
    auth = base64.b64encode(
        f"{key}:{secret}".encode("utf-8")
    ).decode("ascii")

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None


def main():
    print("========== ETAPA 6 — INVENTARIO SCHEMA REGISTRY ==========")

    state = terraform_state()
    endpoint, key, secret = schema_registry_credentials(state)
    endpoint = endpoint.rstrip("/")

    http, subjects = request_json(
        endpoint + "/subjects", key, secret
    )

    if http != 200 or not isinstance(subjects, list):
        print("SUBJECTS_QUERY_HTTP=", http)
        print("INVENTORY_GATE=BLOCKED")
        return 1

    existing = set(subjects)
    cdc_existing = sorted(existing.intersection(EXPECTED_CDC))
    cdc_missing = sorted(set(EXPECTED_CDC) - existing)

    print("TOTAL_SUBJECTS=", len(existing))
    print("EXPECTED_CDC_SUBJECTS=", len(EXPECTED_CDC))
    print("CDC_SUBJECTS_FOUND=", len(cdc_existing))
    print("CDC_SUBJECTS_MISSING=", len(cdc_missing))

    for subject in cdc_missing:
        print("MISSING_CDC_SUBJECT=", subject)

    alerts = sorted(
        subject for subject in existing
        if subject.startswith("payments.fraud.detected-")
    )

    print("ALERT_SUBJECTS_FOUND=", len(alerts))

    # Consulta somente a versao e o tipo dos schemas.
    details = {}

    for subject in cdc_existing + alerts:
        encoded = quote(subject, safe="")
        code, latest = request_json(
            f"{endpoint}/subjects/{encoded}/versions/latest",
            key, secret
        )

        if code != 200 or not isinstance(latest, dict):
            raise RuntimeError("SUBJECT_VERSION_QUERY_FAILED")

        details[subject] = {
            "version": latest.get("version"),
            "schema_type": latest.get("schemaType", "AVRO"),
        }

        print(
            f"SUBJECT={subject} "
            f"VERSION={latest.get('version')} "
            f"TYPE={latest.get('schemaType', 'AVRO')}"
        )

    # Política global e política efetiva de um subject real.
    code, global_config = request_json(
        endpoint + "/config", key, secret
    )

    if code != 200 or not isinstance(global_config, dict):
        raise RuntimeError("GLOBAL_COMPATIBILITY_QUERY_FAILED")

    global_level = (
        global_config.get("compatibilityLevel")
        or global_config.get("compatibility")
    )

    print("GLOBAL_COMPATIBILITY=", global_level)

    target = "payments.public.transactions-value"

    if target in existing:
        code, config = request_json(
            endpoint + "/config/"
            + quote(target, safe="")
            + "?defaultToGlobal=true",
            key, secret
        )

        if code != 200 or not isinstance(config, dict):
            raise RuntimeError("SUBJECT_COMPATIBILITY_QUERY_FAILED")

        effective = (
            config.get("compatibilityLevel")
            or config.get("compatibility")
        )
    else:
        effective = None

    print("TEST_SUBJECT=", target)
    print("TEST_SUBJECT_COMPATIBILITY=", effective)

    # Inventario dos schemas ja controlados pelo Terraform.
    terraform_schemas = list(resources(
        state, "confluent_schema"
    ))

    print("SCHEMAS_MANAGED_IN_TERRAFORM=", len(terraform_schemas))

    report = {
        "expected_cdc_subjects": EXPECTED_CDC,
        "found_cdc_subjects": cdc_existing,
        "missing_cdc_subjects": cdc_missing,
        "alert_subjects": alerts,
        "schema_metadata": details,
        "global_compatibility": global_level,
        "test_subject": target,
        "test_subject_compatibility": effective,
        "terraform_managed_schema_count": len(terraform_schemas),
    }

    output = ROOT / "evidencias/v2/stage6-schema-inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("EVIDENCE_SAVED=True")
    print("SCHEMAS_REGISTERED_BY_SCRIPT=False")
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print("INVENTORY_GATE=PASS")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("INVENTORY_GATE=BLOCKED")
        raise SystemExit(1)
