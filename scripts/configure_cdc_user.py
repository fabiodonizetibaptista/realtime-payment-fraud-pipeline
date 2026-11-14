"""Configura/recupera o usuário CDC em PostgreSQL da Aiven.

Uso: python scripts/configure_cdc_user.py --check | --apply
--check é somente leitura. --apply altera a role e seus GRANTs.
Credenciais não são impressas. Repete --apply com a senha local para recuperar
execuções parciais, sem recriar o banco ou depender de uma execução anterior.
"""

import argparse
import os
import re
import secrets
import ssl
import sys
import tempfile
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file
from scripts.bootstrap_postgres import connect as connect_admin

ENV_PATH = ROOT / ".env"
GRANTS_PATH = ROOT / "database" / "security" / "03_cdc_grants.sql"
ROLE = "cdc_user"
TABLES = (
    "public.customers",
    "public.accounts",
    "public.cards",
    "public.merchants",
    "public.transactions",
    "cdc_internal.heartbeat",
)


def _config() -> dict:
    """Evita credenciais herdadas que divirjam do clone auditado."""
    if not ENV_PATH.is_file():
        raise RuntimeError("ENV_NOT_FOUND")
    config = load_env_file(ENV_PATH)
    for key in (
        "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PG_CA",
        "CDC_PGUSER", "CDC_PGPASSWORD", "TF_VAR_cdc_connector_password",
    ):
        process_value = os.environ.get(key)
        file_value = config.get(key)
        if process_value and file_value and process_value != file_value:
            raise RuntimeError(f"POSTGRES_ENV_CONFLICT:{key}")
        if process_value and not file_value:
            config[key] = process_value
    required = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PG_CA")
    if not all(config.get(key) for key in required):
        raise RuntimeError("POSTGRES_ENV_INCOMPLETE")
    if config["PGUSER"] == ROLE:
        raise RuntimeError("ADMIN_USER_REQUIRED")
    if config.get("CDC_PGUSER") not in (None, "", ROLE):
        raise RuntimeError("CDC_ROLE_CONFLICT")
    if not GRANTS_PATH.is_file():
        raise RuntimeError("GRANTS_FILE_NOT_FOUND")
    if not Path(config["PG_CA"]).expanduser().is_file():
        raise RuntimeError("POSTGRES_CA_MISSING")
    return config


def _save_credentials(password: str) -> None:
    """Preserva variáveis alheias, substituindo só credenciais CDC deste clone.

    Grava primeiro as credenciais; se o SQL falhar, um --apply subsequente
    reutiliza a mesma senha e recupera a role. Não há janela de senha perdida.
    """
    previous = ENV_PATH.read_text(encoding="utf-8")
    changes = {
        "CDC_PGUSER": ROLE,
        "CDC_PGPASSWORD": password,
        "TF_VAR_cdc_connector_password": password,
    }
    remaining = [
        line for line in previous.splitlines()
        if not any(re.match(rf"^\s*(?:export\s+)?{re.escape(key)}\s*=", line)
                   for key in changes)
    ]
    remaining.extend(f"{key}={value}" for key, value in changes.items())

    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=ENV_PATH.parent, prefix=".env-cdc-",
        ) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.fchmod(handle.fileno(), 0o600)
            handle.write("\n".join(remaining) + "\n")
        os.replace(temp, ENV_PATH)
        if os.name == "posix":
            os.chmod(ENV_PATH, 0o600)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _grant_sql() -> list[str]:
    text = GRANTS_PATH.read_text(encoding="utf-8-sig")
    sql = "\n".join(line for line in text.splitlines()
                    if not line.lstrip().startswith("--"))
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    commands = [s for s in statements if s.upper() not in ("BEGIN", "COMMIT")]
    if len(commands) != 4 or not all(s.upper().startswith("GRANT ") for s in commands):
        raise RuntimeError("UNEXPECTED_GRANTS_SQL")
    return commands


def _flag(cursor, sql, *params):
    cursor.execute(sql, params)
    return bool(cursor.fetchone()[0])


def _role_status(cursor) -> dict[str, bool]:
    cursor.execute(
        "SELECT rolcanlogin, rolreplication, rolsuper FROM pg_roles WHERE rolname = %s",
        (ROLE,),
    )
    row = cursor.fetchone()
    role_ok = bool(row and row[0] and row[1] and not row[2])
    schemas_ok = all(
        _flag(cursor, "SELECT has_schema_privilege(%s, %s, 'USAGE')", ROLE, schema)
        for schema in ("public", "cdc_internal")
    ) if row else False
    tables_ok = all(
        _flag(cursor, "SELECT has_table_privilege(%s, %s, 'SELECT')", ROLE, table)
        for table in TABLES
    ) if row else False
    heartbeat_ok = _flag(
        cursor, "SELECT has_column_privilege(%s, %s, %s, 'UPDATE')",
        ROLE, "cdc_internal.heartbeat", "updated_at",
    ) if row else False
    business_write_denied = all(
        not _flag(cursor, "SELECT has_table_privilege(%s, %s, 'INSERT, UPDATE, DELETE')", ROLE, table)
        for table in TABLES[:5]
    ) if row else False
    return {
        "CDC_ROLE_LOGIN_REPLICATION": role_ok,
        "CDC_SCHEMAS_USAGE": schemas_ok,
        "CDC_TABLES_SELECT": tables_ok,
        "CDC_HEARTBEAT_UPDATE": heartbeat_ok,
        "CDC_BUSINESS_WRITE_DENIED": business_write_denied,
    }


def _connect_cdc(config: dict):
    # Mesmo TLS verify-full do bootstrap administrativo.
    context = ssl.create_default_context(cafile=str(Path(config["PG_CA"]).expanduser()))
    return pg8000.dbapi.connect(
        host=config["PGHOST"], port=int(config["PGPORT"]),
        database=config["PGDATABASE"], user=ROLE,
        password=config["CDC_PGPASSWORD"], ssl_context=context, timeout=20,
    )


def main(mode: str) -> int:
    stage = "INITIALIZATION"
    admin = None
    cdc_conn = None
    committed = False
    try:
        config = _config()
        grants = _grant_sql()  # Valida o SQL antes de qualquer mutação.
        stage = "ADMIN_CONNECTION"
        admin = connect_admin()
        cursor = admin.cursor()

        if mode == "--check":
            stage = "READ_ONLY_CHECK"
            status = _role_status(cursor)
            for key, value in status.items():
                print(f"{key}={value}")
            print("CDC_PASSWORD_PRESENT=", bool(config.get("CDC_PGPASSWORD")))
            print("DATABASE_CHANGES=False")
            passed = all(status.values()) and bool(config.get("CDC_PGPASSWORD"))
            print("CDC_USER_GATE=", "PASS" if passed else "BLOCKED")
            admin.rollback()  # Encerra qualquer transação implícita de leitura.
            return 0 if passed else 1

        password = config.get("CDC_PGPASSWORD") or secrets.token_urlsafe(36)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", password):
            raise RuntimeError("CDC_PASSWORD_INVALID_FORMAT")
        connector_password = config.get("TF_VAR_cdc_connector_password")
        if connector_password and connector_password != password:
            raise RuntimeError("CDC_CONNECTOR_PASSWORD_CONFLICT")

        # Persistir antes do SQL torna a recuperação idempotente se falhar o
        # commit; a mesma senha é reutilizada no próximo --apply.
        stage = "STORE_CREDENTIAL"
        _save_credentials(password)
        config["CDC_PGPASSWORD"] = password

        # O valor literal é escapado pelo próprio PostgreSQL em uma query
        # parametrizada. CREATE/ALTER ROLE não recebe senha concatenada crua.
        stage = "CONFIGURE_ROLE"
        cursor.execute("SELECT quote_literal(%s)", (password,))
        quoted_password = cursor.fetchone()[0]
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = %s)", (ROLE,))
        exists = bool(cursor.fetchone()[0])
        sql = (
            "ALTER ROLE cdc_user WITH LOGIN REPLICATION PASSWORD "
            if exists else "CREATE ROLE cdc_user WITH LOGIN REPLICATION PASSWORD "
        )
        cursor.execute(sql + quoted_password)

        stage = "APPLY_GRANTS"
        for statement in grants:
            cursor.execute(statement)

        stage = "VERIFY_PRIVILEGES"
        status = _role_status(cursor)
        if not all(status.values()):
            raise RuntimeError("PRIVILEGE_VALIDATION_FAILED")

        stage = "COMMIT"
        admin.commit()
        committed = True
        stage = "VERIFY_CDC_CONNECTION"
        cdc_conn = _connect_cdc(config)
        cdc_cursor = cdc_conn.cursor()
        cdc_cursor.execute("SELECT 1 FROM public.transactions LIMIT 1")
        login_ok = cdc_cursor.fetchone() is not None
        for key, value in status.items():
            print(f"{key}={value}")
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
        print("FAILED_STAGE=", stage)
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("CDC_USER_GATE=BLOCKED")
        print("SECRETS_PRINTED=False")
        return 1
    finally:
        if cdc_conn is not None:
            cdc_conn.close()
        if admin is not None:
            admin.close()


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica (--check) ou configura (--apply) o usuário PostgreSQL CDC."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="somente leitura")
    group.add_argument("--apply", action="store_true", help="altera role e GRANTs")
    args = parser.parse_args(argv)
    return main("--apply" if args.apply else "--check")


if __name__ == "__main__":
    raise SystemExit(cli())
