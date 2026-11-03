"""Estado da replicacao logica no Postgres. Modos: show | drop-slot

show      : wal_level, slots, tabelas da publication e contagens.
drop-slot : remove o slot payments_cdc_slot SOMENTE se estiver inativo
            (um slot orfao retem WAL e pode encher o disco do Aiven).

Variaveis de ambiente: PGHOST, PGPASSWORD, PG_CA (obrigatorias);
PGPORT (13771), PGDATABASE (defaultdb), PGUSER (avnadmin).
"""

import argparse
import os
import ssl

import pg8000.dbapi

SLOT = "payments_cdc_slot"
PUBLICATION = "payments_publication"
EXPECTED = {"customers", "accounts", "cards", "merchants", "transactions", "heartbeat"}
COUNTED = ["public.customers", "public.accounts", "public.cards",
           "public.merchants", "public.transactions", "cdc_internal.heartbeat"]


def connect():
    context = ssl.create_default_context(cafile=os.environ["PG_CA"])
    return pg8000.dbapi.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "13771")),
        database=os.environ.get("PGDATABASE", "defaultdb"),
        user=os.environ.get("PGUSER", "avnadmin"),
        password=os.environ["PGPASSWORD"],
        ssl_context=context,
        timeout=20,
    )


def count_slots(cur):
    cur.execute("SELECT slot_name, active FROM pg_replication_slots ORDER BY 1")
    return cur.fetchall()


def do_show(conn):
    cur = conn.cursor()
    cur.execute("SHOW wal_level")
    print(f"WAL_LEVEL={cur.fetchone()[0]}")
    slots = count_slots(cur)
    for name, active in slots:
        print(f"slot={name} ativo={active}")
    print(f"SLOTS={len(slots)}")
    cur.execute("SELECT tablename FROM pg_publication_tables WHERE pubname = %s", (PUBLICATION,))
    got = {row[0] for row in cur.fetchall()}
    missing = sorted(EXPECTED - got)
    print(f"PUBLICATION_TABELAS={sorted(got)}")
    print(f"PUBLICATION_OK={not missing}" + (f" FALTANDO={missing}" if missing else ""))
    for table in COUNTED:
        cur.execute(f"SELECT count(*) FROM {table}")
        print(f"{table}={cur.fetchone()[0]}")


def do_drop(conn):
    cur = conn.cursor()
    cur.execute("SELECT active FROM pg_replication_slots WHERE slot_name = %s", (SLOT,))
    row = cur.fetchone()
    if row is None:
        print("SLOT_AUSENTE")
    elif row[0]:
        raise SystemExit("Slot ATIVO: o conector ainda esta ligado. Slot mantido.")
    else:
        cur.execute("SELECT pg_drop_replication_slot(%s)", (SLOT,))
        conn.commit()
        print("SLOT_REMOVIDO")
    print(f"SLOTS_RESTANTES={len(count_slots(cur))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["show", "drop-slot"])
    args = parser.parse_args()
    conn = connect()
    try:
        {"show": do_show, "drop-slot": do_drop}[args.mode](conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()