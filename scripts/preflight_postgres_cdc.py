"""Preflight somente leitura do PostgreSQL CDC da V2.

Reaproveita o contrato de validacao da V1.
Nao cria, altera ou remove recursos, slots ou dados.
Aiven fornece wal_level=logical; o preflight valida esse requisito.
"""

import os
import ssl
import sys
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

REQUIRED_CONFIG = (
    "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD",
    "CDC_PGUSER", "CDC_PGPASSWORD", "PG_CA",
)


def read_config():
    """Valida pre-requisitos locais antes de abrir qualquer conexao."""
    config = load_env_file(ROOT / ".env")
    # Ambiente explicito tem precedencia sobre o arquivo local.
    config.update({key: os.environ[key] for key in REQUIRED_CONFIG if os.environ.get(key)})
    missing = [key for key in REQUIRED_CONFIG if not config.get(key)]
    if missing:
        print("POSTGRES_CONFIG_STATUS=INCOMPLETE")
        print("POSTGRES_MISSING_KEYS=" + ",".join(missing))
        print("NEXT_ACTION=Configure as chaves no .env local ou ambiente; veja docs/deployment.md")
        raise RuntimeError("POSTGRES_ENV_INCOMPLETE")
    try:
        port = int(config["PGPORT"])
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        raise RuntimeError("POSTGRES_PORT_INVALID") from None
    ca = Path(config["PG_CA"]).expanduser()
    if not ca.is_file():
        print("POSTGRES_CA_STATUS=MISSING_FILE")
        print("NEXT_ACTION=Configure PG_CA com o caminho do certificado CA obtido da Aiven")
        raise RuntimeError("POSTGRES_CA_MISSING")
    return config


EXPECTED_COUNTS = {
    "public.customers": 200,
    "public.accounts": 240,
    "public.cards": 320,
    "public.merchants": 60,
    "public.transactions": 2000,
    "cdc_internal.heartbeat": 1,
}

EXPECTED_PUBLICATION = {
    tuple(name.split("."))
    for name in EXPECTED_COUNTS
}

BUSINESS_TABLES = tuple(EXPECTED_COUNTS)[:5]


def connect(env, use_cdc=False):
    # TLS com verificacao de certificado e hostname (equivalente a verify-full).
    context = ssl.create_default_context(cafile=str(Path(env["PG_CA"]).expanduser()))
    return pg8000.dbapi.connect(
        host=env["PGHOST"],
        port=int(env["PGPORT"]),
        database=env["PGDATABASE"],
        user=env["CDC_PGUSER"] if use_cdc else env["PGUSER"],
        password=(
            env["CDC_PGPASSWORD"]
            if use_cdc else env["PGPASSWORD"]
        ),
        ssl_context=context,
        timeout=20,
    )


def scalar(cursor, sql, *params):
    # pg8000: consultas sem parametros nao recebem uma tupla vazia.
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    return cursor.fetchone()[0]


def verify():
    env = read_config()

    admin = None
    cdc = None

    try:
        admin = connect(env)
        cur = admin.cursor()

        wal_ok = scalar(
            cur, "SHOW wal_level"
        ) == "logical"

        slots = scalar(
            cur, "SHOW max_replication_slots"
        )

        senders = scalar(
            cur, "SHOW max_wal_senders"
        )

        replication_ok = (
            wal_ok
            and int(slots) > 0
            and int(senders) > 0
        )

        cur.execute("""
            SELECT schemaname, tablename
            FROM pg_publication_tables
            WHERE pubname = %s
        """, ("payments_publication",))

        publication_tables = {tuple(row) for row in cur.fetchall()}

        publication_actions_ok = bool(scalar(cur, """
            SELECT pubinsert AND pubupdate AND pubdelete
            FROM pg_publication
            WHERE pubname = %s
        """, "payments_publication"))

        publication_ok = (
            publication_tables == EXPECTED_PUBLICATION
            and publication_actions_ok
        )

        counts = {}

        # Nomes fixos no codigo; nenhum identificador vem do usuario.
        for table in EXPECTED_COUNTS:
            counts[table] = scalar(
                cur, f"SELECT COUNT(*) FROM {table}"
            )

        counts_ok = all(
            counts[table] == expected
            for table, expected in EXPECTED_COUNTS.items()
        )

        cur.execute("""
            SELECT n.nspname, c.relname, c.relreplident
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname IN ('public', 'cdc_internal')
        """)

        identities = {
            (schema, table): identity
            for schema, table, identity in cur.fetchall()
        }

        replica_ok = all(
            identities.get(name) == "f"
            for name in EXPECTED_PUBLICATION
        )

        role_ok = bool(scalar(cur, """
            SELECT rolcanlogin AND rolreplication
                   AND NOT rolsuper
            FROM pg_roles
            WHERE rolname = %s
        """, "cdc_user"))

        schema_usage_ok = all(
            scalar(
                cur,
                "SELECT has_schema_privilege(%s, %s, 'USAGE')",
                "cdc_user", schema
            )
            for schema in ("public", "cdc_internal")
        )

        select_ok = all(
            scalar(
                cur,
                "SELECT has_table_privilege(%s, %s, 'SELECT')",
                "cdc_user", table
            )
            for table in EXPECTED_COUNTS
        )

        heartbeat_ok = bool(scalar(
            cur,
            "SELECT has_column_privilege(%s, %s, %s, 'UPDATE')",
            "cdc_user",
            "cdc_internal.heartbeat",
            "updated_at"
        ))

        write_denied = all(
            not scalar(
                cur,
                "SELECT has_table_privilege("
                "%s, %s, 'INSERT, UPDATE, DELETE')",
                "cdc_user", table
            )
            for table in BUSINESS_TABLES
        )

        # O slot pertence ao ciclo de vida do futuro conector.
        slot_exists = bool(scalar(cur, """
            SELECT EXISTS (
                SELECT 1 FROM pg_replication_slots
                WHERE slot_name = %s
            )
        """, "payments_cdc_slot"))

        cdc = connect(env, use_cdc=True)
        cdc_cursor = cdc.cursor()

        cdc_login_ok = (
            scalar(cdc_cursor, "SELECT CURRENT_USER")
            == env["CDC_PGUSER"]
        )

        cdc_read_ok = (
            scalar(
                cdc_cursor,
                "SELECT COUNT(*) FROM public.transactions"
            ) == 2000
        )

        results = {
            "POSTGRES_CONNECTION_OK": True,
            "WAL_LEVEL_LOGICAL": wal_ok,
            "LOGICAL_REPLICATION_READY": replication_ok,
            "PUBLICATION_TABLES_OK": publication_ok,
            "COUNTS_OK": counts_ok,
            "REPLICA_IDENTITY_FULL_OK": replica_ok,
            "CDC_ROLE_LOGIN_REPLICATION": role_ok,
            "CDC_SCHEMA_USAGE_OK": schema_usage_ok,
            "CDC_TABLES_SELECT_OK": select_ok,
            "CDC_HEARTBEAT_UPDATE_OK": heartbeat_ok,
            "CDC_BUSINESS_WRITE_DENIED": write_denied,
            "CDC_SEPARATE_LOGIN_OK": cdc_login_ok,
            "CDC_READ_OK": cdc_read_ok,
        }

        print("========== ETAPA 2 — BLOCO 1 — CDC PREFLIGHT ==========")

        for key, value in results.items():
            print(f"{key}={value}")

        print("CDC_SLOT_EXISTS=", slot_exists)
        print("DATABASE_SCHEMA=public")
        print("SECRETS_PRINTED=False")
        print("REMOTE_CHANGES=False")

        passed = all(results.values())

        print("CDC_PREFLIGHT_GATE=", "PASS" if passed else "BLOCKED")

        return 0 if passed else 1

    finally:
        if cdc is not None:
            cdc.close()
        if admin is not None:
            admin.close()


if __name__ == "__main__":
    try:
        raise SystemExit(verify())
    except Exception as exc:
        print("ERROR_TYPE=", type(exc).__name__)
        print("CDC_PREFLIGHT_GATE=BLOCKED")
        raise SystemExit(1)
