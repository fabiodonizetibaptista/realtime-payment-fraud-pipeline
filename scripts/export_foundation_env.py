"""Exporta credenciais Terraform para .env sem exibi-las no terminal."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Permite importar safety.py quando o script e executado diretamente.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TF_DIR = ROOT / "infra" / "terraform"
ENV_FILE = ROOT / ".env"

OUTPUT_TO_ENV = {
    "environment_id": "TF_VAR_foundation_environment_id",
    "kafka_bootstrap_endpoint": "KAFKA_BOOTSTRAP_ENDPOINT",
    "kafka_cluster_id": "TF_VAR_foundation_kafka_id",
    "kafka_rest_endpoint": "TF_VAR_foundation_kafka_rest_endpoint",
    "kafka_admin_api_key_id": "TF_VAR_foundation_kafka_api_key",
    "kafka_admin_api_key_secret": "TF_VAR_foundation_kafka_api_secret",
    "producer_kafka_api_key_id": "PRODUCER_KAFKA_API_KEY",
    "producer_kafka_api_key_secret": "PRODUCER_KAFKA_API_SECRET",
    "consumer_kafka_api_key_id": "CONSUMER_KAFKA_API_KEY",
    "consumer_kafka_api_key_secret": "CONSUMER_KAFKA_API_SECRET",
    "schema_registry_cluster_id": "TF_VAR_foundation_schema_registry_id",
    "schema_registry_rest_endpoint": "TF_VAR_foundation_schema_registry_rest_endpoint",
    "schema_registry_api_key_id": "TF_VAR_foundation_schema_registry_api_key",
    "schema_registry_api_key_secret": "TF_VAR_foundation_schema_registry_api_secret",
}


def _read_existing_env() -> dict[str, str]:
    from safety import load_env_file

    return load_env_file(ENV_FILE)


def _write_env_securely(values: dict[str, str]) -> None:
    # API secrets are written only to the ignored local .env file.
    # Atomic replace avoids leaving a partially written credential file.
    temporary = ENV_FILE.with_name(".env.foundation.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(temporary, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            for key in sorted(values):
                value = values[key]
                if "\n" in value or "\r" in value:
                    raise ValueError("Valor multilinha inesperado; arquivo nao foi publicado.")
                stream.write(f"{key}={value}\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, ENV_FILE)
        os.chmod(ENV_FILE, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    try:
        execution_env = dict(os.environ)
        execution_env["TF_LOG"] = "OFF"
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=TF_DIR,
            env=execution_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("Terraform output indisponivel; confira se a Foundation foi aplicada.")

        outputs = json.loads(result.stdout)
        exported = _read_existing_env()
        for output_name, env_name in OUTPUT_TO_ENV.items():
            if output_name not in outputs:
                raise RuntimeError(f"Output Terraform ausente: {output_name}.")
            value = outputs[output_name].get("value")
            if not isinstance(value, str) or not value:
                raise RuntimeError(f"Output Terraform vazio ou invalido: {output_name}.")
            exported[env_name] = value

        # O CDC usa o ID da Service Account na configuracao do
        # conector gerenciado; nao necessita de API Key Kafka propria.
        accounts = outputs.get("service_account_ids", {}).get("value", {})
        cdc_id = accounts.get("cdc") if isinstance(accounts, dict) else None
        if not isinstance(cdc_id, str) or not cdc_id:
            raise RuntimeError("ID da Service Account CDC ausente.")

        exported["CDC_SERVICE_ACCOUNT_ID"] = cdc_id

        # Exportar credenciais nao habilita ACLs.
        # A ativacao sera uma operacao explicita apos revisar todas as ACLs.
        exported["TF_VAR_enable_kafka_acls"] = "false"
        _write_env_securely(exported)
        print(f"FOUNDATION_ENV_EXPORTED=True; VARIABLES={len(OUTPUT_TO_ENV) + 2}; FILE_MODE=600")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, KeyError):
        # Nao imprimir stdout/stderr do Terraform: podem conter dados sensiveis.
        print("ERRO: nao foi possivel exportar os outputs da Foundation com seguranca.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
