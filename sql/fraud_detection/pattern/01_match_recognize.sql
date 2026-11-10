-- Etapa 10: deteccao de sequencias de transacoes por cartao.
-- Fonte: Temporal Join da Etapa 9.
-- Executar em modo Streaming no Confluent Cloud Flink SQL.
--
-- Regra:
--   1. Mesmo cartao (card_id).
--   2. Tres transacoes consecutivas.
--   3. Todas com amount > 0.
--   4. Intervalo maximo de 60 segundos.
--   5. Nao reutilizar transacoes apos uma correspondencia.
--
-- Consulta somente leitura: nao cria tabelas nem grava alertas.

WITH transacoes_enriquecidas AS (
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
        ON t.account_id = a.account_id
    -- Apenas cartoes identificados participam da deteccao.
    WHERE t.card_id IS NOT NULL
)

SELECT
    card_id,
    first_transaction_id,
    middle_transaction_id,
    last_transaction_id,
    transaction_count,
    first_rowtime,
    last_rowtime
FROM transacoes_enriquecidas
MATCH_RECOGNIZE (
    PARTITION BY card_id
    ORDER BY transaction_rowtime
    MEASURES
        FIRST(T.transaction_id) AS first_transaction_id,
        LAST(T.transaction_id, 1) AS middle_transaction_id,
        LAST(T.transaction_id) AS last_transaction_id,
        COUNT(T.transaction_id) AS transaction_count,
        FIRST(T.transaction_rowtime) AS first_rowtime,
        LAST(T.transaction_rowtime) AS last_rowtime
    ONE ROW PER MATCH
    AFTER MATCH SKIP PAST LAST ROW
    PATTERN (T{3}) WITHIN INTERVAL '60' SECOND
    DEFINE
        T AS T.amount > 0
);
