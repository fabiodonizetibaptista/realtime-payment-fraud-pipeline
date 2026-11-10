# Validação — Detecção de padrão com MATCH_RECOGNIZE

## 1. Identificação

- SQL: sql/fraud_detection/pattern/01_match_recognize.sql
- Execução: PENDENTE — validação remota não registrada
- Commit executado: PENDENTE
- Data da execução: PENDENTE

## 2. SQL integral executado

Fonte versionada:
`sql/fraud_detection/pattern/01_match_recognize.sql`

- [ ] Arquivo submetido integralmente ao Flink
- [ ] SQL executado corresponde ao commit registrado
- [ ] Identificadores de catálogo/database resolvidos

## 3. Estado do statement

- Statement ID: PENDENTE
- Estado retornado pelo Flink: PENDENTE
- Consulta aceita: PENDENTE
- Evidência técnica: PENDENTE

## 4. Resultados observados

Registrar somente identificadores sintéticos ou anonimizados.

| card_id | first_rowtime | last_rowtime | transaction_count | Resultado |
|---|---|---|---|---|
| PENDENTE | PENDENTE | PENDENTE | PENDENTE | PENDENTE |

## 5. Cenários de validação

| Cenário | Resultado esperado | Teste local | Flink real |
|---|---|---|---|
| 3 transações em 45 segundos | Correspondência | PASS | PENDENTE |
| 3 transações em exatamente 60 segundos | Correspondência | PASS | PENDENTE |
| 3 transações em 61 segundos | Sem correspondência | PASS | PENDENTE |
| Transações de cartões diferentes | Sem mistura entre cartões | PASS | PENDENTE |
| Transação com amount = 0 | Não satisfaz o padrão | PASS | PENDENTE |
| Transação com amount negativo | Não satisfaz o padrão | PASS | PENDENTE |
| 6 transações elegíveis | 2 grupos sem reutilização | PASS | PENDENTE |
| 4 transações elegíveis | 1 grupo de 3 | PASS | PENDENTE |

Os testes locais utilizam um avaliador Python de referência.
PASS local não constitui evidência de execução no Flink.

## 6. Gate de conclusão

- [ ] Statement aceito pelo Flink
- [ ] Particionamento e ordenação confirmados
- [ ] Janela de 60 segundos confirmada
- [ ] Condição amount > 0 confirmada
- [ ] Correspondência observada
- [ ] Cenários positivos e negativos documentados

**Status final: IMPLEMENTAÇÃO E TESTES LOCAIS CONCLUÍDOS; VALIDAÇÃO REAL NO FLINK NÃO COMPROVADA.**
