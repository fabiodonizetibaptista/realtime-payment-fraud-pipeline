"""Teste nao destrutivo de compatibilidade Avro no Schema Registry.

Compara duas evolucoes hipoteticas com o contrato registrado.
Nao registra novas versoes, nao altera configuracoes e nao imprime schemas.
"""

import base64
import copy
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "consumer"))

from audit_cdc import terraform_state
from validate_cdc_avro import schema_registry_credentials

SUBJECT = "payments.public.transactions-value"
OUTPUT = ROOT / "evidencias/schemas/stage6-compatibility.json"


def api_call(endpoint, key, secret, method, path, payload=None):
    auth = base64.b64encode(
        f"{key}:{secret}".encode("utf-8")
    ).decode("ascii")

    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }

    body = None

    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        endpoint.rstrip("/") + path,
        headers=headers,
        data=body,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        # Nao imprimir a resposta bruta da API.
        return error.code, None


def test_candidate(endpoint, key, secret, original, candidate):
    body = {
        "schemaType": original.get("schemaType", "AVRO"),
        "schema": json.dumps(candidate),
    }

    # Preserva referencias, caso existam no schema original.
    if original.get("references"):
        body["references"] = original["references"]

    path = (
        "/compatibility/subjects/"
        + quote(SUBJECT, safe="")
        + "/versions/latest"
    )

    code, response = api_call(
        endpoint, key, secret, "POST", path, body
    )

    if code != 200 or not isinstance(response, dict):
        raise RuntimeError("COMPATIBILITY_API_FAILED")

    result = response.get("is_compatible")

    if type(result) is not bool:
        raise RuntimeError("INVALID_COMPATIBILITY_RESPONSE")

    return result


def main():
    print("========== ETAPA 6 — COMPATIBILIDADE AVRO ==========")

    if OUTPUT.exists():
        raise RuntimeError("EVIDENCE_ALREADY_EXISTS")

    state = terraform_state()
    endpoint, key, secret = schema_registry_credentials(state)

    subject_path = "/subjects/" + quote(SUBJECT, safe="")

    code, original = api_call(
        endpoint, key, secret,
        "GET", subject_path + "/versions/latest"
    )

    if code != 200 or not isinstance(original, dict):
        raise RuntimeError("LATEST_SCHEMA_UNAVAILABLE")

    if original.get("schemaType", "AVRO") != "AVRO":
        raise RuntimeError("SUBJECT_IS_NOT_AVRO")

    version_before = original.get("version")
    schema = json.loads(original["schema"])

    if not isinstance(schema, dict):
        raise RuntimeError("SCHEMA_ROOT_NOT_OBJECT")

    if schema.get("type") != "record":
        raise RuntimeError("SCHEMA_ROOT_NOT_RECORD")

    fields = schema.get("fields")

    if not isinstance(fields, list):
        raise RuntimeError("SCHEMA_FIELDS_MISSING")

    names = {
        field.get("name")
        for field in fields
        if isinstance(field, dict)
    }

    if names.intersection({
        "stage6_required_field",
        "stage6_optional_field",
    }):
        raise RuntimeError("TEST_FIELD_ALREADY_EXISTS")

    # Cenario A: campo obrigatorio sem default.
    incompatible = copy.deepcopy(schema)
    incompatible["fields"].append({
        "name": "stage6_required_field",
        "type": "string",
    })

    # Cenario B: campo opcional com default explicito.
    compatible = copy.deepcopy(schema)
    compatible["fields"].append({
        "name": "stage6_optional_field",
        "type": ["null", "string"],
        "default": None,
    })

    rejected = test_candidate(
        endpoint, key, secret, original, incompatible
    )

    accepted = test_candidate(
        endpoint, key, secret, original, compatible
    )

    # Comprova que os testes nao modificaram a versao registrada.
    code, latest_after = api_call(
        endpoint, key, secret,
        "GET", subject_path + "/versions/latest"
    )

    if code != 200 or not isinstance(latest_after, dict):
        raise RuntimeError("POST_TEST_SCHEMA_QUERY_FAILED")

    unchanged = (
        latest_after.get("version") == version_before
        and latest_after.get("id") == original.get("id")
        and latest_after.get("schema") == original.get("schema")
    )

    passed = (
        rejected is False
        and accepted is True
        and unchanged
    )

    evidence = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "subject": SUBJECT,
        "original_version": version_before,
        "compatibility_mode": "BACKWARD",
        "required_without_default": {
            "field": "stage6_required_field",
            "is_compatible": rejected,
            "expected": False,
        },
        "optional_with_default": {
            "field": "stage6_optional_field",
            "is_compatible": accepted,
            "expected": True,
        },
        "original_schema_unchanged": unchanged,
        "new_schema_registered": False,
        "credentials_recorded": False,
        "schema_contents_recorded": False,
        "gate": "PASS" if passed else "BLOCKED",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SUBJECT=", SUBJECT)
    print("ORIGINAL_VERSION=", version_before)
    print("REQUIRED_WITHOUT_DEFAULT_COMPATIBLE=", rejected)
    print("OPTIONAL_WITH_DEFAULT_COMPATIBLE=", accepted)
    print("ORIGINAL_SCHEMA_UNCHANGED=", unchanged)
    print("NEW_SCHEMA_REGISTERED=False")
    print("EVIDENCE_SAVED=True")
    print("SECRETS_PRINTED=False")
    print("COMPATIBILITY_GATE=", evidence["gate"])

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("COMPATIBILITY_GATE=BLOCKED")
        raise SystemExit(1)
