# Fundação — identidades e ACLs (run-20261111)

Saídas reais da execução de 2026-11-12 (UTC). Os IDs pertencem a recursos já
destruídos; nenhuma chave ou segredo aparece aqui.

## Service accounts criadas pelo Terraform (`terraform output -json service_account_ids`)

```json
{"cdc":"sa-3n6dx7m","consumer":"sa-7pmd25j","iac_admin":"sa-z3wkd6z","producer":"sa-196ypn3","schema_registry":"sa-nyp6jk3"}
```

Identidade do Flink: `sa-r2w6pk7` (`payment-fraud-flink-v2`). Identidade de métricas:
`sa-j87rx8p` (`desafio-metrics`, papel `MetricsViewer`, role binding `rb-QdMOZE`).

## `confluent kafka acl list --environment env-qqm0qp --cluster lkc-xqw7xj1`

```text
     Principal    | Permission |    Operation     |  Resource Type   |      Resource Name       | Pattern Type
------------------+------------+------------------+------------------+--------------------------+---------------
  User:sa-196ypn3 | ALLOW      | WRITE            | TOPIC            | desafio-                 | PREFIXED
  User:sa-3n6dx7m | ALLOW      | CREATE           | TOPIC            | __debezium-heartbeat-    | PREFIXED
  User:sa-3n6dx7m | ALLOW      | CREATE           | TOPIC            | payments                 | PREFIXED
  User:sa-3n6dx7m | ALLOW      | DESCRIBE         | CLUSTER          | kafka-cluster            | LITERAL
  User:sa-3n6dx7m | ALLOW      | DESCRIBE         | TOPIC            | __debezium-heartbeat-    | PREFIXED
  User:sa-3n6dx7m | ALLOW      | DESCRIBE_CONFIGS | CLUSTER          | kafka-cluster            | LITERAL
  User:sa-3n6dx7m | ALLOW      | WRITE            | TOPIC            | __debezium-heartbeat-    | PREFIXED
  User:sa-3n6dx7m | ALLOW      | WRITE            | TOPIC            | payments                 | PREFIXED
  User:sa-7pmd25j | ALLOW      | READ             | GROUP            | desafio-                 | PREFIXED
  User:sa-7pmd25j | ALLOW      | READ             | TOPIC            | desafio-                 | PREFIXED
  User:sa-7pmd25j | ALLOW      | READ             | TOPIC            | payments.                | PREFIXED
  User:sa-r2w6pk7 | ALLOW      | READ             | TOPIC            | payments.public.accounts | LITERAL
  User:sa-r2w6pk7 | ALLOW      | READ             | TRANSACTIONAL_ID | _confluent-flink_        | PREFIXED
  User:sa-r2w6pk7 | ALLOW      | WRITE            | TRANSACTIONAL_ID | _confluent-flink_        | PREFIXED
```

## Gate das ACLs (`scripts/plan_cdc_acls.py` + `apply_cdc_acls.py`)

```text
EXPECTED_MISSING_ACLS= 11
PLANNED_CHANGES= 11
ONLY_EXPECTED_ACL_CREATES= True
CONNECTOR_REMAINS_OFF=True
ACL_PLAN_GATE=PASS
ACL_RESOURCES_IN_STATE= True
ACL_APPLY_GATE=PASS
```
