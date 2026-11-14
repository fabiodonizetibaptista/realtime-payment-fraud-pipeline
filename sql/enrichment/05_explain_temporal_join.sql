EXPLAIN
-- Etapa 9: enriquecimento temporal de transacoes com contas.
-- Chave de relacionamento: account_id.
-- Referencia temporal: timestamp Kafka ($rowtime).
-- Executar em modo Streaming, nunca Snapshot.
-- LEFT JOIN preserva transacoes sem correspondencia em accounts.

SELECT
    t.transaction_id,
    t.account_id,
    t.card_id,
    t.merchant_id,
    t.amount,
    t.currency,
    t.transaction_status,
    t.event_time,
    t.`$rowtime` AS transaction_rowtime,
    a.customer_id,
    a.account_status,
    a.country_code
FROM `desafio-final`.`desafio-basic`.`payments.public.transactions` AS t
LEFT JOIN `desafio-final`.`desafio-basic`.`payments.public.accounts`
    FOR SYSTEM_TIME AS OF t.`$rowtime` AS a
    ON t.account_id = a.account_id;
