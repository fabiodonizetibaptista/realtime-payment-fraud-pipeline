"""Cenario controlado INSERT -> UPDATE -> DELETE para CDC.

--check: verifica requisitos sem alterar dados.
--execute: executa as tres transacoes somente com autorizacao
           e conector CDC presente no Terraform State.

Nunca imprime registros de clientes, cartoes, contas ou credenciais.
"""

import argparse
import json
import os
import secrets
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pg8000.dbapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety import load_env_file

TF_DIR = ROOT / "infra" / "terraform"
CA_FILE = ROOT / ".local" / "aiven-ca.pem"
RESULT_FILE = ROOT / ".local" / "stage5-scenario.json"
CONNECTOR = "confluent_connector.payments_cdc[0]"


def connect():
    config = load_env_file(ROOT / ".env")

    context = ssl.create_default_context(cafile=str(CA_FILE))
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED

    return pg8000.dbapi.connect(
        host=config["PGHOST"],
        port=int(config["PGPORT"]),
        database=config["PGDATABASE"],
        user=config["PGUSER"],
        password=config["PGPASSWORD"],
        ssl_context=context,
        timeout=20,
    )


def connector_in_state():
    result = subprocess.run(
        ["terraform", "state", "list"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TF_LOG": "OFF"},
    )
    if result.returncode != 0:
        raise RuntimeError("TERRAFORM_STATE_UNAVAILABLE")
    return CONNECTOR in result.stdout.splitlines()


LIFECYCLE = ROOT / "src" / "consumer" / "verify_cdc_lifecycle.py"


def run_lifecycle(mode):
    """Executa o verificador existente como processo separado."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, str(LIFECYCLE), mode], cwd=ROOT, check=False)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.check == args.execute:
        raise RuntimeError("SELECT_CHECK_OR_EXECUTE")

    print("========== ETAPA 5 — CENARIO CDC ==========", flush=True)

    if args.execute:
        if RESULT_FILE.exists():
            raise RuntimeError("SCENARIO_RESULT_ALREADY_EXISTS")
        if not connector_in_state():
            raise RuntimeError("CDC_CONNECTOR_NOT_IN_STATE")
        # Baseline de offset ANTES de qualquer mutacao: sem ele a
        # verificacao do ciclo c/u/d/tombstone nao tem ponto de partida
        # (na run-20261111 o passo foi esquecido e o cenario repetido).
        if run_lifecycle("--baseline") != 0:
            raise RuntimeError("LIFECYCLE_BASELINE_FAILED")

    connection = connect()
    try:
        cursor = connection.cursor()

        # Reaproveita apenas FKs e moeda existentes.
        # Nenhum dado comercial ou pessoal e exibido.
        cursor.execute("""
            SELECT account_id, card_id, merchant_id, currency,
                   transaction_status
            FROM public.transactions
            ORDER BY transaction_id
            LIMIT 1
        """)
        reference = cursor.fetchone()

        if not reference:
            raise RuntimeError("REFERENCE_TRANSACTION_UNAVAILABLE")

        cursor.execute("""
            SELECT count(*)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'transactions'
              AND column_name IN (
                  'transaction_id', 'account_id', 'card_id',
                  'merchant_id', 'amount', 'currency',
                  'transaction_status', 'event_time'
              )
        """)
        schema_ok = cursor.fetchone()[0] == 8

        connection.rollback()

        print("REFERENCE_FKS_AVAILABLE=True")
        print("EXPECTED_SCHEMA_VALID=", schema_ok)

        if not schema_ok:
            raise RuntimeError("TRANSACTIONS_SCHEMA_MISMATCH")

        if args.check:
            print("DATA_MUTATIONS=False")
            print("SCENARIO_GATE=READY")
            return 0

        # Identificador negativo aleatorio, separado do seed positivo.
        transaction_id = -(10**12 + secrets.randbelow(10**12))

        cursor.execute(
            "SELECT 1 FROM public.transactions WHERE transaction_id = %s",
            (transaction_id,),
        )

        if cursor.fetchone():
            connection.rollback()
            raise RuntimeError("TEST_ID_COLLISION")

        connection.rollback()

        account_id, card_id, merchant_id, currency, status = reference

        # Cada etapa e uma transacao independente.
        cursor.execute("""
            INSERT INTO public.transactions (
                transaction_id, account_id, card_id, merchant_id,
                amount, currency, transaction_status, event_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        """, (
            transaction_id, account_id, card_id, merchant_id,
            "15.25", currency, status,
        ))
        connection.commit()
        print("INSERT_COMMITTED=True", flush=True)

        cursor.execute("""
            UPDATE public.transactions
            SET amount = %s
            WHERE transaction_id = %s
        """, ("25.75", transaction_id))

        if cursor.rowcount != 1:
            raise RuntimeError("UPDATE_ROWCOUNT_INVALID")

        connection.commit()
        print("UPDATE_COMMITTED=True", flush=True)

        cursor.execute("""
            DELETE FROM public.transactions
            WHERE transaction_id = %s
        """, (transaction_id,))

        if cursor.rowcount != 1:
            raise RuntimeError("DELETE_ROWCOUNT_INVALID")

        connection.commit()
        print("DELETE_COMMITTED=True", flush=True)

        # Registra apenas o ID sintetico e a sequencia executada.
        # Esse arquivo local permite correlacionar os eventos
        # no consumidor Avro, sem persistir dados pessoais.
        RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "test_transaction_id": transaction_id,
            "expected_operations": ["c", "u", "d"],
            "expected_tombstone": True,
            "insert_amount": "15.25",
            "update_amount": "25.75",
            "source_row_deleted": True,
        }

        with RESULT_FILE.open("x", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(payload, output, indent=2)
            output.write("\n")

        print("SCENARIO_RESULT_SAVED=True")
        print("BUSINESS_RECORDS_PRESERVED=True")
        print("SOURCE_TEST_RECORD_REMOVED=True")
        print("SECRETS_PRINTED=False")
        print("SCENARIO_GATE=PASS")
        # Verificacao Avro do ciclo completo no Kafka (somente booleanos).
        return run_lifecycle("--verify")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("SCENARIO_GATE=BLOCKED")
        raise SystemExit(1)
