# Ingestão CDC — conector, tópicos e ciclo c/u/d (run-20261111)

Saídas reais de 2026-11-12 (UTC), sem payloads, credenciais ou dados pessoais.

## Origem PostgreSQL (`bootstrap_postgres.py apply` + `preflight_postgres_cdc.py`)

```text
WAL_LEVEL_LOGICAL= True
PUBLICATION_TABLES_OK= True
COUNT_PUBLIC_CUSTOMERS= 200
COUNT_PUBLIC_ACCOUNTS= 240
COUNT_PUBLIC_CARDS= 320
COUNT_PUBLIC_MERCHANTS= 60
COUNT_PUBLIC_TRANSACTIONS= 2000
COUNT_CDC_INTERNAL_HEARTBEAT= 1
REPLICA_IDENTITY_FULL_OK= True
CDC_ROLE_LOGIN_REPLICATION=True
CDC_TABLES_SELECT_OK=True
CDC_BUSINESS_WRITE_DENIED=True
CDC_SEPARATE_LOGIN_OK=True
CDC_PREFLIGHT_GATE= PASS
```

## Conector (`apply_cdc_connector.py` + `confluent connect cluster list`)

```text
PLANNED_CHANGES= 1
ONLY_CONNECTOR_CREATE= True
FOUNDATION_MUTATIONS= 0
TERRAFORM_APPLY_SUCCESS= True
CONNECTOR_IN_STATE= True
APPLY_GATE= PASS
      ID      |     Name     | Status  |  Type  | Trace
--------------+--------------+---------+--------+--------
  lcc-6k6w7n2 | payments-cdc | RUNNING | source |
```

## Tópicos (`confluent kafka topic list`)

```text
  __debezium-heartbeat-lcc-6k6w7n2.payments | false | 3 | 1
  payments.cdc_internal.heartbeat           | false | 3 | 1
  payments.public.accounts                  | false | 3 | 1
  payments.public.cards                     | false | 3 | 1
  payments.public.customers                 | false | 3 | 1
  payments.public.merchants                 | false | 3 | 1
  payments.public.transactions              | false | 3 | 1
```

## Snapshot lido pelo consumer de leitura (`src/consumer/audit_cdc.py`)

```text
TOPIC=payments.public.customers AVAILABLE=200 SAMPLED=200
TOPIC=payments.public.accounts AVAILABLE=240 SAMPLED=240
TOPIC=payments.public.cards AVAILABLE=320 SAMPLED=320
TOPIC=payments.public.merchants AVAILABLE=60 SAMPLED=60
TOPIC=payments.public.transactions AVAILABLE=2004 SAMPLED=2004
TOPIC=payments.cdc_internal.heartbeat AVAILABLE=1 SAMPLED=1
CONSUMER_IDENTITY=desafio-consumer
CONSUMER_READ_ONLY=True
CONSUMER_GATE= PASS
```

`transactions` = 2000 do snapshot + 4 eventos do primeiro cenário (c, u, d, tombstone).

## Ciclo INSERT → UPDATE → DELETE (`verify_cdc_lifecycle.py --verify`, Avro decodificado)

```text
VALIDATED_EVENT=C TEST_TRANSACTION_ID=-1777306075833
VALIDATED_EVENT=U TEST_TRANSACTION_ID=-1777306075833
VALIDATED_EVENT=D TEST_TRANSACTION_ID=-1777306075833
VALIDATED_EVENT=TOMBSTONE TEST_TRANSACTION_ID=-1777306075833
EVENTS_VALIDATED= 4
LIFECYCLE_GATE= PASS
```

`op=c`: `before=null`, `after` com a linha; `op=u`: `before` preenchido
(REPLICA IDENTITY FULL) e `after`; `op=d`: `after=null`, seguido do tombstone.
Detalhe por evento em [stage5-cdc-lifecycle.json](stage5-cdc-lifecycle.json).
