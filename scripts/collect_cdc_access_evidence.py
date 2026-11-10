"""Coleta evidencias de volume e autenticacao CDC.

Somente leitura no PostgreSQL e Terraform State.
Nenhuma senha, chave ou identificador sensivel e impresso.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

COUNTS = {
    "public.customers": 200,
    "public.accounts": 240,
    "public.cards": 320,
    "public.merchants": 60,
    "public.transactions": 2000,
    "cdc_internal.heartbeat": 1,
}

OUTPUT = ROOT / "evidencias" / "security"


def connect(env, cdc=False):
    return pg8000.dbapi.connect(
        host=env["PGHOST"],
        port=int(env["PGPORT"]),
        database=env["PGDATABASE"],
        user="cdc_user" if cdc else env["PGUSER"],
        password=env["CDC_PGPASSWORD"] if cdc else env["PGPASSWORD"],
        ssl_context=True,
        timeout=20,
    )


def main():
    env = load_env_file(ROOT / ".env")

    required = (
        "PGHOST", "PGPORT", "PGDATABASE",
        "PGUSER", "PGPASSWORD", "PGSSLMODE",
        "CDC_PGUSER", "CDC_PGPASSWORD",
    )

    presence = {key: bool(env.get(key)) for key in required}

    if not all(presence.values()):
        print("ENV_GATE=BLOCKED")
        return 1

    if env["PGSSLMODE"] != "require":
        print("TLS_GATE=BLOCKED")
        return 1

    if env["CDC_PGUSER"] != "cdc_user":
        print("CDC_IDENTITY_GATE=BLOCKED")
        return 1

    # Confirmar a divergencia ja documentada, sem alterar o seed.
    decision = ROOT / "docs/decisions/postgres-cdc.md"
    documented = (
        decision.is_file()
        and "DECISAO_MERCHANTS=60" in decision.read_text(
            encoding="utf-8"
        )
    )

    if not documented:
        print("MERCHANTS_DOCUMENTATION_GATE=BLOCKED")
        return 1

    admin = None
    cdc = None

    try:
        admin = connect(env)
        cursor = admin.cursor()

        counts = {}

        for table in COUNTS:
            # Identificadores fixos, nunca fornecidos externamente.
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])

        counts_ok = all(
            counts[name] == expected
            for name, expected in COUNTS.items()
        )

        cursor.execute("""
            SELECT rolcanlogin, rolreplication, rolsuper
            FROM pg_roles
            WHERE rolname = %s
        """, ("cdc_user",))

        role = cursor.fetchone()

        exists = role is not None
        login = bool(role[0]) if exists else False
        replication = bool(role[1]) if exists else False
        not_superuser = not bool(role[2]) if exists else False

        cdc = connect(env, cdc=True)
        cdc_cursor = cdc.cursor()
        cdc_cursor.execute("SELECT CURRENT_USER")
        auth_ok = cdc_cursor.fetchone()[0] == "cdc_user"

    finally:
        if cdc is not None:
            cdc.close()
        if admin is not None:
            admin.close()

    # Capturar o State em memoria, sem mostrá-lo no terminal.
    state_result = subprocess.run(
        ["terraform", "-chdir=infra/terraform", "state", "pull"],
        capture_output=True,
        text=True,
        check=False,
    )

    if state_result.returncode != 0:
        print("TERRAFORM_STATE_GATE=BLOCKED")
        return 1

    state = json.loads(state_result.stdout)
    resources = state.get("resources", [])

    accounts = [
        instance.get("attributes", {})
        for resource in resources
        if resource.get("mode") == "managed"
        and resource.get("type") == "confluent_service_account"
        and resource.get("name") == "cdc"
        for instance in resource.get("instances", [])
    ]

    cdc_id = accounts[0].get("id") if len(accounts) == 1 else None
    account_ok = bool(cdc_id)

    acls = [
        instance.get("attributes", {})
        for resource in resources
        if resource.get("mode") == "managed"
        and resource.get("type") == "confluent_kafka_acl"
        for instance in resource.get("instances", [])
    ]

    cdc_acl_count = sum(
        acl.get("principal") == f"User:{cdc_id}"
        for acl in acls
    ) if cdc_id else 0

    kafka_ready = account_ok and cdc_acl_count > 0
    role_ready = (
        exists and login and replication
        and not_superuser and auth_ok
    )

    if not (counts_ok and role_ready and kafka_ready):
        print("COUNTS_GATE=", "PASS" if counts_ok else "BLOCKED")
        print("CDC_ROLE_GATE=", "PASS" if role_ready else "BLOCKED")
        print("KAFKA_IDENTITY_GATE=", "PASS" if kafka_ready else "BLOCKED")
        print("EVIDENCE_GATE=BLOCKED")
        return 1

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    count_lines = [
        "ETAPA=3",
        "EVIDENCE=TABLE_COUNTS",
        "DATABASE_SCHEMA=public",
        "MERCHANTS_REFERENCE_VIDEO=360",
        "MERCHANTS_DECISION_V2=60",
        "MERCHANTS_DIVERGENCE_DOCUMENTED=True",
    ]

    for name, expected in COUNTS.items():
        key = name.replace(".", "_").upper()
        count_lines.extend([
            f"{key}_EXPECTED={expected}",
            f"{key}_ACTUAL={counts[name]}",
            f"{key}_MATCH=True",
        ])

    count_lines.append("COUNTS_GATE=PASS")

    role_lines = [
        "ETAPA=3",
        "EVIDENCE=CDC_ROLE",
        "CDC_USER_EXISTS=True",
        "CDC_LOGIN_ENABLED=True",
        "CDC_REPLICATION_ENABLED=True",
        "CDC_NOT_SUPERUSER=True",
        "CDC_AUTHENTICATION_OK=True",
        "CDC_PASSWORD_PRESENT=True",
        "CDC_PASSWORD_PRINTED=False",
        "CDC_ROLE_GATE=PASS",
    ]

    kafka_lines = [
        "ETAPA=3",
        "EVIDENCE=KAFKA_CONNECT_IDENTITY",
        "AUTHENTICATION_MODE=SERVICE_ACCOUNT",
        "CDC_SERVICE_ACCOUNT_IN_TERRAFORM_STATE=True",
        "CDC_SERVICE_ACCOUNT_ID_AVAILABLE=True",
        f"CDC_ACLS_IN_STATE={cdc_acl_count}",
        "CONNECTOR_SPECIFIC_API_KEY_REQUIRED=False",
        "CONNECTOR_AUTHENTICATION_TESTED=False",
        "CREDENTIALS_PRINTED=False",
        "KAFKA_IDENTITY_GATE=PASS",
    ]

    files = {
        f"{stamp}-stage3-counts.txt": count_lines,
        f"{stamp}-stage3-cdc-user.txt": role_lines,
        f"{stamp}-stage3-kafka-identity.txt": kafka_lines,
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)

    if any((OUTPUT / name).exists() for name in files):
        print("EVIDENCE_GATE=BLOCKED")
        print("REASON=TIMESTAMP_COLLISION")
        return 1

    for name, lines in files.items():
        (OUTPUT / name).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print("========== ETAPA 3 — EVIDENCIAS ==========")
    print("COUNTS_GATE=PASS")
    print("CDC_ROLE_GATE=PASS")
    print("KAFKA_IDENTITY_GATE=PASS")
    print("CDC_ACLS_IN_STATE=", cdc_acl_count)
    print("ARTIFACTS_CREATED=", len(files))

    for name in files:
        print("EVIDENCE_FILE=", f"evidencias/security/{name}")

    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print("EVIDENCE_GATE=PASS")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Mensagens de driver/provider podem conter dados sensiveis.
        print("ERROR_TYPE=", type(exc).__name__)
        print("EVIDENCE_GATE=BLOCKED")
        raise SystemExit(1)
