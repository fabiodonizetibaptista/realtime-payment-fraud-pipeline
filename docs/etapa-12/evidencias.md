# Etapa 12 — Evidências de cenários e alertas

## 1. Identificação da execução

- Branch: etapa-12
- Commit executado: PENDENTE
- Data da execução: PENDENTE
- Ambiente: PENDENTE
- Status: AGUARDANDO EXECUÇÃO INTEGRAL

## 2. Comandos e registros de teste

Script: `scripts/fraud_scenarios.py`

Preparação local:

```bash
python3 -m scripts.fraud_scenarios plan
```

Execução real, somente após autorização:

```bash
python3 -m scripts.fraud_scenarios execute --confirm-execute
```

O manifesto privado `.local/etapa12-scenarios.json`
mantém os IDs sintéticos usados no teste.

- [ ] Manifesto criado
- [ ] Quatro transações inseridas
- [ ] IDs sintéticos reconciliados com a origem
- [ ] CDC confirmou a propagação dos eventos

Não publicar o manifesto nem identificadores reais.

## 3. Resultado esperado versus observado

| Cenário | Esperado | Observado | Status |
|---|---|---|---|
| Uma transação legítima em cartão separado | Nenhum alerta atribuível ao cenário | PENDENTE | PENDENTE |
| Três transações positivas no mesmo cartão, até 60 s | Uma correspondência | PENDENTE | PENDENTE |
| Temporalidade e watermark | Processamento temporal coerente | PENDENTE | PENDENTE |
| Rastreabilidade | Três IDs da correspondência identificáveis | PENDENTE | PENDENTE |

A verificação deve considerar os IDs sintéticos do teste,
e não somente a quantidade global de alertas.

## 4. Destino e mensagem de alerta

Destino implementado: `fraud.pattern_matches`

SQL de persistência:
`sql/fraud_detection/continuous/01_continuous_matches.sql`

SQL de inspeção:
`sql/fraud_detection/continuous/02_inspect_matches.sql`

Contrato:
`docs/etapa-12/contrato_alertas.md`

Campos esperados:

- card_id
- first_transaction_id
- middle_transaction_id
- last_transaction_id
- transaction_count
- first_rowtime
- last_rowtime

Evidências pendentes:

- [ ] Statement contínuo em RUNNING
- [ ] Alerta observado na tabela de destino
- [ ] Quantidade de transações igual a 3
- [ ] Intervalo temporal confirmado
- [ ] IDs do alerta reconciliados com os eventos inseridos

Registrar somente evidências sanitizadas.

## 5. Cenários positivos e negativos

### Positivo — fraude simulada

- Três INSERTs independentes
- Mesmo card_id
- amount > 0
- Intervalo de até 60 segundos
- Correspondência esperada no destino

Resultado real: PENDENTE

### Negativo — transação legítima

- Um INSERT isolado
- Cartão diferente do cenário fraudulento
- Nenhuma correspondência atribuível ao evento

Resultado real: PENDENTE

## 6. Watermark

SQL:
`sql/validation/01_inspect_watermark.sql`

- [ ] Watermark observado
- [ ] Progresso temporal confirmado
- [ ] Resultado interpretado considerando a chegada de eventos

A ausência inicial de correspondências não significa,
isoladamente, falha de compilação ou processamento.

## 7. Destino citado pelo instrutor

A transcrição menciona um termo semelhante a "CPL",
sem identificação suficientemente confiável.

- Destino implementado: fraud.pattern_matches
- Destino original do instrutor: NÃO CONFIRMADO
- Validação no material SQL/configuração: PENDENTE

Não declarar equivalência sem evidência.

## 8. Gate final

- [ ] Cenário legítimo sem alerta indevido
- [ ] Cenário fraudulento identificado
- [ ] Alerta observado no destino
- [ ] Três transações rastreáveis

**STATUS: CENÁRIOS PREPARADOS; INSERÇÃO REAL E ALERTAS NÃO COMPROVADOS.**
