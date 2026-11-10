# Validação e matriz de rastreabilidade

## Critérios de classificação

- **Implementado:** artefatos de código declarados no repositório.
- **Teste local:** execução de teste automatizado sobre lógica ou contrato; não comprova serviços externos.
- **Comprovado em nuvem:** evidência de execução real vinculada a ambiente e janela verificáveis.
- **Não comprovado:** pendência explícita; não assumir êxito pela existência do script.

| Requisito | Implementação | Verificação esperada | Evidência disponível / limitação |
|---|---|---|---|
| Kafka e identidades | `infra/terraform/foundation.tf`, `kafka-acls.tf` | Plano, recursos e ACLs remotos | Inventário histórico em `evidencias/infrastructure/`; revisar contexto |
| Avro e compatibilidade | `schemas/registry/`, scripts de schema | Subjects e evolução BACKWARD | Registros históricos em `evidencias/schemas/` |
| PostgreSQL e grants | `database/`, `aiven-postgres.tf` | WAL, tabelas, permissões e contagem de dados | `evidencias/database/`, `evidencias/security/` |
| CDC 5 tabelas | `cdc-connector.tf`, scripts de cenário | INSERT/UPDATE/DELETE, tombstone, entrega Kafka | `evidencias/cdc/`; comparar IDs de eventos |
| Temporal Join | `sql/enrichment/`, `scripts/flink_setup.py` | PK, changelog e resultado enriquecido real | `evidencias/flink/`, `docs/validation/flink-table-metadata.md` |
| Regra 3/60s | `sql/fraud_detection/pattern/` | Eventos do mesmo cartão dentro de 60s | Testes locais em `docs/validation/fraud-pattern.md`; Flink real não comprovado nesses documentos |
| Alerta contínuo | `sql/fraud_detection/continuous/`, `scripts/fraud_stream.py` | Statement RUNNING e linha de correspondência | `docs/validation/fraud-stream.md`: pendência operacional explícita |
| Cenário sintético | `scripts/fraud_scenarios.py` | Cenário legítimo não gera alerta; fraudulento gera correspondência | `docs/validation/fraud-scenarios.md`: sem resultado real comprovado |
| Custos e teardown | `collect_operations_evidence.py`, `lab.py` | Extrato de período e ausência de recursos indesejados após teardown | `evidencias/billing/` e `docs/validation/operations.md`; revisão manual necessária |

## Testes e revisão de segurança

Executar `python lab.py test` para regressões locais. O número total de testes depende da revisão do repositório: não fixar uma contagem no contrato. `git diff --check` e `git status -sb` validam integridade de alterações e estado do checkout, mas não substituem testes ou execução integrada.

Antes de publicar, conferir que artefatos de evidência não contêm credenciais, dados financeiros reais, nomes de conta ou outros identificadores que não devem ser públicos. Os JSONs históricos devem ser revisados manualmente; ausência de algumas chaves sensíveis não garante anonimização completa.

## Aceite para alegar reprodução integral

Somente afirmar *ponta a ponta validado* quando houver, na mesma janela controlada: provisionamento confirmado, origem PostgreSQL válida, CDC entregando eventos Kafka, contratos aceitos, statement Flink executando, correspondência no destino ligada aos três eventos sintéticos e encerramento/custos registrados. Até lá, classificar como implementado e validado localmente, com evidências históricas parciais.
