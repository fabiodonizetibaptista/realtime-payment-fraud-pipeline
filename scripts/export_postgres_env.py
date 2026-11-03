"""Exporta a conexao PostgreSQL do Terraform State para .env local."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
TF_DIR = ROOT / "infra" / "terraform"

# Nao exibir o State: ele contem credenciais sensiveis.
result = subprocess.run(
    ["terraform", "show", "-json"],
    cwd=TF_DIR,
    capture_output=True,
    text=True,
    env={**os.environ, "TF_LOG": "OFF"},
    check=False,
)

if result.returncode:
    raise SystemExit("BLOCKED: TERRAFORM_STATE_UNAVAILABLE")

try:
    resources = json.loads(result.stdout)["values"]["root_module"]["resources"]
    pg = next(
        resource["values"]
        for resource in resources
        if resource.get("address") == "aiven_pg.payments"
    )

    values = {
        "PGHOST": pg["service_host"],
        "PGPORT": str(pg["service_port"]),
        "PGDATABASE": "defaultdb",
        "PGUSER": pg["service_username"],
        "PGPASSWORD": pg["service_password"],
        "PGSSLMODE": "require",
    }
except (KeyError, StopIteration, TypeError, ValueError):
    raise SystemExit("BLOCKED: POSTGRES_CONNECTION_UNAVAILABLE")

if not all(values.values()):
    raise SystemExit("BLOCKED: POSTGRES_CONNECTION_INCOMPLETE")

# Preserva todas as variaveis da Foundation.
# Substitui somente as chaves PostgreSQL para manter idempotencia.
existing = ENV_FILE.read_text() if ENV_FILE.exists() else ""

lines = [
    line for line in existing.splitlines()
    if not any(
        line.startswith(f"{key}=")
        or line.startswith(f"export {key}=")
        for key in values
    )
]

lines.extend(f"{key}={value}" for key, value in values.items())

# O arquivo contem segredos: permissao apenas para o usuario.
ENV_FILE.touch(mode=0o600, exist_ok=True)
os.chmod(ENV_FILE, 0o600)
ENV_FILE.write_text("\n".join(lines) + "\n")
os.chmod(ENV_FILE, 0o600)

print("========== ETAPA 2 — ITEM 3 ==========")
print("POSTGRES_ENV_EXPORTED=True")
print("VARIABLES_CONFIGURED=", len(values))
print("SECRETS_PRINTED=False")
print("ITEM_3_GATE=PASS")
