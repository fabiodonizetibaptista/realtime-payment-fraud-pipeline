# Contrato de alertas e watermark

## Destino

Tabela de resultados:
`fraud.pattern_matches`

Definida em:
`sql/fraud_detection/continuous/01_continuous_matches.sql`

Consulta de inspeção:
`sql/fraud_detection/continuous/02_inspect_matches.sql`

A tabela representa correspondências identificadas pela regra
de fraude. Ela não registra todas as transações individuais.

## Nomenclatura do destino

O exemplo de entrega do desafio utiliza o nome
`desafio.fraud.detected` para o destino dos alertas.

Esta implementação utiliza `fraud.pattern_matches`,
definido pelo CTAS em
`sql/fraud_detection/continuous/01_continuous_matches.sql`.

A diferença é de nomenclatura: o destino implementado
representa as correspondências identificadas pela regra
de três transações positivas do mesmo cartão em até
60 segundos.

A declaração SQL define o destino pretendido. A
criação efetiva do tópico e a publicação dos alertas
dependem de comprovação na execução integrada.

## Contrato de saída

| Campo | Significado |
|---|---|
| card_id | Identificador do cartão associado ao padrão |
| first_transaction_id | Primeira transação da correspondência |
| middle_transaction_id | Transação intermediária da correspondência |
| last_transaction_id | Última transação da correspondência |
| transaction_count | Quantidade de transações correspondentes |
| first_rowtime | Tempo inicial da correspondência |
| last_rowtime | Tempo final da correspondência |

Os tipos finais devem ser confirmados com DESCRIBE no Flink.

## Regra de geração

- Mesmo card_id, obrigatoriamente não nulo
- Três transações consecutivas
- amount > 0 em cada transação
- Intervalo máximo de 60 segundos
- AFTER MATCH SKIP PAST LAST ROW

SQL da regra:
`sql/fraud_detection/pattern/01_match_recognize.sql`

## Watermark

Consulta de observação:
`sql/validation/01_inspect_watermark.sql`

O atributo temporal utilizado é o $rowtime do Kafka.
A estratégia padrão do Confluent utiliza SOURCE_WATERMARK,
com tolerância padrão de 180 milissegundos para desordem.

A janela de 60 segundos define a regra de fraude;
não representa o atraso do watermark.

Execução integral (run-20261111, 2026-11-12):
- [x] `SHOW CREATE TABLE` inspecionado pelo `flink-setup` (PK e changelog)
- [x] Atributo `$rowtime` aceito no temporal join e no `MATCH_RECOGNIZE`
- [ ] `CURRENT_WATERMARK` não foi consultado isoladamente
- [x] Statement de detecção em RUNNING
- [x] Correspondência do cenário registrada no destino

Um watermark NULL inicial não comprova falha.
A ausência de alertas também exige verificar chegada
de eventos, progresso temporal e condições do padrão.

**Consequência observada de usar `$rowtime`:** o tempo é o da chegada ao
Kafka. No snapshot inicial os 2000 registros chegam quase juntos e todo cartão
do seed com 3 ou mais transações gera alerta. Um consumidor real deve
descartar alertas do snapshot ou a regra deve usar `event_time` com watermark
próprio. A verificação do desafio filtra pelos IDs do cenário por isso.

## Evidência e privacidade

Registrar estado do statement, quantidade de alertas e
tempos de correspondência. Utilizar somente dados sintéticos
ou identificadores mascarados nos relatórios.

## Estado

VALIDADO NO FLINK REAL (run-20261111): alerta do cenário emitido em
`fraud.pattern_matches` com os três IDs; evidência em
`evidencias/runs/run-20261111/flink/fraud-scenario-alert.json`.
