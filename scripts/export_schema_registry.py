"""Exporta os 12 contratos CDC da V2 para arquivos .avsc.

Fonte: Schema Registry existente.
Operacao somente leitura na API.
Nao imprime credenciais ou conteudo dos contratos.
Nao sobrescreve arquivos existentes.
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "consumer"))

from audit_cdc import terraform_state
from validate_cdc_avro import schema_registry_credentials

TOPICS = (
    "payments.public.customers",
    "payments.public.accounts",
    "payments.public.cards",
    "payments.public.merchants",
    "payments.public.transactions",
    "payments.cdc_internal.heartbeat",
)

SUBJECTS = tuple(
    f"{topic}-{kind}"
    for topic in TOPICS
    for kind in ("key", "value")
)

DESTINATION = ROOT / "schemas" / "registry"


def fetch_schema(endpoint, key, secret, subject):
    credentials = base64.b64encode(
        f"{key}:{secret}".encode("utf-8")
    ).decode("ascii")

    url = (
        endpoint.rstrip("/")
        + "/subjects/"
        + quote(subject, safe="")
        + "/versions/latest"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    print("========== ETAPA 6 — EXPORT SCHEMAS ==========")

    if DESTINATION.exists() and any(DESTINATION.iterdir()):
        raise RuntimeError("SCHEMA_DIRECTORY_NOT_EMPTY")

    state = terraform_state()
    endpoint, key, secret = schema_registry_credentials(state)

    contracts = {}

    # Recupera e valida os 12 contratos antes de gravar arquivos.
    for subject in SUBJECTS:
        result = fetch_schema(endpoint, key, secret, subject)

        if result.get("subject") != subject:
            raise RuntimeError("SUBJECT_MISMATCH")

        if result.get("schemaType", "AVRO") != "AVRO":
            raise RuntimeError("UNEXPECTED_SCHEMA_TYPE")

        if result.get("references"):
            raise RuntimeError("SCHEMA_REFERENCES_REQUIRE_REVIEW")

        raw_schema = result.get("schema")

        if not isinstance(raw_schema, str):
            raise RuntimeError("INVALID_SCHEMA_CONTENT")

        parsed = json.loads(raw_schema)

        if not isinstance(parsed, (dict, list, str)):
            raise RuntimeError("INVALID_AVRO_STRUCTURE")

        contracts[subject] = {
            "schema": raw_schema,
            "version": result.get("version"),
        }

    if len(contracts) != 12:
        raise RuntimeError("SCHEMA_COUNT_MISMATCH")

    DESTINATION.mkdir(parents=True, exist_ok=True)

    created = []

    try:
        for subject, item in contracts.items():
            path = DESTINATION / f"{subject}.avsc"

            # Exclusividade: nunca sobrescrever contratos locais.
            with path.open("x", encoding="utf-8") as output:
                output.write(item["schema"].rstrip() + "\n")

            created.append(path)

    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

    manifest = {
        "source": "Confluent Schema Registry — V2",
        "subjects": {
            subject: {
                "file": f"{subject}.avsc",
                "version_at_export": item["version"],
                "schema_type": "AVRO",
            }
            for subject, item in contracts.items()
        },
        "remote_mutations": False,
    }

    manifest_path = DESTINATION / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Confirma integridade dos arquivos gravados.
    valid = all(
        json.loads(
            (DESTINATION / f"{subject}.avsc").read_text(
                encoding="utf-8"
            )
        ) == json.loads(item["schema"])
        for subject, item in contracts.items()
    )

    print("EXPECTED_SCHEMAS=", len(SUBJECTS))
    print("EXPORTED_SCHEMAS=", len(created))
    print("ALL_SCHEMAS_VALID=", valid)
    print("MANIFEST_CREATED=", manifest_path.is_file())
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print("SCHEMA_EXPORT_GATE=", "PASS" if valid else "BLOCKED")

    return 0 if valid else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("SCHEMA_EXPORT_GATE=BLOCKED")
        raise SystemExit(1)
