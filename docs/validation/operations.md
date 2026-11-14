# Evidências — Observabilidade, segurança e custos

## Execução run-20261111 (2026-11-12)

Coletado por `collect_operations_evidence.py` (escopo explícito) e
`collect_metrics_evidence.py`; arquivos em
[`evidencias/runs/run-20261111/`](../../evidencias/runs/run-20261111/).

| Item | Resultado |
|---|---|
| Cluster | `desafio-basic`, BASIC, UP (data de criação não retornada pela CLI; apply da fundação ≈ 00:40 UTC) |
| Compute pool | `payment-fraud-v2`, PROVISIONED, `max_cfu=10` |
| Identidades | 7 do projeto (+1 da conta, fora do escopo); 14 ACLs — CREATE 2, DESCRIBE 2, DESCRIBE_CONFIGS 1, READ 5, WRITE 4 |
| Metrics API | `received_bytes`: 43 pontos/min, pico 180.626 B/min, total 233.839 B; lag por grupo sem série |
| Billing | Vazio na CLI no dia da janela; **final pela fatura do console (2026-11-13): US$ 1,317** — conector 1,000, Flink 0,182, Kafka 0,135 — coberto pelo crédito `FREETRIAL400` |
| Teardown | State vazio; sem environment, service accounts ou conector do projeto |

O conteúdo abaixo é a inspeção **anterior** (09/11/2026), mantida como histórico.

## 1. Contexto

- Ambiente inspecionado: desafio-final
- Provedor: Confluent Cloud / AWS
- Região: us-east-1
- Data da inspeção: 09/11/2026
- Origem: consultas reais realizadas pela Confluent CLI
- Tipo de evidência: resumo sanitizado dos resultados observados

## 2. Inventário de recursos

### Cluster Kafka

| Propriedade | Resultado |
|---|---|
| Nome | desafio-basic |
| Tipo | BASIC |
| Estado observado | UP |
| Região | aws / us-east-1 |
| Tópicos | 8 |
| Proteção contra exclusão | Desativada |
| Data de criação | Não retornada pela CLI |

### Compute Pool

| Propriedade | Resultado |
|---|---|
| Nome | payment-fraud-v2 |
| Status | PROVISIONED |
| Capacidade máxima | 10 CFUs |
| CFUs em uso no momento da consulta | 0 |
| Região | aws / us-east-1 |

### CDC

Foram identificados lançamentos históricos de uso
de conectores CDC no billing.

A existência de cobranças históricas não comprova
que o conector esteja ativo no momento da inspeção.

## 3. Identidades e segurança

Service Accounts encontradas: 9

Categorias identificadas:

- Flink
- CDC PostgreSQL / Debezium
- Schema Registry
- Administração de ACLs
- Producer Kafka
- Consumer Kafka

ACLs Kafka encontradas: 14

Permissões observadas:

- READ em tópicos e grupos
- WRITE em tópicos e IDs transacionais
- CREATE em tópicos
- DESCRIBE e DESCRIBE_CONFIGS

A consulta RBAC do usuário autenticado retornou
'None found' para o escopo consultado.

Isso não comprova inexistência de permissões
RBAC atribuídas a outras identidades.

Não foi realizada alteração de permissões.

## 4. Billing e utilização

Período consultado: 01/11/2026 a 09/11/2026.

Valores em USD, anteriores aos créditos promocionais:

| Serviço | Valor observado |
|---|---:|
| Connect / CDC | 1.0000 |
| Flink | 0.1820 |
| Kafka Network Read | 0.0008 |
| Total bruto | 1.1828 |

Créditos promocionais exibidos: -1.1829 USD.

Diferenças de arredondamento podem ocorrer entre
lançamentos individuais e créditos agregados.

O billing consultado contém lançamentos de mais
de um ambiente da organização Confluent.

Portanto, o total bruto não representa exclusivamente
o custo do cluster desafio-basic.

Os registros também não comprovam o custo atual
da próxima execução integral.

## 5. Procedimentos de consulta

Comandos utilizados:

```bash
confluent environment list
confluent kafka cluster list -o json
confluent kafka cluster describe
confluent iam service-account list
confluent kafka acl list
confluent flink compute-pool list
confluent billing cost list --start-date 2026-11-01 --end-date 2026-11-10
```

Essas consultas são somente leitura.

## 6. Automação e reprodutibilidade

Scripts existentes:

- scripts/observability_plan.py
- scripts/collect_operations_evidence.py

Estado atual:
- [x] Comandos de consulta identificados
- [x] Consultas manuais executadas
- [x] Evidências reais consolidadas
- [ ] Coletor integral automatizado e validado
- [ ] Exportação automatizada de billing comprovada

O coletor deve resolver recursos dinamicamente,
sanitizar as respostas e preservar a separação
entre consumo da organização e do desafio.

## 7. Gate

- [x] Recursos identificados
- [x] Identidades e ACLs inspecionadas
- [x] Custos observados
- [x] Relatório de evidências preparado
- [ ] Automação integral validada

STATUS: EVIDENCIAS CONSOLIDADAS.
