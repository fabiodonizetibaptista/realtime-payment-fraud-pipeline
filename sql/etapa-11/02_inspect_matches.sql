-- Etapas 11.2 e 11.3: inspecao independente.
-- Executar como consulta Snapshot, em outro statement.
-- Nao interromper o processamento continuo.

SELECT
    card_id,
    first_transaction_id,
    last_transaction_id,
    transaction_count,
    first_rowtime,
    last_rowtime
FROM `desafio-final`.`desafio-basic`.`fraud.pattern_matches`
LIMIT 50;
