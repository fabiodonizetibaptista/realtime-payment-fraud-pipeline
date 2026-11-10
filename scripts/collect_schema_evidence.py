"""Consolida evidencias da Etapa 6 sem consultar ou alterar a nuvem.

Fontes:
- Manifesto dos 12 schemas exportados
- Resultado real da API de compatibilidade
- Schema Avro local, usado para validar os campos propostos

Nenhum schema completo, segredo ou dado pessoal e registrado.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas" / "registry"
EVIDENCE = ROOT / "evidencias" / "schemas"

SUBJECT = "payments.public.transactions-value"
EXPECTED_TOPICS = (
    "payments.public.customers",
    "payments.public.accounts",
    "payments.public.cards",
    "payments.public.merchants",
    "payments.public.transactions",
    "payments.cdc_internal.heartbeat",
)
EXPECTED_SUBJECTS = {
    f"{topic}-{kind}"
    for topic in EXPECTED_TOPICS
    for kind in ("key", "value")
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, data):
    # Nao substituir evidencias existentes.
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, indent=2, ensure_ascii=False)
        output.write("\n")


def main():
    print("========== ETAPA 6 — EVIDENCIAS ==========")

    # Evidencias sao validadas pelo contrato dos arquivos,
    # independentemente da branch de desenvolvimento.
    manifest = read_json(SCHEMAS / "manifest.json")
    compatibility = read_json(
        EVIDENCE / "stage6-compatibility.json"
    )

    subjects = manifest.get("subjects", {})

    if set(subjects) != EXPECTED_SUBJECTS:
        raise RuntimeError("SUBJECT_SET_MISMATCH")

    for subject, metadata in subjects.items():
        if metadata.get("file") != f"{subject}.avsc":
            raise RuntimeError("SUBJECT_FILE_MISMATCH")
        if not isinstance(metadata.get("version_at_export"), int):
            raise RuntimeError("SUBJECT_VERSION_INVALID")
        if metadata.get("schema_type") != "AVRO":
            raise RuntimeError("SUBJECT_TYPE_INVALID")

        # Confirma que o schema local continua sintaticamente valido.
        read_json(SCHEMAS / metadata["file"])

    required = compatibility.get("required_without_default", {})
    optional = compatibility.get("optional_with_default", {})

    compatible_results_valid = all([
        compatibility.get("subject") == SUBJECT,
        compatibility.get("original_version")
            == subjects[SUBJECT]["version_at_export"],
        compatibility.get("compatibility_mode") == "BACKWARD",
        required.get("field") == "stage6_required_field",
        required.get("is_compatible") is False,
        optional.get("field") == "stage6_optional_field",
        optional.get("is_compatible") is True,
        compatibility.get("original_schema_unchanged") is True,
        compatibility.get("new_schema_registered") is False,
        compatibility.get("gate") == "PASS",
    ])

    if not compatible_results_valid:
        raise RuntimeError("COMPATIBILITY_EVIDENCE_INVALID")

    schema = read_json(SCHEMAS / f"{SUBJECT}.avsc")

    if schema.get("type") != "record":
        raise RuntimeError("SCHEMA_NOT_RECORD")

    original_fields = schema.get("fields")

    if not isinstance(original_fields, list):
        raise RuntimeError("SCHEMA_FIELDS_INVALID")

    original_names = {
        field["name"] for field in original_fields
    }

    if original_names.intersection({
        "stage6_required_field",
        "stage6_optional_field",
    }):
        raise RuntimeError("PROPOSED_FIELD_ALREADY_EXISTS")

    timestamp = datetime.now(timezone.utc).isoformat()

    subjects_evidence = {
        "evidence_type": "RETROSPECTIVE_INVENTORY",
        "generated_at_utc": timestamp,
        "source": "schemas/registry/manifest.json",
        "subjects": [
            {
                "subject": name,
                "version_at_export": subjects[name]["version_at_export"],
                "schema_type": "AVRO",
            }
            for name in sorted(subjects)
        ],
        "subject_count": len(subjects),
        "gate": "PASS",
    }

    # Registra apenas os metadados dos testes realmente executados.
    compatibility_evidence = {
        "evidence_type": "DERIVED_TEST_RESULT",
        "generated_at_utc": timestamp,
        "source": "evidencias/schemas/stage6-compatibility.json",
        "subject": SUBJECT,
        "tested_against_version": compatibility["original_version"],
        "compatibility": "BACKWARD",
        "required_without_default_compatible": False,
        "optional_with_default_compatible": True,
        "schema_unchanged": True,
        "version_2_registered": False,
        "gate": "PASS",
    }

    # Diff sem reproduzir os campos originais ou o schema completo.
    # Os campos abaixo sao propostas testadas, NAO uma versao 2.
    diff_evidence = {
        "evidence_type": "PROPOSED_SCHEMA_DIFF",
        "generated_at_utc": timestamp,
        "subject": SUBJECT,
        "base_version": compatibility["original_version"],
        "registered_new_version": False,
        "changes": [
            {
                "scenario": "INCOMPATIBLE",
                "operation": "ADD_FIELD",
                "field": "stage6_required_field",
                "type": "string",
                "default_present": False,
                "compatibility_result": "REJECTED",
            },
            {
                "scenario": "COMPATIBLE",
                "operation": "ADD_FIELD",
                "field": "stage6_optional_field",
                "type": ["null", "string"],
                "default_present": True,
                "default": None,
                "compatibility_result": "ACCEPTED",
            },
        ],
        "existing_fields_changed": False,
        "credentials_recorded": False,
        "personal_data_recorded": False,
        "gate": "PASS",
    }

    outputs = {
        "stage6-schema-subjects.json": subjects_evidence,
        "stage6-compatibility-summary.json": compatibility_evidence,
        "stage6-schema-evolution-diff.json": diff_evidence,
    }

    if any((EVIDENCE / name).exists() for name in outputs):
        raise RuntimeError("EVIDENCE_TARGET_ALREADY_EXISTS")

    created = []

    try:
        for filename, data in outputs.items():
            path = EVIDENCE / filename
            write_new(path, data)
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

    print("SUBJECTS_DOCUMENTED=", len(subjects))
    print("COMPATIBLE_CHANGE_ACCEPTED=True")
    print("INCOMPATIBLE_CHANGE_REJECTED=True")
    print("SCHEMA_DIFF_DOCUMENTED=True")
    print("NEW_SCHEMA_VERSION_REGISTERED=False")
    print("EVIDENCE_FILES_CREATED=", len(created))
    print("PERSONAL_DATA_RECORDED=False")
    print("SECRETS_RECORDED=False")
    print("REMOTE_CHANGES=False")
    print("STAGE6_EVIDENCE_GATE=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("STAGE6_EVIDENCE_GATE=BLOCKED")
        raise SystemExit(1)
