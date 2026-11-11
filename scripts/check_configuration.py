"""Validacao local de configuracao por fase; sem rede, credenciais ou valores na saida.

Uso: python -m scripts.check_configuration foundation|pipeline|postgres|cdc
A verificacao confirma apenas presenca local; permissao e validade sao testes remotos.
"""

import argparse
import os
from pathlib import Path

from safety import load_env_file

ROOT = Path(__file__).resolve().parents[1]

# Foundation precisa de credenciais do operador. Outputs Terraform sao produzidos
# somente apos a primeira aplicacao e nao sao solicitados nesta fase.
PHASE_KEYS = {
    "foundation": (
        "AIVEN_TOKEN", "CONFLUENT_CLOUD_API_KEY", "CONFLUENT_CLOUD_API_SECRET",
        "TF_VAR_aiven_project",
    ),
    "pipeline": (
        "AIVEN_TOKEN", "CONFLUENT_CLOUD_API_KEY", "CONFLUENT_CLOUD_API_SECRET",
        "TF_VAR_foundation_environment_id", "TF_VAR_foundation_kafka_id",
        "TF_VAR_foundation_kafka_rest_endpoint", "TF_VAR_foundation_kafka_api_key",
        "TF_VAR_foundation_kafka_api_secret", "TF_VAR_foundation_schema_registry_id",
        "TF_VAR_foundation_schema_registry_rest_endpoint",
        "TF_VAR_foundation_schema_registry_api_key",
        "TF_VAR_foundation_schema_registry_api_secret",
    ),
    "postgres": (
        "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PG_CA",
    ),
    "cdc": (
        "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PG_CA",
        "CDC_PGUSER", "CDC_PGPASSWORD", "TF_VAR_cdc_connector_password",
    ),
}


def available_config(root: Path, environment: dict[str, str]) -> dict[str, str]:
    """Replica precedencia de safety.merge_env_file; recusa .env simbolico.

    Lemos apenas chaves dos valores para diagnostico. Nunca mostramos nem
    salvamos valores, e o arquivo ignorado pelo Git nao e modificado.
    """
    path = root / ".env"
    if path.is_symlink():
        raise ValueError("ENV_SYMLINK_NOT_ALLOWED")
    local = load_env_file(path)
    local.update({key: value for key, value in environment.items() if value})
    return local


def missing_keys(phase: str, config: dict[str, str]) -> list[str]:
    if phase not in PHASE_KEYS:
        raise ValueError("UNKNOWN_PHASE")
    # Variaveis de ambiente no Windows nao distinguem capitalizacao.
    present = {key.casefold(): value for key, value in config.items() if value.strip()}
    return [key for key in PHASE_KEYS[phase] if not present.get(key.casefold())]


def report(phase: str, root: Path = ROOT, environment: dict[str, str] | None = None) -> int:
    print(f"CONFIG_PHASE={phase}")
    try:
        config = available_config(root, dict(os.environ) if environment is None else environment)
        missing = missing_keys(phase, config)
    except (OSError, UnicodeError, ValueError):
        print("CONFIG_STATUS=INVALID_ENV_FILE")
        print("NEXT_ACTION=Verifique o formato e as permissoes do .env local; veja docs/local-bootstrap.md")
        print("CREDENTIAL_VALUES_PRINTED=False")
        return 2

    if missing:
        print("CONFIG_STATUS=INCOMPLETE")
        print("MISSING_KEYS=" + ",".join(missing))
        if phase == "pipeline":
            print("NEXT_ACTION=Aplique a Foundation e execute python -m scripts.export_foundation_env")
        else:
            print("NEXT_ACTION=Preencha as variaveis no .env local ou no ambiente; veja docs/local-bootstrap.md")
    else:
        print("CONFIG_STATUS=PRESENT_NOT_VERIFIED")
        print("NEXT_ACTION=Continue com os gates da fase; credenciais e servicos ainda nao foram validados")
    print("CREDENTIAL_VALUES_PRINTED=False")
    print("CLOUD_CALLS=False")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=tuple(PHASE_KEYS))
    args = parser.parse_args(argv)
    return report(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
