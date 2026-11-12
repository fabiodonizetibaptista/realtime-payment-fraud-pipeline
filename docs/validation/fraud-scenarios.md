# Validação — Cenários sintéticos e alertas

## Identificação

- Execução: **run-20261111**, 2026-11-12 (UTC), branch `chore/final-delivery`
- Script: `scripts/fraud_scenarios.py`
- Evidência: [`fraud-scenario-alert.json`](../../evidencias/runs/run-20261111/flink/fraud-scenario-alert.json)

## Execução

```bash
python -m scripts.fraud_scenarios execute --confirm-execute
```

Insere, em transações independentes no Postgres, 1 transação legítima num
cartão e 3 transações (`amount > 0`) noutro cartão, reaproveitando contas e
lojistas existentes e IDs sintéticos negativos (fora do seed). O manifesto
privado `.local/etapa12-scenarios.json` guarda só esses IDs e não é versionado.
Ao final, o script consulta o Flink a cada 30 s (até 10 min) e grava a
evidência no primeiro PASS.

```text
LEGITIMATE_COMMITTED=True
FRAUD_1_COMMITTED=True
FRAUD_2_COMMITTED=True
FRAUD_3_COMMITTED=True
SCENARIO_EXECUTION=COMPLETED
FRAUD_INTERVAL_UNDER_60S=True
```

## Esperado versus observado

| Cenário | Esperado | Observado | Status |
|---|---|---|---|
| 1 transação legítima em cartão separado | Nenhum alerta que a contenha | `LEGITIMATE_IN_ANY_MATCH=False` | PASS |
| 3 transações no mesmo cartão em ≤ 60 s | 1 correspondência | `FRAUD_MATCHES_FOR_SCENARIO=1` | PASS |
| Rastreabilidade | Os 3 IDs na correspondência, em ordem | `FRAUD_SEQUENCE_MATCHED=True` | PASS |
| Temporalidade | Alerta após o avanço do watermark | Observado na 1ª consulta após o cenário | PASS |

A verificação usa os IDs sintéticos do cenário, não a quantidade global de
alertas — o snapshot também gera correspondências
([fraud-pattern.md](fraud-pattern.md#observação-tempo-do-evento)).

## Destino do alerta

Tópico/tabela `fraud.pattern_matches` (`changelog.mode = 'append'`), campos
`card_id`, `first_transaction_id`, `middle_transaction_id`,
`last_transaction_id`, `transaction_count`, `first_rowtime`, `last_rowtime`.
Contrato em [alert-contract.md](../alert-contract.md).

**STATUS: VALIDADO NO FLINK REAL (run-20261111).**
