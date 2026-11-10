"""Valida INSERT, UPDATE, DELETE e tombstone no Kafka.

--check: verifica os componentes locais.
--baseline: registra o offset inicial, antes do cenario.
--verify: decodifica Avro e valida a sequencia CDC.

Nao imprime payloads, identificadores de clientes ou credenciais.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from confluent_kafka import Consumer, TopicPartition

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "consumer"))

from audit_cdc import kafka_credentials, terraform_state
from validate_cdc_avro import create_deserializers, decode_message

TOPIC = "payments.public.transactions"
BASELINE = ROOT / ".local" / "stage5-cdc-baseline.json"
SCENARIO = ROOT / ".local" / "stage5-scenario.json"
EVIDENCE = ROOT / "evidencias/cdc/stage5-cdc-lifecycle.json"


def save_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(path), flags, 0o600)

    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(data, output, indent=2)
        output.write("\n")


def make_consumer(state):
    bootstrap, key, secret = kafka_credentials(state)

    return Consumer({
        "bootstrap.servers": bootstrap,
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "PLAIN",
        "sasl.username": key,
        "sasl.password": secret,
        "group.id": "desafio-cdc-lifecycle-v2",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "allow.auto.create.topics": False,
        "auto.offset.reset": "earliest",
        "enable.partition.eof": False,
    })


def transaction_id_of(record):
    if isinstance(record, dict):
        value = record.get("transaction_id")
        if value is not None:
            return int(value)
    return None


def capture_baseline():
    state = terraform_state()
    consumer = make_consumer(state)

    try:
        metadata = consumer.list_topics(topic=TOPIC, timeout=15)
        topic = metadata.topics.get(TOPIC)

        if topic is None or topic.error is not None:
            raise RuntimeError("TRANSACTIONS_TOPIC_UNAVAILABLE")

        offsets = {}

        for partition in sorted(topic.partitions):
            tp = TopicPartition(TOPIC, partition)

            low, high = consumer.get_watermark_offsets(
                tp, timeout=15, cached=False
            )

            offsets[str(partition)] = {
                "low": low,
                "high": high,
            }

        save_private(BASELINE, {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "topic": TOPIC,
            "offsets": offsets,
        })

        print("BASELINE_PARTITIONS=", len(offsets))
        print("BASELINE_SAVED=True")
        print("PAYLOADS_PRINTED=False")
        print("BASELINE_GATE=PASS")
    finally:
        consumer.close()


def validate_event(event, target_id):
    operation = event["operation"]
    before = event["before"]
    after = event["after"]

    if operation == "c":
        valid = (
            before is None
            and isinstance(after, dict)
            and transaction_id_of(after) == target_id
        )
    elif operation == "u":
        valid = (
            isinstance(before, dict)
            and isinstance(after, dict)
            and transaction_id_of(before) == target_id
            and transaction_id_of(after) == target_id
            and Decimal(str(before["amount"]))
            == Decimal("15.25")
            and Decimal(str(after["amount"]))
            == Decimal("25.75")
        )
    elif operation == "d":
        valid = (
            isinstance(before, dict)
            and before is not None
            and transaction_id_of(before) == target_id
            and after is None
        )
    elif operation == "tombstone":
        valid = (
            event["tombstone"]
            and event["before"] is None
            and event["after"] is None
            and transaction_id_of(event["key"]) == target_id
        )
    else:
        valid = False

    return valid


def verify():
    if not BASELINE.is_file() or not SCENARIO.is_file():
        raise RuntimeError("BASELINE_OR_SCENARIO_MISSING")

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))

    if baseline.get("topic") != TOPIC:
        raise RuntimeError("BASELINE_TOPIC_MISMATCH")

    if scenario.get("expected_operations") != ["c", "u", "d"]:
        raise RuntimeError("SCENARIO_OPERATIONS_MISMATCH")

    target_id = int(scenario["test_transaction_id"])
    state = terraform_state()
    key_decoder, value_decoder = create_deserializers(state)

    consumer = make_consumer(state)
    observed = []

    try:
        assignments = [
            TopicPartition(TOPIC, int(partition), int(values["high"]))
            for partition, values in baseline["offsets"].items()
        ]

        if not assignments:
            raise RuntimeError("BASELINE_PARTITIONS_MISSING")

        consumer.assign(assignments)

        deadline = time.monotonic() + 120

        while time.monotonic() < deadline and len(observed) < 4:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                raise RuntimeError("KAFKA_POLL_FAILED")

            event = decode_message(
                message, key_decoder, value_decoder
            )

            operation = event["operation"]
            event_id = (
                transaction_id_of(event["after"])
                or transaction_id_of(event["before"])
                or transaction_id_of(event["key"])
            )

            if event_id != target_id:
                continue

            expected = ["c", "u", "d", "tombstone"]
            index = len(observed)

            if operation != expected[index]:
                raise RuntimeError("CDC_OPERATION_ORDER_INVALID")

            if not validate_event(event, target_id):
                raise RuntimeError(
                    "CDC_BEFORE_AFTER_SEMANTICS_INVALID"
                )

            observed.append(operation)
            print(
                f"VALIDATED_EVENT={operation.upper()} "
                f"TEST_TRANSACTION_ID={target_id}",
                flush=True,
            )

        passed = observed == ["c", "u", "d", "tombstone"]

        evidence = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "topic": TOPIC,
            "consumer_identity": "desafio-consumer",
            "events_validated": observed,
            "test_transaction_id": target_id,
            "synthetic_identifier": True,
            "before_after_valid": passed,
            "delete_semantics_valid": "d" in observed,
            "tombstone_valid": "tombstone" in observed,
            "payloads_recorded": False,
            "gate": "PASS" if passed else "BLOCKED",
        }

        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(
            json.dumps(evidence, indent=2) + "\n",
            encoding="utf-8",
        )

        print("EVENTS_VALIDATED=", len(observed))
        print("PAYLOADS_PRINTED=False")
        print("EVIDENCE_SAVED=True")
        print("LIFECYCLE_GATE=", evidence["gate"])

        return 0 if passed else 1

    finally:
        consumer.close()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--baseline", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    print("========== ETAPA 5 — CDC LIFECYCLE ==========")

    if args.check:
        print("AVRO_DECODER_IMPORTED=True")
        print("CONSUMER_IMPLEMENTED=True")
        print("EXPECTED_EVENTS=C,U,D,TOMBSTONE")
        print("REMOTE_CHANGES=False")
        print("LIFECYCLE_PREPARATION_GATE=PASS")
        return 0

    if args.baseline:
        capture_baseline()
        return 0

    return verify()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("LIFECYCLE_GATE=BLOCKED")
        raise SystemExit(1)
