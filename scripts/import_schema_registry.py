"""Importa contratos CDC existentes para o Terraform State.

Nao registra novos schemas nem altera contratos remotos.
Nao imprime Terraform State, schemas ou credenciais.
Pode ser executado novamente apos uma falha parcial.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "terraform"
MANIFEST = ROOT / "schemas" / "registry" / "manifest.json"

sys.path.insert(0, str(ROOT))
from safety import load_env_file
from scripts.cdc_stage_flags import configure_flags


def terraform(*arguments, env=None):
    return subprocess.run(
        ["terraform", *arguments],
        cwd=TF_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def get_instances(state, kind, name, mode=None):
    result = []

    for resource in state.get("resources", []):
        if resource.get("type") != kind:
            continue
        if resource.get("name") != name:
            continue
        if mode and resource.get("mode") != mode:
            continue

        result.extend(
            instance
            for instance in resource.get("instances", [])
        )

    return result


def main():
    print("========== ETAPA 6 — IMPORT SCHEMAS ==========", flush=True)

    config = load_env_file(ROOT / ".env")
    env = dict(os.environ)

    for key, value in config.items():
        if value and not env.get(key):
            env[key] = value

    configure_flags(env, connector="auto", subject="auto")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    subjects = manifest.get("subjects", {})

    if len(subjects) != 12:
        raise RuntimeError("EXPECTED_TWELVE_SUBJECTS")

    state_result = terraform("state", "pull", env=env)

    if state_result.returncode != 0:
        raise RuntimeError("STATE_UNAVAILABLE")

    state = json.loads(state_result.stdout)

    clusters = get_instances(
        state,
        "confluent_schema_registry_cluster",
        "essentials",
        mode="data",
    )

    keys = get_instances(
        state,
        "confluent_api_key",
        "schema_registry",
        mode="managed",
    )

    if len(clusters) != 1 or len(keys) != 1:
        raise RuntimeError("SCHEMA_REGISTRY_RESOURCES_NOT_UNIQUE")

    cluster = clusters[0]["attributes"]
    api_key = keys[0]["attributes"]

    cluster_id = cluster.get("id")
    endpoint = cluster.get("rest_endpoint")
    key = api_key.get("id")
    secret = api_key.get("secret")

    if not all((cluster_id, endpoint, key, secret)):
        raise RuntimeError("REGISTRY_CONFIGURATION_INCOMPLETE")

    env.update({
        "IMPORT_SCHEMA_REGISTRY_API_KEY": key,
        "IMPORT_SCHEMA_REGISTRY_API_SECRET": secret,
        "IMPORT_SCHEMA_REGISTRY_REST_ENDPOINT": endpoint,
    })

    existing = {
        instance.get("index_key"): instance.get("attributes") or {}
        for instance in get_instances(
            state, "confluent_schema", "cdc", mode="managed"
        )
    }

    # Validacao completa antes de iniciar qualquer importacao.
    for subject, item in subjects.items():
        filename = item.get("file")

        if filename != f"{subject}.avsc":
            raise RuntimeError("INVALID_SCHEMA_FILENAME")

        path = ROOT / "schemas" / "registry" / filename

        if not path.is_file():
            raise RuntimeError("SCHEMA_FILE_MISSING")

        json.loads(path.read_text(encoding="utf-8"))

    print("EXPECTED_SUBJECTS=", len(subjects), flush=True)
    print("ALREADY_IMPORTED=", len(existing), flush=True)

    imported = 0

    for subject in sorted(subjects):
        attributes = existing.get(subject)

        if attributes is not None:
            if attributes.get("subject_name") != subject:
                raise RuntimeError("IMPORTED_SUBJECT_MISMATCH")
            continue

        schema_file = (
            ROOT / "schemas" / "registry" / f"{subject}.avsc"
        )

        # Algumas versoes do provider exigem SCHEMA_CONTENT
        # durante terraform import.
        import_env = dict(env)
        import_env["SCHEMA_CONTENT"] = schema_file.read_text(
            encoding="utf-8"
        )

        address = f'confluent_schema.cdc["{subject}"]'
        import_id = f"{cluster_id}/{subject}/latest"

        result = terraform(
            "import",
            "-input=false",
            "-no-color",
            address,
            import_id,
            env=import_env,
        )

        # Nao imprimir stdout/stderr do Terraform: o provider
        # pode incluir dados sensiveis em seus diagnosticos.
        if result.returncode != 0:
            print("IMPORT_FAILED_SUBJECT=", subject, flush=True)
            print("IMPORT_EXIT_CODE=", result.returncode, flush=True)
            print("ERROR_DETAILS_REDACTED=True", flush=True)
            print("IMPORT_GATE=BLOCKED", flush=True)
            return 1

        imported += 1
        print(
            f"IMPORTED={imported} SUBJECT={subject}",
            flush=True,
        )

    # Confirma os 12 contratos no State depois da importacao.
    final = terraform("state", "pull", env=env)

    if final.returncode != 0:
        raise RuntimeError("FINAL_STATE_UNAVAILABLE")

    final_state = json.loads(final.stdout)

    final_instances = get_instances(
        final_state, "confluent_schema", "cdc", mode="managed"
    )

    managed = {
        instance.get("index_key"): (
            instance.get("attributes") or {}
        ).get("subject_name")
        for instance in final_instances
    }

    passed = (
        len(managed) == 12
        and set(managed) == set(subjects)
        and all(name == subject for subject, name in managed.items())
    )

    print("NEW_IMPORTS=", imported)
    print("SCHEMAS_IN_TERRAFORM_STATE=", len(managed))
    print("ALL_SUBJECTS_MATCH=", passed)
    print("REMOTE_SCHEMA_MUTATIONS=False")
    print("SECRETS_PRINTED=False")
    print("IMPORT_GATE=", "PASS" if passed else "BLOCKED")

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("IMPORT_GATE=BLOCKED")
        raise SystemExit(1)
