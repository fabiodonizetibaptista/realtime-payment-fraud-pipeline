"""Coleta evidencias sanitizadas e reproduziveis do PostgreSQL.

Somente leitura. Reutiliza o preflight PostgreSQL existente.
Nao altera banco, Terraform, slots, dados ou credenciais.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import evidence_path, load_env_file

EXPECTED = {
    "public.customers": 200,
    "public.accounts": 240,
    "public.cards": 320,
    "public.merchants": 60,
    "public.transactions": 2000,
    "cdc_internal.heartbeat": 1,
}

REQUIRED_ENV = (
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGSSLMODE",
    "CDC_PGUSER",
    "CDC_PGPASSWORD",
)

EVIDENCE_DIR = evidence_path(ROOT, "database")


def main():
    # Nunca mostrar valores de ambiente ou mensagens brutas do driver.
    env = load_env_file(ROOT / ".env")

    if not all(env.get(key) for key in REQUIRED_ENV):
        print("ENV_GATE=BLOCKED")
        return 1

    if env["PGSSLMODE"] != "require":
        print("TLS_REQUIRED=False")
        return 1

    if env["CDC_PGUSER"] != "cdc_user":
        print("CDC_IDENTITY_GATE=BLOCKED")
        return 1

    # Executa a verificacao integral ja validada no bloco anterior.
    # Captura stdout/stderr em memoria para evitar exposicao acidental.
    preflight = subprocess.run(
        [sys.executable, str(ROOT / "scripts/preflight_postgres_cdc.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    if (
        preflight.returncode != 0
        or "CDC_PREFLIGHT_GATE=PASS"
        not in [
            line.replace(" ", "")
            for line in preflight.stdout.splitlines()
        ]
    ):
        print("CDC_PREFLIGHT_GATE=BLOCKED")
        return 1

    connection = None

    try:
        connection = pg8000.dbapi.connect(
            host=env["PGHOST"],
            port=int(env["PGPORT"]),
            database=env["PGDATABASE"],
            user=env["PGUSER"],
            password=env["PGPASSWORD"],
            ssl_context=True,
            timeout=20,
        )

        cursor = connection.cursor()

        cursor.execute(
            "SELECT current_setting('wal_level'), "
            "current_setting('max_replication_slots'), "
            "current_setting('max_wal_senders')"
        )
        wal, slots, senders = cursor.fetchone()

        wal_ok = (
            wal == "logical"
            and int(slots) > 0
            and int(senders) > 0
        )

        if not wal_ok:
            print("WAL_GATE=BLOCKED")
            return 1

        counts = {}
        for table in EXPECTED:
            # Identificadores fixos definidos neste script.
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])

        counts_ok = all(
            counts[table] == expected
            for table, expected in EXPECTED.items()
        )

        if not counts_ok:
            print("COUNTS_GATE=BLOCKED")
            return 1

    finally:
        if connection is not None:
            connection.close()

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    wal_content = "\n".join([
        "ETAPA=2",
        "EVIDENCIA=LOGICAL_REPLICATION",
        "PROVIDER=AIVEN",
        "WAL_LEVEL_LOGICAL=True",
        "REPLICATION_SLOTS_AVAILABLE=True",
        "WAL_SENDERS_AVAILABLE=True",
        "WAL_GATE=PASS",
        "",
    ])

    connection_lines = [
        "ETAPA=2",
        "EVIDENCIA=POSTGRES_CONNECTION",
        "CONNECTION_SOURCE=LOCAL_ENV",
    ]

    for key in REQUIRED_ENV:
        connection_lines.append(
            f"{key}_PRESENT={bool(env.get(key))}"
        )

    connection_lines.extend([
        "TLS_REQUIRED=True",
        "POSTGRES_CONNECTION_OK=True",
        "CDC_PREFLIGHT_GATE=PASS",
        "CDC_AUTHENTICATION_OK=True",
        "SECRETS_PRINTED=False",
        "CONNECTION_GATE=PASS",
        "",
    ])

    counts_lines = [
        "ETAPA=2",
        "EVIDENCIA=DATABASE_COUNTS",
        "DATABASE_SCHEMA=public",
    ]

    for table, expected in EXPECTED.items():
        label = table.replace(".", "_").upper()
        actual = counts[table]

        counts_lines.extend([
            f"{label}_EXPECTED={expected}",
            f"{label}_ACTUAL={actual}",
            f"{label}_MATCH={actual == expected}",
        ])

    counts_lines.extend([
        "COUNTS_GATE=PASS",
        "",
    ])

    artifacts = {
        f"{timestamp}-wal-level.txt": wal_content,
        f"{timestamp}-postgres-connection.txt":
            "\n".join(connection_lines),
        f"{timestamp}-database-counts.txt":
            "\n".join(counts_lines),
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Nao sobrescrever evidencias anteriores da mesma janela.
    if any((EVIDENCE_DIR / name).exists() for name in artifacts):
        print("EVIDENCE_GATE=BLOCKED")
        print("REASON=TIMESTAMP_COLLISION")
        return 1

    for name, content in artifacts.items():
        (EVIDENCE_DIR / name).write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )

    print("========== ETAPA 2 — EVIDENCIAS ==========")
    print("WAL_GATE=PASS")
    print("CONNECTION_GATE=PASS")
    print("COUNTS_GATE=PASS")
    print("ARTIFACTS_CREATED=", len(artifacts))

    for name in artifacts:
        print("EVIDENCE_FILE=", EVIDENCE_DIR.relative_to(ROOT) / name)

    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")
    print("EVIDENCE_GATE=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        print("EVIDENCE_GATE=BLOCKED")
        raise SystemExit(1)
