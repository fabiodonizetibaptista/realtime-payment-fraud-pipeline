# Validação — Processamento contínuo e inspeção

## Identificação

- Execução: **run-20261111**, 2026-11-12 (UTC), environment `desafio-final`,
  compute pool `payment-fraud-v2` (AWS us-east-1)
- SQL: `sql/fraud_detection/continuous/01_continuous_matches.sql`
- Statement: `etapa11-fraud-pattern-matches` → tabela/tópico `fraud.pattern_matches` (`append`)

## Pré-requisitos aplicados por `lab.py flink-setup --apply`

```text
payment-fraud-setup-accounts-pk: APPLIED          PRIMARY KEY (account_id)
payment-fraud-setup-transactions-pk: APPLIED      PRIMARY KEY (transaction_id)
payment-fraud-setup-transactions-append: APPLIED  changelog.mode: retract → append
FLINK_SETUP_COMPLETED=True
```

Em instalação limpa a Confluent infere `changelog.mode = 'retract'` para
tópicos Debezium; o temporal join exige `append` em `transactions`. O preflight
trata esse valor inferido como sobrescrevível e bloqueia qualquer outro modo.

## Processamento contínuo

```text
STATEMENT_PHASE=PENDING
START_SUBMITTED=True
STATEMENT_PHASE=RUNNING
```

O statement ficou `RUNNING` durante toda a inspeção e foi apagado no fechamento
da janela (`lab.py teardown` agora faz isso automaticamente).

## Consulta independente

- `python -m scripts.fraud_stream inspect` (SELECT separado, `LIMIT 50`):
  `ROWS_OBSERVED=50`, `HAS_CARD_ID_FIELD=True`, `HAS_TIME_FIELDS=True`.
  As linhas incluem correspondências do snapshot (ver
  [fraud-pattern.md](fraud-pattern.md#observação-tempo-do-evento)).
- `python -m scripts.fraud_stream verify-scenario`: correspondência exata do
  cenário — `SCENARIO_ALERT_GATE=PASS`.

## Tratamento de `card_id` nulo

A regra filtra `WHERE t.card_id IS NOT NULL`: transações sem cartão ficam na
origem e fora da detecção. `python -m scripts.fraud_stream inspect-null`:
`ROWS_OBSERVED=0` na execução.

## Gate

- [x] Statement contínuo permanece RUNNING
- [x] Consulta independente retorna registros
- [x] Alerta do cenário observado e rastreável aos 3 IDs
- [x] Tratamento de `card_id` nulo confirmado

**Status: VALIDADO NO FLINK REAL (run-20261111).**
