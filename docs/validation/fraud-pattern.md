# Validação — Detecção de padrão com MATCH_RECOGNIZE

## Identificação

- SQL de referência: `sql/fraud_detection/pattern/01_match_recognize.sql`
- SQL executado no Flink (contínuo): `sql/fraud_detection/continuous/01_continuous_matches.sql`
- Execução real: **run-20261111**, 2026-11-12 (UTC), branch `chore/final-delivery`
- Evidência: [`evidencias/runs/run-20261111/flink/fraud-scenario-alert.json`](../../evidencias/runs/run-20261111/flink/fraud-scenario-alert.json)

## Regra

`MATCH_RECOGNIZE` com `PARTITION BY card_id`, `ORDER BY transaction_rowtime`,
`PATTERN (T{3})`, `WITHIN INTERVAL '60' SECOND`, `DEFINE T AS T.amount > 0` e
`AFTER MATCH SKIP PAST LAST ROW`, sobre transações enriquecidas pelo temporal
join e com `card_id IS NOT NULL`.

## Resultado no Flink real

| Cenário | Esperado | Resultado (run-20261111) |
|---|---|---|
| 3 transações positivas no mesmo cartão em < 60 s | 1 correspondência com os 3 IDs, em ordem | **PASS** — `FRAUD_SEQUENCE_MATCHED=True`, `FRAUD_MATCHES_FOR_SCENARIO=1` |
| 1 transação legítima em outro cartão | Nenhuma correspondência que a contenha | **PASS** — `LEGITIMATE_IN_ANY_MATCH=False` |
| Registros sem cartão | Fora da detecção | **PASS** — `inspect-null`: `ROWS_OBSERVED=0` |

A verificação (`python -m scripts.fraud_stream verify-scenario`, chamada pelo
`fraud_scenarios execute`) consulta somente as correspondências que contêm os
IDs sintéticos do cenário e grava apenas booleanos.

## Cenários só testados localmente

Avaliador Python de referência (`tests/`), **não executados no Flink**:

| Cenário | Esperado | Teste local |
|---|---|---|
| 3 transações em 45 s | Correspondência | PASS |
| 3 transações em exatamente 60 s | Correspondência | PASS |
| 3 transações em 61 s | Sem correspondência | PASS |
| Cartões diferentes | Sem mistura | PASS |
| `amount = 0` ou negativo | Não satisfaz | PASS |
| 6 elegíveis | 2 grupos sem reutilização | PASS |
| 4 elegíveis | 1 grupo de 3 | PASS |

## Observação: tempo do evento

A regra ordena por `$rowtime`, o horário em que o evento chegou ao Kafka, e não
por `event_time`. No snapshot inicial os 2000 registros chegam quase juntos, então
**todo cartão do seed com 3 ou mais transações gera correspondência** — por isso
`fraud_stream inspect` (com `LIMIT 50`) mostra linhas antes mesmo do cenário e
não serve como prova. A prova é a verificação dirigida acima. Para uso real, a
regra deveria ordenar por `event_time` com watermark próprio, ou ignorar o
snapshot (ver [alert-contract.md](../alert-contract.md)).

**Status: VALIDADO NO FLINK REAL para o cenário positivo e o negativo; demais
cenários de borda validados apenas localmente.**
