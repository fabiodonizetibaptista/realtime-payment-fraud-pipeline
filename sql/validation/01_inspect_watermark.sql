-- Etapa 12: observar o watermark no fluxo de transacoes.
-- Executar em modo Streaming durante a validacao integral.
-- CURRENT_WATERMARK pode retornar NULL enquanto o operador
-- ainda nao recebeu um watermark comum de todas as entradas.

SELECT
    t.`$rowtime` AS transaction_rowtime,
    CURRENT_WATERMARK(t.`$rowtime`) AS current_watermark
FROM `desafio-final`.`desafio-basic`.`payments.public.transactions` AS t
WHERE t.card_id IS NOT NULL;
