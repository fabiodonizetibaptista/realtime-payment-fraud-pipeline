"""Prepara e valida o PostgreSQL de origem para o pipeline CDC.

Uso:
  python scripts/bootstrap_postgres.py check       # somente leitura
  python scripts/bootstrap_postgres.py apply       # altera banco: DDL e seed

Credenciais: .env na raiz do projeto; nunca imprime valores confidenciais.
"""

import argparse
import os
import sys
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database/migrations/01_schema.sql"
SEED = ROOT / "database/seeds/02_seed.sql"
EXPECTED = {
    "public.customers": 200,
    "public.accounts": 240,
    "public.cards": 320,
    "public.merchants": 60,
    "public.transactions": 2000,
    "cdc_internal.heartbeat": 1,
}


def read_local_env():
    # Nao faz source de shell nem executa comandos vindos do .env.
    path = ROOT / ".env"
    if not path.is_file():
        raise RuntimeError("LOCAL_ENV_MISSING")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().removeprefix("export ").strip()] = value.strip().strip('"').strip("'")
    return values


def connect():
    stored = read_local_env()
    # Usa credenciais exportadas dos recursos gerenciados,
    # evitando hosts e senhas fixos no codigo.
    keys = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")
    if not all(stored.get(k) for k in keys):
        raise RuntimeError("POSTGRES_ENV_INCOMPLETE")
    return pg8000.dbapi.connect(
        host=stored["PGHOST"],
        port=int(stored["PGPORT"]),
        database=stored["PGDATABASE"],
        user=stored["PGUSER"],
        password=stored["PGPASSWORD"],
        ssl_context=True,
        timeout=20,
    )


def check(conn):
    cur = conn.cursor()
    cur.execute("SELECT current_setting('wal_level')")
    wal = cur.fetchone()[0]
    cur.execute("SELECT schemaname, tablename FROM pg_publication_tables WHERE pubname = 'payments_publication'")
    publication = {f"{s}.{t}" for s, t in cur.fetchall()}
    print("WAL_LEVEL_LOGICAL=", wal == "logical")
    print("PUBLICATION_TABLES_OK=", publication == set(EXPECTED))
    all_ok = wal == "logical" and publication == set(EXPECTED)
    for table, expected in EXPECTED.items():
        # Somente nomes fixos, definidos neste arquivo; sem interpolacao externa.
        try:
            cur.execute(f"SELECT count(*) FROM {table}")
            actual = cur.fetchone()[0]
            ok = actual == expected
        except pg8000.dbapi.DatabaseError:
            conn.rollback()
            actual = "MISSING"
            ok = False
        print(f"COUNT_{table.replace('.', '_').upper()}=", actual)
        all_ok = all_ok and ok
    cur.execute("""
        SELECT n.nspname || '.' || c.relname, c.relreplident
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE (n.nspname || '.' || c.relname) = ANY(%s)
    """, (list(EXPECTED),))
    replica = {name: ident for name, ident in cur.fetchall()}
    replica_ok = all(replica.get(name) == "f" for name in EXPECTED)
    print("REPLICA_IDENTITY_FULL_OK=", replica_ok)
    all_ok = all_ok and replica_ok
    print("ITEM_5_6_GATE=", "PASS" if all_ok else "BLOCKED")
    return all_ok


def apply(conn):
    # O SQL versionado ja contem BEGIN/COMMIT e operacoes idempotentes.
    # Desabilitar implicit transactions evita interferencia do driver com BEGIN.
    conn.autocommit = True
    for label, path in (("SCHEMA", SCHEMA), ("SEED", SEED)):
        if not path.is_file():
            raise RuntimeError(f"{label}_SOURCE_MISSING")
        sql = path.read_text(encoding="utf-8-sig")
        if not sql.strip():
            raise RuntimeError(f"{label}_EMPTY")
        cur = conn.cursor()
        cur.execute(sql)
        print(f"{label}_APPLIED=True")
    return check(conn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "apply"))
    args = parser.parse_args()
    conn = None
    try:
        conn = connect()
        print("POSTGRES_CONNECTION_OK=True")
        valid = apply(conn) if args.mode == "apply" else check(conn)
        return 0 if valid else 1
    except Exception as exc:
        # Erros de drivers e banco podem conter dados de conexao;
        # nao imprimir a mensagem nem traceback.
        print("ITEM_5_6_GATE=BLOCKED")
        print("ERROR_TYPE=", type(exc).__name__)
        if isinstance(exc, RuntimeError):
            print("ERROR_CODE=", str(exc))
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
