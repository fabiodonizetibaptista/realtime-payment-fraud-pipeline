-- Etapa 11.4: observar registros sem cartao.
-- Consultar a origem, pois a regra da Etapa 10
-- exclui registros com card_id nulo.

SELECT
    transaction_id,
    account_id,
    card_id,
    amount,
    event_time
FROM `desafio-final`.`desafio-basic`.`payments.public.transactions`
WHERE card_id IS NULL
LIMIT 50;
