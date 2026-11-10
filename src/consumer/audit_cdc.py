"""Auditoria read-only dos seis topicos CDC da V2.

Credenciais recuperadas em memoria do Terraform State.
Nao imprime payloads, credenciais ou dados pessoais.
Nao realiza commit de offsets ou altera recursos remotos.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF_DIR = ROOT / "infra" / "terraform"

TOPICS = (
    "payments.public.customers",
    "payments.public.accounts",
    "payments.public.cards",
    "payments.public.merchants",
    "payments.public.transactions",
    "payments.cdc_internal.heartbeat",
)


def terraform_state():
    result = subprocess.run(
        ["terraform", "state", "pull"],
        cwd=TF_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("TERRAFORM_STATE_UNAVAILABLE")
    return json.loads(result.stdout)


def resources(state, resource_type):
    for resource in state.get("resources", []):
        if resource.get("type") != resource_type:
            continue
        for instance in resource.get("instances", []):
            yield (
                resource.get("name", ""),
                instance.get("attributes") or {},
            )


def kafka_credentials(state):
    matches = [
        attrs
        for name, attrs in resources(state, "confluent_api_key")
        if "consumer" in name.lower()
        and attrs.get("id")
        and attrs.get("secret")
    ]

    if len(matches) != 1:
        raise RuntimeError("CONSUMER_API_KEY_NOT_UNIQUE")

    clusters = list(resources(state, "confluent_kafka_cluster"))

    if len(clusters) != 1:
        raise RuntimeError("KAFKA_CLUSTER_NOT_UNIQUE")

    bootstrap = clusters[0][1].get("bootstrap_endpoint", "")
    bootstrap = bootstrap.removeprefix("SASL_SSL://")

    if not bootstrap:
        raise RuntimeError("KAFKA_BOOTSTRAP_MISSING")

    return bootstrap, matches[0]["id"], matches[0]["secret"]


def audit():
    try:
        from confluent_kafka import Consumer, TopicPartition
    except ImportError:
        raise RuntimeError("CONFLUENT_KAFKA_NOT_INSTALLED")

    state = terraform_state()
    bootstrap, key, secret = kafka_credentials(state)

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "PLAIN",
        "sasl.username": key,
        "sasl.password": secret,
        "group.id": "desafio-cdc-audit-v2",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
        "allow.auto.create.topics": False,
        "socket.timeout.ms": 10000,
    })

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "consumer_identity": "desafio-consumer",
        "read_only": True,
        "topics": {},
    }

    print("========== ETAPA 5 — CONSUMIDOR CDC ==========", flush=True)
    print("TOPICS_EXPECTED=", len(TOPICS), flush=True)

    try:
        # Consulta individual para diagnosticar autorizacao ou ausencia.
        # A consulta geral pode omitir topicos sem permissao de descricao.
        print("========== DIAGNOSTICO DE TOPICO ==========", flush=True)

        probe = consumer.list_topics(
            topic=TOPICS[0],
            timeout=15,
        )

        item = probe.topics.get(TOPICS[0])

        if item is None:
            print("DIRECT_TOPIC_METADATA=MISSING", flush=True)
        elif item.error is not None:
            print(
                "DIRECT_TOPIC_ERROR_CODE=", item.error.code(),
                flush=True,
            )
            print(
                "DIRECT_TOPIC_ERROR_NAME=", item.error.name(),
                flush=True,
            )
        else:
            print("DIRECT_TOPIC_METADATA=OK", flush=True)
            print(
                "DIRECT_TOPIC_PARTITIONS=",
                len(item.partitions),
                flush=True,
            )

        metadata = consumer.list_topics(timeout=15)

        partitions = []
        for topic in TOPICS:
            item = metadata.topics.get(topic)

            if item is None:
                print(f"TOPIC={topic} METADATA=MISSING", flush=True)
                raise RuntimeError("CDC_TOPIC_METADATA_UNAVAILABLE")

            if item.error is not None:
                print(
                    f"TOPIC={topic} "
                    f"ERROR_CODE={item.error.code()} "
                    f"ERROR_NAME={item.error.name()}",
                    flush=True,
                )
                raise RuntimeError("CDC_TOPIC_METADATA_UNAVAILABLE")

            print(f"TOPIC={topic} METADATA=OK", flush=True)

            topic_partitions = [
                TopicPartition(topic, partition_id)
                for partition_id in sorted(item.partitions)
            ]

            if not topic_partitions:
                raise RuntimeError("CDC_TOPIC_WITHOUT_PARTITIONS")

            partitions.extend(topic_partitions)

        offsets = {}

        for partition in partitions:
            low, high = consumer.get_watermark_offsets(
                partition, timeout=10, cached=False
            )

            if low < 0 or high < low:
                raise RuntimeError("INVALID_KAFKA_OFFSETS")

            offsets[(partition.topic, partition.partition)] = {
                "low": low,
                "high": high,
            }

            # Leitura direta, sem associacao a grupo nem commits.
            partition.offset = low

        consumer.assign(partitions)

        counts = {topic: 0 for topic in TOPICS}
        target = sum(
            value["high"] - value["low"]
            for value in offsets.values()
        )

        # Limite intencional: auditoria pequena, nao exportacao de dados.
        max_messages = min(target, 3000)
        consumed = 0
        deadline = time.monotonic() + 30

        while consumed < max_messages and time.monotonic() < deadline:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                # Particao no fim do log nao e erro de auditoria.
                from confluent_kafka import KafkaError

                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError("KAFKA_CONSUMPTION_ERROR")

            counts[message.topic()] += 1
            consumed += 1

        for topic in TOPICS:
            topic_offsets = [
                value
                for (name, _), value in offsets.items()
                if name == topic
            ]

            report["topics"][topic] = {
                "partitions": len(topic_offsets),
                "available_offsets": sum(
                    value["high"] - value["low"]
                    for value in topic_offsets
                ),
                "messages_sampled": counts[topic],
            }

            print(
                f"TOPIC={topic} "
                f"AVAILABLE={report['topics'][topic]['available_offsets']} "
                f"SAMPLED={counts[topic]}",
                flush=True,
            )

        report["topics_available"] = len(report["topics"])
        report["messages_sampled_total"] = consumed
        report["gate"] = (
            "PASS"
            if len(report["topics"]) == len(TOPICS)
            and all(
                item["messages_sampled"] > 0
                for item in report["topics"].values()
            )
            else "PARTIAL"
        )

        output = ROOT / "evidencias/cdc/stage5-cdc-consumer.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        print("CONSUMER_IDENTITY=desafio-consumer")
        print("CONSUMER_READ_ONLY=True")
        print("TOPICS_AVAILABLE=", report["topics_available"])
        print("MESSAGES_SAMPLED_TOTAL=", consumed)
        print("EVIDENCE_SAVED=True")
        print("PAYLOADS_PRINTED=False")
        print("SECRETS_PRINTED=False")
        print("CONSUMER_GATE=", report["gate"])

    finally:
        consumer.close()


if __name__ == "__main__":
    try:
        audit()
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("CONSUMER_GATE=BLOCKED")
        raise SystemExit(1)
