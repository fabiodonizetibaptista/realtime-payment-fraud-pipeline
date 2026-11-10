# Validação — Processamento contínuo e inspeção

## 1. Identificação

- Commit executado: PENDENTE
- Data da execução: PENDENTE
- Ambiente: PENDENTE

## 2. Processamento contínuo

SQL:
`sql/fraud_detection/continuous/01_continuous_matches.sql`

Statement configurado (identificador técnico preservado por compatibilidade):
`etapa11-fraud-pattern-matches`

- [ ] Statement submetido
- [ ] Estado RUNNING confirmado
- [ ] Processamento permanece ativo durante a inspeção

Estado observado: PENDENTE

## 3. Consulta independente

SQL:
`sql/fraud_detection/continuous/02_inspect_matches.sql`

Comando:
`python3 -m scripts.fraud_stream inspect`

- [ ] SELECT executado separadamente
- [ ] Resultado observado
- [ ] Estado do processamento contínuo preservado

Evidência sanitizada:

- Quantidade de linhas observadas: PENDENTE
- Campo card_id presente: PENDENTE
- Campos first_rowtime e last_rowtime presentes: PENDENTE

Não registrar IDs reais de cartões ou dados financeiros.

## 4. Tratamento de card_id nulo

A regra de detecção utiliza:

`WHERE t.card_id IS NOT NULL`

Consequentemente:

- Registros com cartão identificado participam da detecção.
- Registros com card_id nulo são excluídos da detecção.
- Esses registros continuam disponíveis na origem para inspeção.

SQL de inspeção:
`sql/fraud_detection/continuous/03_inspect_null_cards.sql`

- [ ] Inspeção executada
- [ ] Quantidade de registros sem cartão observada

## 5. Interpretação operacional

A ausência imediata de linhas não significa necessariamente falha.

Distinguir:

1. Statement rejeitado ou FAILED: investigar compilação/execução.
2. Statement RUNNING sem resultados: verificar chegada de eventos e condições da regra.
3. SELECT sem linhas: verificar existência de correspondências e disponibilidade dos dados.

Uma consulta de inspeção deve ser independente do statement contínuo.

## 6. Gate de conclusão

- [ ] Statement contínuo permanece RUNNING
- [ ] Consulta independente retorna registros
- [ ] Tratamento de card_id nulo confirmado

**Status: IMPLEMENTAÇÃO PREPARADA; EXECUÇÃO CONTÍNUA NO FLINK NÃO COMPROVADA.**
