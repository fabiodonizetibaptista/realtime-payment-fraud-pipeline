"""Etapa 12: cenarios sequenciais de transacoes via PostgreSQL/CDC.

--plan: valida a configuracao local sem acesso cloud ou mutacoes.
--execute: insere quatro transacoes somente na execucao autorizada.

O watermark e calculado pelo Flink/Kafka, nao por este produtor.
Os registros de teste sao mantidos para evidencias ate o teardown.
"""

import argparse
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.cdc_test_scenario import connect, connector_in_state

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".local" / "etapa12-scenarios.json"
AMOUNTS = ("12.50", "21.00", "35.00", "49.00")


def plan():
    """Mostra a sequencia sem consultar ou alterar o banco."""
    print("SCENARIO_COUNT=2")
    print("TRANSACTION_COUNT=4")
    print("LEGITIMATE_TRANSACTIONS=1")
    print("FRAUD_SEQUENCE_TRANSACTIONS=3")
    print("FRAUD_WINDOW_SECONDS=60")
    print("AMOUNTS_POSITIVE=True")
    print("DIFFERENT_CARD_FOR_LEGITIMATE=True")
    print("WATERMARK_SOURCE=FLINK_KAFKA_ROWTIME")
    print("CLOUD_EXECUTION=False")


def execute():
    """Insere eventos independentes, reaproveitando FKs existentes."""
    if MANIFEST.exists():
        raise RuntimeError("SCENARIO_ALREADY_RECORDED")
    if not connector_in_state():
        raise RuntimeError("CDC_CONNECTOR_NOT_IN_STATE")

    connection = connect()
    try:
        cursor = connection.cursor()

        # Dois cartoes distintos: um legitimo e um para fraude.
        # Nenhum identificador real e impresso ou persistido.
        cursor.execute("""
            SELECT DISTINCT ON (card_id)
                account_id, card_id, merchant_id,
                currency, transaction_status
            FROM public.transactions
            WHERE card_id IS NOT NULL
            ORDER BY card_id, transaction_id
            LIMIT 2
        """)
        references = cursor.fetchall()
        connection.rollback()

        if len(references) != 2:
            raise RuntimeError("TWO_DISTINCT_CARDS_REQUIRED")

        # Reserva IDs negativos sinteticos, fora do seed convencional.
        ids = [-(10**12 + secrets.randbelow(10**12))
               for _ in range(4)]
        if len(set(ids)) != 4:
            raise RuntimeError("TEST_ID_COLLISION")

        for transaction_id in ids:
            cursor.execute(
                "SELECT 1 FROM public.transactions WHERE transaction_id = %s",
                (transaction_id,),
            )
            if cursor.fetchone():
                raise RuntimeError("TEST_ID_COLLISION")
        connection.rollback()

        events = [
            ("LEGITIMATE", references[0], ids[0], AMOUNTS[0]),
            ("FRAUD_1", references[1], ids[1], AMOUNTS[1]),
            ("FRAUD_2", references[1], ids[2], AMOUNTS[2]),
            ("FRAUD_3", references[1], ids[3], AMOUNTS[3]),
        ]

        MANIFEST.parent.mkdir(parents=True, exist_ok=True)

        # Manifesto privado criado ANTES das mutacoes.
        # Permite recuperar IDs sinteticos em caso de falha parcial.
        with MANIFEST.open("x", encoding="utf-8") as output:
            import os
            os.fchmod(output.fileno(), 0o600)
            json.dump({
                "status": "STARTED",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "test_ids": ids,
                "committed_count": 0,
            }, output)

        start = time.monotonic()

        for index, (label, ref, transaction_id, amount) in enumerate(events):
            account_id, card_id, merchant_id, currency, status = ref

            cursor.execute("""
                INSERT INTO public.transactions (
                    transaction_id, account_id, card_id, merchant_id,
                    amount, currency, transaction_status, event_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            """, (
                transaction_id, account_id, card_id, merchant_id,
                amount, currency, status,
            ))
            connection.commit()

            # Registra somente contagem e IDs sinteticos.
            with MANIFEST.open("r+", encoding="utf-8") as output:
                manifest = json.load(output)
                manifest["committed_count"] = index + 1
                output.seek(0)
                json.dump(manifest, output)
                output.truncate()

            print(f"{label}_COMMITTED=True", flush=True)

        elapsed = time.monotonic() - start

        with MANIFEST.open("r+", encoding="utf-8") as output:
            manifest = json.load(output)
            manifest["status"] = "COMPLETED"
            manifest["elapsed_seconds"] = round(elapsed, 3)
            output.seek(0)
            json.dump(manifest, output)
            output.truncate()

        print("SCENARIO_EXECUTION=COMPLETED")
        print("FRAUD_INTERVAL_UNDER_60S=" + str(elapsed <= 60))
        print("WATERMARK_CONFIRMATION=PENDING_FLINK")
        print("ALERT_CONFIRMATION=PENDING_FLINK")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("plan", "execute")
    )
    parser.add_argument(
        "--confirm-execute", action="store_true"
    )
    args = parser.parse_args()

    if args.action == "plan":
        plan()
        return

    if not args.confirm_execute:
        parser.error("execute exige --confirm-execute")

    execute()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Nunca imprime conexoes ou conteudo de registros.
        print("ETAPA12_ERROR=" + type(error).__name__)
        raise SystemExit(1) from None
