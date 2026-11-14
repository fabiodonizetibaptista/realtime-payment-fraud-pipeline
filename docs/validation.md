# Validação e matriz de rastreabilidade

## Critérios de classificação

- **Implementado:** artefatos de código declarados no repositório.
- **Teste local:** execução de teste automatizado sobre lógica ou contrato; não comprova serviços externos.
- **Comprovado em nuvem:** evidência de execução real vinculada a ambiente e janela verificáveis.
- **Não comprovado:** pendência explícita; não assumir êxito pela existência do script.

Execução de referência: **run-20261111** (2026-11-12, do zero, em conta vazia), reproduzida seguindo apenas a documentação em **run-20261112** (Codespace limpo) com os mesmos resultados.
Evidências em [`evidencias/runs/run-20261111/`](../evidencias/runs/run-20261111/).

| Requisito | Implementação | Verificação | Situação |
|---|---|---|---|
| Kafka e identidades | `foundation.tf`, `*-acls.tf`, `metrics-identity.tf` | 14 ACLs, uma identidade por papel | **Comprovado em nuvem** — [foundation/](../evidencias/runs/run-20261111/foundation/identities-and-acls.md) |
| Avro e compatibilidade | Schema Registry, `*_schema_compatibility_*` | BACKWARD aceita opcional com default e rejeita obrigatório sem default | **Comprovado em nuvem** — [schemas/](../evidencias/runs/run-20261111/schemas/) |
| PostgreSQL e grants | `database/`, `aiven-postgres.tf`, `configure_cdc_user.py` | WAL lógico, publicação, contagens 200/240/320/60/2000, escrita de negócio negada ao `cdc_user` | **Comprovado em nuvem** — [cdc/](../evidencias/runs/run-20261111/cdc/connector-topics-and-scenario.md) |
| CDC 5 tabelas | `cdc-connector.tf`, `cdc_test_scenario.py` | c/u/d + tombstone decodificados do Avro para o mesmo ID | **Comprovado em nuvem** — `stage5-cdc-lifecycle.json` |
| Temporal join | `sql/enrichment/`, `flink_setup.py` | 2004 linhas, 2002 IDs, sem perda nem duplicação | **Comprovado em nuvem** — `flink/02_statement_execution.json` |
| Regra 3/60 s | `sql/fraud_detection/` | Cenário positivo gera 1 alerta; legítimo não | **Comprovado em nuvem** (bordas só locais) — [fraud-pattern.md](validation/fraud-pattern.md) |
| Alerta contínuo | `fraud_stream.py` | Statement RUNNING e alerta rastreável aos 3 IDs | **Comprovado em nuvem** — [fraud-stream.md](validation/fraud-stream.md) |
| Observabilidade | `collect_metrics_evidence.py` | Série `received_bytes` da Metrics API | **Comprovado** (bytes); lag por grupo sem série — limitação documentada |
| Custos | Fatura do console + `billing cost list` | Custo por recurso e por execução | **Comprovado** — US$ 1,317 (run-20261111) e US$ 1,289 (run-20261112), cobertos pelo crédito; [billing-final.json](../evidencias/runs/run-20261111/operations/billing-final.json) |
| Teardown | `lab.py teardown` | Listas vazias e State vazio | **Comprovado**, após correção da ordem de destruição — [teardown/](../evidencias/runs/run-20261111/teardown/closure-and-teardown.md) |

## Testes e revisão de segurança

Executar `python lab.py test` para regressões locais. O número total de testes depende da revisão do repositório: não fixar uma contagem no contrato. `git diff --check` e `git status -sb` validam integridade de alterações e estado do checkout, mas não substituem testes ou execução integrada.

Antes de publicar, conferir que artefatos de evidência não contêm credenciais, dados financeiros reais, nomes de conta ou outros identificadores que não devem ser públicos. Os JSONs históricos devem ser revisados manualmente; ausência de algumas chaves sensíveis não garante anonimização completa.

## Aceite para alegar reprodução integral

Critério: na mesma janela controlada, provisionamento confirmado, origem PostgreSQL válida, CDC entregando eventos Kafka, contratos aceitos, statement Flink executando, correspondência no destino ligada aos três eventos sintéticos e encerramento/custos registrados.

A run-20261111 atendeu a todos os itens; o custo final veio da fatura do console no dia seguinte. Ela foi conduzida com correções durante a execução; a reprodução guiada **apenas** pela documentação é o gate seguinte ([backlog](audits/reproduction-readiness-backlog.md)).
