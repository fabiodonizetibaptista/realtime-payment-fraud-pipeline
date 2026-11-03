"""Etapa 2 / Bloco 1: configura o usuario CDC no Aiven PostgreSQL.

Reutiliza os grants da V1. Nao altera Terraform, tabelas, dados,
publication, replication slots ou recursos Confluent.

Credenciais sao mantidas na .env e nunca exibidas.
"""

import os
import secrets
import sys
import tempfile
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

ENV_PATH = ROOT / ".env"
GRANTS_PATH = ROOT / "database/security/03_cdc_grants.sql"

ROLE = "cdc_user"

TABLES = (
    "public.customers",
    "public.accounts",
    "public.cards",
    "public.merchants",
    "public.transactions",
    "cdc_internal.heartbeat",
)


def connect(config, cdc=False):
    return pg8000.dbapi.connect(
        host=config["PGHOST"],
        port=int(config["PGPORT"]),
        database=config["PGDATABASE"],
        user=ROLE if cdc else config["PGUSER"],
        password=(
            config["CDC_PGPASSWORD"]
            if cdc else config["PGPASSWORD"]
        ),
        ssl_context=True,
        timeout=20,
    )


def apply_v1_grants(cursor):
    """Executa somente os quatro GRANTs conhecidos da V1."""

    text = GRANTS_PATH.read_text(encoding="utf-8-sig")

    sql = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )

    commands = [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]

    commands = [
        statement for statement in commands
        if statement.upper() not in ("BEGIN", "COMMIT")
    ]

    if len(commands) != 4:
        raise RuntimeError("UNEXPECTED_GRANTS_COUNT")

    if not all(
        statement.upper().startswith("GRANT ")
        for statement in commands
    ):
        raise RuntimeError("UNEXPECTED_GRANTS_SQL")

    for statement in commands:
        cursor.execute(statement)


def save_cdc_credentials(password):
    """Preserva a .env e grava a senha com permissao restrita."""

    original = ENV_PATH.read_text(encoding="utf-8")

    if any(
        line.startswith(("CDC_PGUSER=", "CDC_PGPASSWORD="))
        for line in original.splitlines()
    ):
        raise RuntimeError("CDC_ENV_ALREADY_CONFIGURED")

    content = (
        original.rstrip("\n")
        + "\nCDC_PGUSER=cdc_user"
        + "\nCDC_PGPASSWORD=" + password
        + "\n"
    )

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=ENV_PATH.parent,
            prefix=".env-cdc-",
            delete=False,
        ) as file:
            temporary = file.name
            os.fchmod(file.fileno(), 0o600)
            file.write(content)

        os.replace(temporary, ENV_PATH)

    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def check(cursor, sql, *parameters):
    cursor.execute(sql, parameters)
    return bool(cursor.fetchone()[0])


def main():
    step = "INITIALIZATION"
    admin = None
    cdc_connection = None
    committed = False

    try:
        if not ENV_PATH.is_file():
            raise RuntimeError("ENV_NOT_FOUND")

        if not GRANTS_PATH.is_file():
            raise RuntimeError("V1_GRANTS_NOT_FOUND")

        env = load_env_file(ENV_PATH)

        required = (
            "PGHOST",
            "PGPORT",
            "PGDATABASE",
            "PGUSER",
            "PGPASSWORD",
        )

        if not all(env.get(key) for key in required):
            raise RuntimeError("POSTGRES_ENV_INCOMPLETE")

        if env["PGUSER"] == ROLE:
            raise RuntimeError("ADMIN_USER_REQUIRED")

        existing_password = env.get("CDC_PGPASSWORD")
        new_password = not bool(existing_password)

        password = (
            existing_password
            or secrets.token_urlsafe(36)
        )

        # O nome da role e fixo. A senha gerada e URL-safe.
        # Evita interpolacao de caracteres SQL inesperados.
        if "'" in password or "\\" in password:
            raise RuntimeError("UNSUPPORTED_PASSWORD_CHARACTER")

        env["CDC_PGPASSWORD"] = password

        step = "ADMIN_CONNECTION"
        admin = connect(env)
        cursor = admin.cursor()

        cursor.execute(
            "SELECT EXISTS("
            "SELECT 1 FROM pg_roles WHERE rolname = %s"
            ")",
            (ROLE,),
        )

        exists = bool(cursor.fetchone()[0])

        step = "CONFIGURE_ROLE"

        if not exists:
            cursor.execute(
                "CREATE ROLE cdc_user "
                "WITH LOGIN REPLICATION "
                f"PASSWORD '{password}'"
            )

        elif new_password:
            cursor.execute(
                "ALTER ROLE cdc_user "
                "WITH LOGIN REPLICATION "
                f"PASSWORD '{password}'"
            )

        else:
            cursor.execute(
                "ALTER ROLE cdc_user "
                "WITH LOGIN REPLICATION"
            )

        step = "APPLY_V1_GRANTS"
        apply_v1_grants(cursor)

        step = "VERIFY_PRIVILEGES"

        role_ok = check(
            cursor,
            "SELECT rolcanlogin AND rolreplication "
            "AND NOT rolsuper "
            "FROM pg_roles WHERE rolname = %s",
            ROLE,
        )

        schemas_ok = all(
            check(
                cursor,
                "SELECT has_schema_privilege(%s, %s, 'USAGE')",
                ROLE,
                schema,
            )
            for schema in ("public", "cdc_internal")
        )

        tables_ok = all(
            check(
                cursor,
                "SELECT has_table_privilege(%s, %s, 'SELECT')",
                ROLE,
                table,
            )
            for table in TABLES
        )

        heartbeat_ok = check(
            cursor,
            "SELECT has_column_privilege("
            "%s, %s, %s, 'UPDATE')",
            ROLE,
            "cdc_internal.heartbeat",
            "updated_at",
        )

        business_write_denied = all(
            not check(
                cursor,
                "SELECT has_table_privilege("
                "%s, %s, 'INSERT, UPDATE, DELETE')",
                ROLE,
                table,
            )
            for table in TABLES[:5]
        )

        validations = (
            role_ok,
            schemas_ok,
            tables_ok,
            heartbeat_ok,
            business_write_denied,
        )

        if not all(validations):
            raise RuntimeError("PRIVILEGE_VALIDATION_FAILED")

        step = "COMMIT"
        admin.commit()
        committed = True

        if new_password:
            step = "STORE_CREDENTIAL"
            save_cdc_credentials(password)

        step = "VERIFY_CDC_CONNECTION"

        cdc_connection = connect(env, cdc=True)
        cdc_cursor = cdc_connection.cursor()

        cdc_cursor.execute(
            "SELECT 1 FROM public.transactions LIMIT 1"
        )

        login_ok = cdc_cursor.fetchone() is not None

        print("========== ETAPA 2 — BLOCO 1 — CDC USER ==========")
        print("CDC_ROLE_LOGIN_REPLICATION=", role_ok)
        print("CDC_SCHEMAS_USAGE=", schemas_ok)
        print("CDC_TABLES_SELECT=", tables_ok)
        print("CDC_HEARTBEAT_UPDATE=", heartbeat_ok)
        print("CDC_BUSINESS_WRITE_DENIED=", business_write_denied)
        print("CDC_SEPARATE_LOGIN_OK=", login_ok)
        print("CDC_SECRET_STORED_LOCALLY=True")
        print("SECRETS_PRINTED=False")
        print("CDC_USER_GATE=", "PASS" if login_ok else "BLOCKED")

        return 0 if login_ok else 1

    except Exception as error:
        if admin is not None and not committed:
            try:
                admin.rollback()
            except Exception:
                pass

        print("FAILED_STAGE=", step)
        print("ERROR_TYPE=", type(error).__name__)
        print("CDC_USER_GATE=BLOCKED")
        print("SECRETS_PRINTED=False")

        return 1

    finally:
        if cdc_connection is not None:
            cdc_connection.close()

        if admin is not None:
            admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
