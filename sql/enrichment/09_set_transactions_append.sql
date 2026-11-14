-- Interpretar transactions como fluxo de eventos append-only.
-- Necessario para usar $rowtime no lado esquerdo do Temporal Join.
-- Atualizacoes/deletes CDC requerem avaliacao separada.
ALTER TABLE `desafio-final`.`desafio-basic`.`payments.public.transactions` SET ('changelog.mode' = 'append');
