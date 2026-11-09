-- Etapa 11.1: processamento continuo e persistencia.
-- Executar uma unica vez na criacao limpa do ambiente.
-- A tabela criada possui um topico Kafka associado.
-- O statement de criacao deve permanecer em execucao.

CREATE TABLE `desafio-final`.`desafio-basic`.`fraud.pattern_matches`
WITH ('changelog.mode' = 'append')
AS
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
