"""Validador Avro CDC — Etapa 5.

--check: valida dependencias e configuracao, sem acessar mensagens.
As funcoes de decodificacao serao usadas no teste integrado.
Nunca imprime payloads, credenciais ou dados pessoais.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF_DIR = ROOT / "infra" / "terraform"
sys.path.insert(0, str(ROOT / "src" / "consumer"))

from audit_cdc import kafka_credentials, resources, terraform_state


def schema_registry_credentials(state):
    clusters = [
        attributes
        for _, attributes in resources(
            state, "confluent_schema_registry_cluster"
        )
        if attributes.get("rest_endpoint")
    ]

    keys = [
        attributes
        for name, attributes in resources(state, "confluent_api_key")
        if ("schema" in name.lower() or "registry" in name.lower())
        and attributes.get("id")
        and attributes.get("secret")
    ]

    if len(clusters) != 1:
        raise RuntimeError("SCHEMA_REGISTRY_ENDPOINT_NOT_UNIQUE")

    if len(keys) != 1:
        raise RuntimeError("SCHEMA_REGISTRY_API_KEY_NOT_UNIQUE")

    return (
        clusters[0]["rest_endpoint"],
        keys[0]["id"],
        keys[0]["secret"],
    )


def create_deserializers(state):
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer

    endpoint, key, secret = schema_registry_credentials(state)

    client = SchemaRegistryClient({
        "url": endpoint,
        "basic.auth.user.info": f"{key}:{secret}",
    })

    return AvroDeserializer(client), AvroDeserializer(client)


def decode_message(message, key_decoder, value_decoder):
    from confluent_kafka.serialization import (
        MessageField,
        SerializationContext,
    )

    key_context = SerializationContext(
        message.topic(), MessageField.KEY
    )
    value_context = SerializationContext(
        message.topic(), MessageField.VALUE
    )

    key = (
        key_decoder(message.key(), key_context)
        if message.key() is not None
        else None
    )

    value = (
        value_decoder(message.value(), value_context)
        if message.value() is not None
        else None
    )

    # Algumas configuracoes apresentam um wrapper payload.
    envelope = value

    if isinstance(envelope, dict) and isinstance(
        envelope.get("payload"), dict
    ):
        envelope = envelope["payload"]

    if value is None:
        operation = "tombstone"
        before = None
        after = None
    elif isinstance(envelope, dict):
        operation = envelope.get("op")
        before = envelope.get("before")
        after = envelope.get("after")
    else:
        raise RuntimeError("UNEXPECTED_AVRO_ENVELOPE")

    return {
        "key": key,
        "operation": operation,
        "before": before,
        "after": after,
        "tombstone": value is None,
    }


def check():
    print("========== ETAPA 5 — AVRO PREFLIGHT ==========")

    try:
        from confluent_kafka.schema_registry.avro import AvroDeserializer
        from confluent_kafka.serialization import SerializationContext

        dependencies = bool(
            AvroDeserializer and SerializationContext
        )
    except ImportError:
        dependencies = False

    print("AVRO_DEPENDENCIES_AVAILABLE=", dependencies)

    if not dependencies:
        print("AVRO_GATE=BLOCKED")
        return 1

    state = terraform_state()

    try:
        bootstrap, consumer_key, consumer_secret = kafka_credentials(
            state
        )
        consumer_ready = all([
            bootstrap, consumer_key, consumer_secret
        ])
    except RuntimeError:
        consumer_ready = False

    try:
        endpoint, registry_key, registry_secret = (
            schema_registry_credentials(state)
        )
        registry_ready = all([
            endpoint, registry_key, registry_secret
        ])
    except RuntimeError:
        registry_ready = False

    print("CONSUMER_CREDENTIALS_AVAILABLE=", bool(consumer_ready))
    print("SCHEMA_REGISTRY_CREDENTIALS_AVAILABLE=", bool(registry_ready))

    hcl = (TF_DIR / "cdc-connector.tf").read_text(
        encoding="utf-8"
    )

    def option_is_true(name):
        pattern = (
            r'["\']' + re.escape(name) +
            r'["\']\s*=\s*["\']true["\']'
        )
        return bool(re.search(pattern, hcl, flags=re.IGNORECASE))

    # A existencia dessas opcoes no HCL e distinta da capacidade
    # teorica do Debezium; o teste exige semantica explicita.
    tombstones = option_is_true("tombstones.on.delete")
    envelope = (
        not option_is_true("after.state.only")
        and not bool(re.search(
            r'["\']after\.state\.only["\']\s*=\s*["\']true["\']',
            hcl,
            flags=re.IGNORECASE,
        ))
    )

    print("TOMBSTONES_EXPLICITLY_ENABLED=", tombstones)
    print("AFTER_STATE_ONLY_NOT_TRUE=", envelope)
    print("REMOTE_CHANGES=False")
    print("SECRETS_PRINTED=False")

    # O gate completo exige tombstone explicitamente habilitado.
    passed = all([
        consumer_ready,
        registry_ready,
        tombstones,
        envelope,
    ])

    print("AVRO_PREFLIGHT_GATE=", "PASS" if passed else "BLOCKED")
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()

    try:
        raise SystemExit(check())
    except Exception as error:
        print("ERROR_TYPE=", type(error).__name__)
        if isinstance(error, RuntimeError):
            print("ERROR_CODE=", str(error))
        print("AVRO_PREFLIGHT_GATE=BLOCKED")
        raise SystemExit(1)
